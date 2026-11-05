"""Offline vendor stub address boundary audit; MMIO stores are modeled only."""
from pathlib import Path
import struct,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent/'.tools'))
from unicorn import *
from unicorn.arm_const import *
ART=Path('firmware_dump/boot_safety_audit');ART.mkdir(exist_ok=True)
flash=Path('firmware_dump/flash_cpu_pass1.bin').read_bytes();ram=Path('firmware_dump/boot_initial_ram.bin').read_bytes();stub=Path('vendor_stub.bin').read_bytes()
cases=[]
for off in [0x24,0x6c]:
 for page in [0,15,16,207,208,255,256,0xffffffff]:
  u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
  for a,n in [(0,0x20000),(0x20000000,0x4000),(0x40013000,0x1000)]:u.mem_map(a,n)
  u.mem_write(0,flash);u.mem_write(0x20000000,ram);u.mem_write(0x20000000,stub)
  u.mem_write(0x20000754,struct.pack('<3I',0x5a5a5a5a,0xa5a5a5a5,0x5555aaaa));u.mem_write(0x20001000,struct.pack('<128I',*range(128)));u.reg_write(UC_ARM_REG_SP,0x20002000);u.reg_write(UC_ARM_REG_LR,0x1ff01);u.reg_write(UC_ARM_REG_R0,page);u.reg_write(UC_ARM_REG_R1,0x20001000)
  writes=[]
  def w(uc,a,p,n,v,d):
   if 0x40013000<=p<0x40014000:writes.append((p,v))
  u.hook_add(UC_HOOK_MEM_WRITE,w);u.emu_start((0x20000000+off)|1,0x1ff00,count=100000)
  assert u.reg_read(UC_ARM_REG_PC)==0x1ff00
  status=u.reg_read(UC_ARM_REG_R0);addresses=[v for p,v in writes if p==0x40013004];commands=[v for p,v in writes if p==0x40013000]
  if page<=255:
   assert status==0,(hex(off),page,status,writes[-6:])
   expected=[page<<7] if off==0x24 else [(page<<7)|i for i in range(128)]
   assert addresses==expected
   assert commands==([2] if off==0x24 else [1]*128)
  else:assert status==2 and not writes
  cases.append(dict(entry=hex(off),page=page,status=status,command_count=len(commands),first_word_address=hex(addresses[0]) if addresses else None,last_word_address=hex(addresses[-1]) if addresses else None,mmio_writes=writes[:4] if len(writes)<=4 else writes[:3]+writes[-1:]))
r=dict(passed=True,cases=cases,method='Actual vendor stub and recovered boot ABI helper execution; RAM guard fixture matches native DATA preconditions; MMIO modeled as memory with busy bit clear; no real flash hardware',limitation='Command-register reachability is not proof that physical flash accepts an erase/program; hardware protection remains unknown')
(ART/'stub_page_boundaries.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print('PASS16vendorstubboundarycases; bootpages0and15issueerase/programcommandsinmodel')



