"""Bounded CPU code reads returned as real USB bytes, using verified ABI.

Only known caller/target code windows are allowed. Each request uploads own
code via START; no DATA or COMPLETE support here. Writes one guarded RAM
stack return word. No flash erase/program or peripheral access in payload.
"""
import json,struct,hashlib,argparse
from pathlib import Path
from timing_channel import BASE,ENTRIES,CODE_WINDOWS,Channel,probe
from test_usb_repeated_live import request
from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_MEM_WRITE,UC_HOOK_CODE
from unicorn.arm_const import *

ART=Path('readonly_stub/usb_read_probes')

def build_read_byte(address):
    assert any(lo<=address<hi for lo,hi in CODE_WINDOWS),'Address outside verified code windows'
    ks=Ks(KS_ARCH_ARM,KS_MODE_THUMB)
    image=bytearray(b'\x70\x47'*220)
    for offset in ENTRIES: image[offset:offset+4]=b'\x00\x20\x70\x47'
    branch,_=ks.asm('b #0x20000160',BASE+0x13a); image[0x13a:0x13c]=bytes(branch)
    source=f'''
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
        movs r1, #{address>>8}
        lsls r1, #8
        adds r1, #{address&255}
        ldrb r1, [r1]
        adds r2, #6
        str r2, [sp, #52]
done:
        movs r0, #0
        bx lr
    '''
    encoded,_=ks.asm(source,BASE+0x160)
    assert 0x160+len(encoded)<=440
    image[0x160:0x160+len(encoded)]=bytes(encoded)
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS)
    decoded=list(md.disasm(bytes(image),BASE))
    assert sum(i.size for i in decoded)==440
    assert all(i.mnemonic in ['b','bx','mov','movs','lsls','adds','cmp','bne','ldr','ldrb','str'] for i in decoded)
    assert [(i.mnemonic,i.op_str) for i in decoded if i.mnemonic=='str']==[('str','r2, [sp, #0x34]')]
    uc=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
    uc.mem_map(0,0x2000); uc.mem_map(BASE,0x3000)
    uc.mem_write(BASE,bytes(image))
    fixtures={0x22c:'03b40148019001bd3b010020',0x101c:'fff706f933e0',0x108a:'002068e7',
              0xf60:'09b0f0bd',0xcc8:'2046fff777ffcfe0',0xbbc:'7047'}
    for location,hexdata in fixtures.items(): uc.mem_write(location,bytes.fromhex(hexdata))
    if not any(start<=address<start+len(bytes.fromhex(s)) for start,s in fixtures.items()): uc.mem_write(address,b'\xa5')
    expected=uc.mem_read(address,1)[0]
    sp=BASE+0x1000; context=BASE+0x1800
    uc.reg_write(UC_ARM_REG_SP,sp)
    uc.mem_write(sp+36,struct.pack('<5I',context,5,6,7,0xcc3))
    writes=[]; result=[]
    uc.hook_add(UC_HOOK_MEM_WRITE,lambda u,a,addr,size,value,d:writes.append((addr,size,value)))
    uc.hook_add(UC_HOOK_CODE,lambda u,a,s,d:result.append((u.reg_read(UC_ARM_REG_R0),u.reg_read(UC_ARM_REG_R1))),begin=0xbbc,end=0xbbc)
    uc.emu_start(0x101d,0xe70,count=100)
    assert result==[(context,expected)] and uc.reg_read(UC_ARM_REG_SP)==sp+56
    assert all(a in [sp-8,sp-4,sp+52] and size==4 for a,size,v in writes)
    ART.mkdir(parents=True,exist_ok=True)
    stem=f'read_{address:08x}'
    (ART/f'{stem}.bin').write_bytes(image)
    (ART/f'{stem}.s').write_text(source)
    return bytes(image),dict(address=f'0x{address:08x}',sha256=hashlib.sha256(image).hexdigest(),mocked_reply_helper_emulation_passed=True)

class Reader:
    def __init__(self):
        self.channel=Channel(); self.records=[]

    def open(self):
        self.channel.open()
        assert self.channel.version['version_words_hex']==['a1050000','a1040000'],'Unsupported live firmware identity'

    def read(self,address,length):
        assert 1<=length<=256 and any(lo<=address and address+length<=hi for lo,hi in CODE_WINDOWS)
        data=[]
        for current in range(address,address+length):
            blob,spec=build_read_byte(current)
            reply=request(self.channel,blob)
            self.records.append(dict(spec=spec,reply=reply))
            data.append(reply['number'])
        return bytes(data)

    def close(self,restore_application=True):
        result={}
        if restore_application and self.channel.h:
            # Return to the repeatedly verified ordinary START/getv exit path.
            normal,_=probe('cal',0)
            result['normal_START']=self.channel.send(normal)
        result['final_state']=self.channel.close()
        return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--address',type=lambda s:int(s,0))
    parser.add_argument('--length',type=int,default=16)
    args=parser.parse_args()
    reader=Reader(); log=dict(method='direct one-byte USB reply per bounded code-byte request',blocks=[])
    try:
        reader.open(); log['version']=reader.channel.version
        if args.address is None:
            known=reader.read(0x101c,6)
            assert known==bytes.fromhex('fff706f933e0'),known.hex()
            log['blocks'].append(dict(address='0x0000101c',hex=known.hex(),matches_independent_timing_read=True))
            body=reader.read(0xbbc,32)
            assert body[:16]==bytes.fromhex('10b5002809d0017201218180ff30ff30')
            Path('usb_reply_builder_0bbc.bin').write_bytes(body)
            log['blocks'].append(dict(address='0x00000bbc',hex=body.hex(),first16_match_independent_timing_read=True))
        else:
            block=reader.read(args.address,args.length)
            log['blocks'].append(dict(address=f'0x{args.address:08x}',hex=block.hex()))
        log['verified']=True
    except Exception as error:
        log['error']=str(error); raise
    finally:
        log['transactions']=reader.records
        log['cleanup']=reader.close()
        name='usb_code_read_live.json' if args.address is None else f'usb_read_{args.address:08x}_{args.length}_live.json'
        Path(name).write_text(json.dumps(log,indent=2))
        print(json.dumps({k:v for k,v in log.items() if k!='transactions'}),flush=True)
