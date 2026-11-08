"""Test proposed pin configuration only in emulated metadata, never a device."""
from pathlib import Path
import sys,struct,json,functools,hashlib
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'.tools'))
from unicorn import *
from unicorn.arm_const import *
image=(ROOT/'firmware_dump/flash_cpu_pass1.bin').read_bytes();metadata=(ROOT/'firmware_dump/boot_safety_audit/metadata_10000600.bin').read_bytes();ram=(ROOT/'firmware_dump/boot_initial_ram.bin').read_bytes()
cases=[]
for layout in ['captured','pins_only','pins_and_no_patch_list']:
 for gpio in [0,1,2,3]:
  for badapp in [False,True]:
   m=bytearray(metadata);flash=bytearray(image)
   if layout!='captured':struct.pack_into('<I',m,0x100,0x100) # illustrative encoded pins0/1, NOT a physical pin recommendation
   if layout=='pins_and_no_patch_list':m[0x150:0x190]=b'\xff'*64
   struct.pack_into('<I',m,0x1fc,functools.reduce(int.__xor__,struct.unpack('<127I',m[:0x1fc]),0))
   if badapp:flash[0x2000:0x1a000]=b'\xff'*(0x1a000-0x2000)
   u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
   for a,n in [(0,0x20000),(0x10000000,0x1000),(0x20000000,0x4000),(0x40000000,0x20000),(0xe000e000,0x2000)]:u.mem_map(a,n)
   u.mem_write(0,bytes(flash));u.mem_write(0x10000600,bytes(m));u.mem_write(0x20000000,ram);u.mem_write(0x40018030,struct.pack('<I',gpio));u.reg_write(UC_ARM_REG_SP,0x20000bf0)
   seen=[];reads=[];writes=[]
   def code(uc,a,n,d):
    if a==0x9bc:uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    if a in [0x848,0x8c0]:seen.append(a);uc.emu_stop()
   def access(uc,t,a,n,v,d):
    if t==UC_MEM_READ and 0x40018030<=a<=0x4001803c:reads.append(hex(a))
    if t==UC_MEM_WRITE:writes.append((a,n))
   u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,access)
   u.emu_start(0x701,0,count=200000);assert len(seen)==1
   decision='USB_bootstrap' if seen[0]==0x848 else 'application_call'
   expected='application_call' if layout!='pins_and_no_patch_list' else ('USB_bootstrap' if gpio==0 or badapp else 'application_call')
   assert decision==expected,(layout,gpio,badapp,decision)
   assert bool(reads)==(layout=='pins_and_no_patch_list')
   assert all(not (a<0x20000 or 0x10000000<=a<0x10001000) for a,n in writes)
   cases.append(dict(configuration=layout,synthetic_gpio_bits=gpio,erased_app=badapp,decision=decision,gpio_register_reads=reads,passed=True))
r=dict(cases_passed=len(cases),metadata_sha256=hashlib.sha256(metadata).hexdigest(),cases=cases,critical_result='Changing only pinword does NOT enable recovery with captured valid patch list; GPIO check is bypassed. Removing patch list exposes GPIO/checksum path in model, but also removes existing flash-controller setup.',limitations='Synthetic encodedpins0/1 are not selected physical pins. Removingpatchlist has unverified hardwareeffects. No hardwareaccess/persistentwrites/erase, and no live electricalrecovery proof.')
p=ROOT/'firmware_dump/boot_safety_audit/recovery_enable_test.json';p.write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in r.items() if k!='cases'},indent=2))
