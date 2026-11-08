"""Bounded no-store Thumb probes carried only in observed START framing.

No DATA/COMPLETE support. Data reads are restricted to a small code window
around the previously measured caller. This is a research tool, not a flasher.
"""
from pathlib import Path
import sys,struct,functools,time,hashlib
from boot_console import open_bootloader,get_version,hid
from extract_vendor_stub import extract
sys.path.insert(0,str(Path(__file__).resolve().parent/'.tools'))
from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_MEM_WRITE,UC_HOOK_CODE
from unicorn.arm_const import *

BASE=0x20000000
ENTRIES=[0,0x24,0x6c,0xda,0xfc,0x13a]
CODE_WINDOWS=[(0x200,0x300),(0xb00,0xd00),(0xf00,0x1100)]
ARTIFACTS=Path('readonly_stub/caller_probes')

def probe(kind,value=0,high=False,*,bits=18,whole=False):
    ks=Ks(KS_ARCH_ARM,KS_MODE_THUMB)
    assert bits in [15,18]
    if kind=='cal':
        assert value in ([0,255] if whole else [0,8])
        expression=f'movs r0, #{value}'
        sample=value
        name=f'cal{value}'
    elif kind=='byte':
        assert any(lo<=value<hi for lo,hi in CODE_WINDOWS),'Read outside verified caller/branch-target windows'
        expression=f'movs r0, #{value>>8}; lsls r0, #8; adds r0, #{value&255}; ldrb r0, [r0]; '
        if high and not whole: expression+='lsrs r0, #4; '
        if not whole: expression+='movs r1, #15; ands r0, r1'
        sample=165 if whole else 10 if high else 5
        name=f'byte_{value:08x}_{int(high)}'
    elif kind in ['saved','savedcheck']:
        assert kind=='savedcheck' or 0<=value<8
        expression='mov r0, sp; ldr r0, [r0, #52]; '
        if kind=='saved':
            if value: expression+=f'lsrs r0, #{4*value}; '
            sample=(0x12345679>>(4*value))&15
        else:
            expression+='mov r1, r0; lsrs r1, #16; eors r0, r1; mov r1, r0; lsrs r1, #8; eors r0, r1; mov r1, r0; lsrs r1, #4; eors r0, r1; '
            sample=functools.reduce(int.__xor__,[(0x12345679>>s)&15 for s in range(0,32,4)],0)
        expression+='movs r1, #15; ands r0, r1'
        name=f'{kind}_{value}'
    else:
        raise ValueError('Unsupported probe kind')
    if whole: name+=f'_whole{bits}'
    expression+='''
        cmp r0, #0
        beq done
        lsls r0, #18
    loop:
        subs r0, #1
        bne loop
    done:
        movs r0, #0
        bx lr
    '''
    expression=expression.replace('lsls r0, #18',f'lsls r0, #{bits}')
    image=bytearray(b'\x70\x47'*220)
    for offset in ENTRIES:
        branch,_=ks.asm('b #0x20000160',BASE+offset)
        image[offset:offset+2]=bytes(branch)
    code,_=ks.asm(expression,BASE+0x160)
    assert 0x160+len(code)<=440
    image[0x160:0x160+len(code)]=bytes(code)
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS)
    instructions=list(md.disasm(bytes(image),BASE))
    assert sum(i.size for i in instructions)==440
    assert all(i.mnemonic in ['b','bx','movs','mov','lsls','adds','ldr','ldrb','lsrs','ands','eors','cmp','beq','subs','bne'] for i in instructions)
    cmp_pc=next(i.address for i in instructions if i.mnemonic=='cmp')
    for entry in ENTRIES:
        uc=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
        uc.mem_map(BASE,0x1000)
        uc.mem_write(BASE,bytes(image))
        uc.mem_map(0,0x2000)
        uc.mem_write(0,b'\xa5'*0x2000)
        stop=BASE+0x800
        uc.reg_write(UC_ARM_REG_LR,stop|1)
        uc.reg_write(UC_ARM_REG_SP,BASE+0x400)
        uc.mem_write(BASE+0x400+52,struct.pack('<I',0x12345679))
        writes=[]
        sampled=[]
        uc.hook_add(UC_HOOK_MEM_WRITE,lambda *args:writes.append(args))
        uc.hook_add(UC_HOOK_CODE,lambda u,a,s,d:sampled.append(u.reg_read(UC_ARM_REG_R0)),begin=cmp_pc,end=cmp_pc)
        uc.emu_start((BASE+entry)|1,stop,count=2*(sample<<bits)+100)
        assert uc.reg_read(UC_ARM_REG_PC)==stop and uc.reg_read(UC_ARM_REG_R0)==0
        assert not writes and sampled==[sample]
        assert uc.reg_read(UC_ARM_REG_LR)==stop|1
        assert uc.reg_read(UC_ARM_REG_SP)==BASE+0x400
    ARTIFACTS.mkdir(parents=True,exist_ok=True)
    (ARTIFACTS/f'{name}.bin').write_bytes(image)
    (ARTIFACTS/f'{name}.s').write_text(expression)
    (ARTIFACTS/f'{name}.disasm.txt').write_text('\n'.join(f'{i.address:08x}: {i.mnemonic} {i.op_str}' for i in instructions))
    return bytes(image),dict(name=name,kind=kind,value=value,high=high,bits=bits,whole=whole,sha256=hashlib.sha256(image).hexdigest(),emulated_calls=6)

class Channel:
    def __init__(self):
        self.original,old=extract('fw_update.pcap')
        assert len(self.original)==496
        assert struct.unpack_from('<I',self.original,492)[0]==functools.reduce(int.__xor__,struct.unpack('<110I',old),0)
        self.h=None

    def open(self):
        self.h=open_bootloader(True)
        self.version=get_version(self.h)

    def send(self,image):
        assert len(image)==440
        frame=bytearray(self.original)
        frame[52:492]=image
        struct.pack_into('<I',frame,492,functools.reduce(int.__xor__,struct.unpack('<110I',image),0))
        start=time.perf_counter_ns()
        for pos in range(0,len(frame),64):
            assert self.h.write(b'\0'+bytes(frame[pos:pos+64]).ljust(64,b'\0'))==65
        sent=time.perf_counter_ns()
        reply=bytes(self.h.read(65,2000))
        end=time.perf_counter_ns()
        if len(reply)==65 and reply[0]==0: reply=reply[1:]
        record=dict(total_ms=(end-start)/1e6,post_write_ms=(end-sent)/1e6,reply_hex=reply.hex())
        assert len(reply)==64 and reply[:9]==bytes.fromhex('010000730100017704'),record
        return record

    def close(self):
        result={}
        if self.h:
            try: result['exit_query']=get_version(self.h)
            except (OSError,RuntimeError) as error: result['exit_query_error']=str(error)
            self.h.close()
            self.h=None
        for _ in range(40):
            count=len(hid.enumerate(0x3532,0xa0a3))
            if count: break
            time.sleep(.1)
        result['application_collections']=count
        result['bootloader_interfaces']=len(hid.enumerate(0x352d,0x1101))
        return result
