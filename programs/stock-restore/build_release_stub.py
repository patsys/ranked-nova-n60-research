"""RAM-only release of the verified restore session; no flash operations."""
from pathlib import Path
import sys, struct, json, hashlib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'.tools'))
from timing_channel import BASE,ENTRIES
from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
from unicorn import *
from unicorn.arm_const import *
ks=Ks(KS_ARCH_ARM,KS_MODE_THUMB)
image=bytearray(b'\x70\x47'*220)
for entry in ENTRIES: image[entry:entry+4]=b'\x00\x20\x70\x47'
image[0x13a:0x13c]=bytes(ks.asm('b #0x20000080',BASE+0x13a)[0])
source='''
 mov r0,lr
 movs r2,#0x10
 lsls r2,#8
 adds r2,#0x21
 cmp r0,r2
 bne fail
 ldr r0,[sp,#52]
 movs r2,#0xc
 lsls r2,#8
 adds r2,#0xc3
 cmp r0,r2
 bne fail
 ldr r0,[sp,#116]
 movs r2,#8
 lsls r2,#8
 adds r2,#0x49
 cmp r0,r2
 beq release
 adds r2,#0x36
 cmp r0,r2
 bne fail
 b done
release:
 adds r2,#0x36
 str r2,[sp,#116]
done:
 movs r0,#0
 bx lr
fail:
 movs r0,#2
 bx lr
'''
code=bytes(ks.asm(source,BASE+0x80)[0]);assert 0x80+len(code)<=0xda
image[0x80:0x80+len(code)]=code
flash=(ROOT/'firmware_dump/flash_cpu_pass1.bin').read_bytes();cases=[]
for lr,handler,caller in [(0x1021,0xcc3,0x849),(0x1021,0xcc3,0x87f),(0x1021,0xcc3,0xdead),(0x1021,0xaaa,0x849),(0x1201,0xcc3,0x849)]:
 u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);u.mem_map(0,0x20000);u.mem_write(0,flash);u.mem_map(BASE,0x4000);u.mem_write(BASE,bytes(image))
 sp=BASE+0x1000;u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,lr);u.mem_write(sp+52,struct.pack('<I',handler));u.mem_write(sp+116,struct.pack('<I',caller));writes=[]
 u.hook_add(UC_HOOK_MEM_WRITE,lambda uc,a,p,n,v,d:writes.append((p,n,v)))
 u.emu_start(BASE+0x13b,lr&~1,count=500)
 valid=lr==0x1021 and handler==0xcc3 and caller in (0x849,0x87f)
 expected=[(sp+116,4,0x87f)] if valid and caller==0x849 else []
 assert writes==expected and u.reg_read(UC_ARM_REG_R0)==(0 if valid else 2)
 cases.append(dict(caller_lr=hex(caller),handler_lr=hex(handler),incoming_lr=hex(lr),valid=valid,writes=writes))
out=ROOT/'stock_restore';(out/'release_stub.bin').write_bytes(image)
r=dict(passed=True,sha256=hashlib.sha256(image).hexdigest(),bytes=len(image),cases=cases,method='Actual release instructions; only permitted store restores original native caller return at guarded SP+116; no MMIO or flash stores')
(out/'release_stub_validation.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in r.items() if k!='cases'},indent=2))
