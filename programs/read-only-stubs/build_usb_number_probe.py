"""Guarded RAM-stack redirection to the observed native status reply path.

Only START entry 0x13a is active. No flash/controller accesses. This payload
writes one verified saved return word on the caller's RAM stack, not flash.
It relies on live-read code/ABI documented in CALLER_TRACE.md.
"""
from pathlib import Path
import sys,json,hashlib,struct,argparse
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root.parent/'.tools'))
from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_MEM_WRITE,UC_HOOK_CODE
from unicorn.arm_const import *

base=0x20000000
parser=argparse.ArgumentParser()
parser.add_argument('--number',type=int,default=42)
args=parser.parse_args()
assert 0<=args.number<=255
ks=Ks(KS_ARCH_ARM,KS_MODE_THUMB)
blob=bytearray(b'\x70\x47'*220)
for entry in [0,0x24,0x6c,0xda,0xfc,0x13a]: blob[entry:entry+4]=b'\x00\x20\x70\x47'
branch,_=ks.asm('b #0x20000160',base+0x13a)
blob[0x13a:0x13c]=bytes(branch)
source='''
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
    adds r2, #6
    str r2, [sp, #52]
    movs r1, #42
done:
    movs r0, #0
    bx lr
'''
source=source.replace('movs r1, #42',f'movs r1, #{args.number}')
encoded,_=ks.asm(source,base+0x160)
assert 0x160+len(encoded)<=440
blob[0x160:0x160+len(encoded)]=bytes(encoded)
md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS)
instructions=list(md.disasm(bytes(blob),base))
assert sum(i.size for i in instructions)==440
assert all(i.mnemonic in ['b','bx','movs','mov','lsls','adds','cmp','bne','ldr','str'] for i in instructions)
stores=[i for i in instructions if i.mnemonic=='str']
assert len(stores)==1 and stores[0].op_str=='r2, [sp, #0x34]'

def setup(saved=0xcc3):
    uc=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
    uc.mem_map(0,0x2000); uc.mem_map(base,0x3000)
    uc.mem_write(base,bytes(blob))
    # All control-flow bytes below were independently read from the device.
    uc.mem_write(0x22c,bytes.fromhex('03b40148019001bd3b010020'))
    uc.mem_write(0x101c,bytes.fromhex('fff706f933e0'))
    uc.mem_write(0x108a,bytes.fromhex('002068e7'))
    uc.mem_write(0xf60,bytes.fromhex('09b0f0bd'))
    uc.mem_write(0xcc8,bytes.fromhex('2046fff777ffcfe0'))
    uc.mem_write(0xbbc,bytes.fromhex('7047')) # Mock only the reply function body.
    sp=base+0x1000; context=base+0x1800
    uc.reg_write(UC_ARM_REG_SP,sp)
    uc.mem_write(sp+36,struct.pack('<5I',context,0x55555555,0x66666666,0x77777777,saved))
    writes=[]; replies=[]
    uc.hook_add(UC_HOOK_MEM_WRITE,lambda u,a,addr,size,value,d:writes.append((addr,size,value)))
    uc.hook_add(UC_HOOK_CODE,lambda u,a,s,d:replies.append((u.reg_read(UC_ARM_REG_R0),u.reg_read(UC_ARM_REG_R1))),begin=0xbbc,end=0xbbc)
    return uc,sp,context,writes,replies

uc,sp,ctx,writes,replies=setup()
uc.emu_start(0x101d,0xe70,count=100)
assert uc.reg_read(UC_ARM_REG_PC)==0xe70 and replies==[(ctx,args.number)],replies
assert uc.reg_read(UC_ARM_REG_SP)==sp+56
assert all(a in [sp-8,sp-4,sp+52] and s==4 for a,s,v in writes),writes
assert sum(a==sp+52 and v==0xcc9 for a,s,v in writes)==1
uc,sp,ctx,writes,replies=setup(saved=0xaa1)
uc.reg_write(UC_ARM_REG_LR,0x1021)
uc.emu_start((base+0x13a)|1,0xaa0,count=100)
assert not writes and not replies and uc.reg_read(UC_ARM_REG_SP)==sp+56
uc,sp,ctx,writes,replies=setup()
uc.reg_write(UC_ARM_REG_LR,(base+0x2800)|1)
uc.emu_start((base+0x13a)|1,base+0x2800,count=100)
assert not writes and not replies and uc.reg_read(UC_ARM_REG_SP)==sp

stem='usb_number' if args.number==42 else f'usb_number_{args.number}'
(root/f'{stem}.bin').write_bytes(blob)
(root/f'{stem}.s').write_text(source)
(root/f'{stem}.disasm.txt').write_text('\n'.join(f'{i.address:08x}: {i.mnemonic} {i.op_str}' for i in instructions))
manifest=dict(bytes=440,sha256=hashlib.sha256(blob).hexdigest(),expected_usb_status_byte=args.number,
              guards=dict(incoming_lr='0x00001021',saved_lr='0x00000cc3'),
              ram_write='SP+52: 0x00000cc3 -> 0x00000cc9',
              checks='native verified control-flow emulation + two guard-failure cases passed',
              limitation='reply helper body mocked in emulator; physical USB return not yet verified')
(root/f'{stem}.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest,indent=2))
