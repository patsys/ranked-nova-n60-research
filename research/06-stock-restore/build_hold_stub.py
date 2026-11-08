"""Read-only RAM probe that retains the native USB-menu return, no flash writes."""
from pathlib import Path
import sys,struct,json,hashlib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from usb_block_reader import build_block,BASE
from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
from unicorn import *
from unicorn.arm_const import *
image=bytearray(build_block(0x101c,6)[0])
source='''
 mov r0,lr
 movs r2,#0x10
 lsls r2,#8
 adds r2,#0x21
 cmp r0,r2
 bne done
 ldr r0,[sp,#52]
 movs r2,#0xc
 lsls r2,#8
 adds r2,#0xc3
 cmp r0,r2
 bne done
 ldr r0,[sp,#116]
 movs r2,#8
 lsls r2,#8
 adds r2,#0x49
 cmp r0,r2
 beq hold
 adds r2,#0x36
 cmp r0,r2
 bne done
 subs r2,#0x36
hold:
 str r2,[sp,#116]
 movs r2,#0x20
 lsls r2,#24
 adds r2,#255
 adds r2,#66
 str r2,[sp,#52]
done:
 movs r0,#0
 bx lr
'''
code=bytes(Ks(KS_ARCH_ARM,KS_MODE_THUMB).asm(source,BASE+0x80)[0]);assert 0x80+len(code)<=0xda
image[0x80:0x80+len(code)]=code
flash=(ROOT/'firmware_dump/flash_cpu_pass1.bin').read_bytes();cases=[]
for caller in [0x849,0x87f]:
 u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);u.mem_map(0,0x20000);u.mem_write(0,flash);u.mem_write(0xa00,b'\x70\x47');u.mem_map(BASE,0x4000);u.mem_write(BASE,bytes(image))
 sp=BASE+0x1000;ctx=BASE+0x2000;u.reg_write(UC_ARM_REG_SP,sp);u.mem_write(sp+36,struct.pack('<5I',ctx,5,6,7,0xcc3));u.mem_write(sp+116,struct.pack('<I',caller));u.mem_write(ctx+0x214,struct.pack('<I',0xa01))
 writes=[];replies=[]
 u.hook_add(UC_HOOK_MEM_WRITE,lambda uc,a,p,n,v,d:writes.append((p,n,v)))
 u.hook_add(UC_HOOK_CODE,lambda uc,a,n,d:replies.append(bytes(uc.mem_read(ctx+8,6))),begin=0xa00,end=0xa00)
 u.emu_start(0x101d,0xe70,count=1000)
 assert replies==[flash[0x101c:0x1022]]
 assert struct.unpack('<I',u.mem_read(sp+116,4))[0]==0x849
 assert all((p in [sp-8,sp-4,sp+52,sp+116] and n==4) or (p==ctx+4 and n==2) or (ctx+8<=p<ctx+14 and n==1) for p,n,v in writes)
 cases.append(dict(previous_native_caller=hex(caller),new_native_caller='0x849',reply_hex=replies[0].hex()))
out=ROOT/'stock_restore';(out/'hold_stub.bin').write_bytes(image)
r=dict(passed=True,sha256=hashlib.sha256(image).hexdigest(),cases=cases,scope='Read-only boot-code reply and guarded native caller return in RAM; continuous host keepalive still required')
(out/'hold_stub_validation.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps(r,indent=2))
