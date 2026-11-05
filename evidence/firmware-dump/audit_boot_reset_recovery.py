"""Original boot reset/recovery selection with captured config. Offline only."""
from pathlib import Path
import struct,json,sys,hashlib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.tools'))
from unicorn import *
from unicorn.arm_const import *
original=(ROOT/'firmware_dump/flash_cpu_pass1.bin').read_bytes()
meta=(ROOT/'firmware_dump/boot_safety_audit/metadata_10000600.bin').read_bytes()
body=(ROOT/'qmk_flash/qmk_via_application_pages.bin').read_bytes()
assert hashlib.sha256(body).hexdigest()=='071ee8e608a2332b6462a12191260572319706cbc67a96df2d405276848a92ef'
image=bytearray(original);image[0x2000:0x10a00]=body
app_reset=struct.unpack_from('<I',image,0x2004)[0]&~1
results=[]
for request,ram_pattern,clock_ok,label in [
 (0,0,True,'ordinary reset, request0'),
 (0,0xa5,True,'ordinary reset with retained RAM pattern'),
 (0,0x5a,True,'second tap RAM pattern, no request'),
 (0x5ac396c5,0xa5,True,'explicit original boot request'),
 (0x5ac396c4,0xa5,True,'near-magic value does not select USB'),
 (0xffffffff,0xa5,True,'erased request does not select USB'),
 (0,0xa5,False,'boot clock verification fails, request0'),
 (0x5ac396c5,0xa5,False,'boot clock verification fails before request check')]:
 u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
 for a,n in [(0,0x20000),(0x20000000,0x4000),(0x40000000,0x20000),(0x10000000,0x1000),(0xe000e000,0x2000)]:u.mem_map(a,n)
 u.mem_write(0,bytes(image));u.mem_write(0x10000600,meta)
 u.mem_write(0x20000000,bytes([ram_pattern])*0x4000)
 u.mem_write(0x20000754,struct.pack('<III',0x5a5a5a5a,0xa5a5a5a5,0x5555aaaa))
 u.mem_write(0x4001400c,struct.pack('<I',request));u.reg_write(UC_ARM_REG_SP,0x20000bf0)
 event=[];main_guards=[];pre_main_external_reads=[];reached_main=False;request_reads=[]
 def code(uc,a,size,user):
  global reached_main
  if a==0x700:
   reached_main=True;main_guards.extend(struct.unpack('<III',uc.mem_read(0x20000754,12)))
  if a==0x9bc:uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  if a in (0x848,0x24c,app_reset):event.append(hex(a));uc.emu_stop()
 def memory(uc,access,a,size,value,user):
  if access==UC_MEM_READ:
   if not reached_main and a>=0x40000000:pre_main_external_reads.append(hex(a))
   if a==0x4001400c:request_reads.append(a)
   if not clock_ok and a==0x40014050:uc.mem_write(a,b'\0'*4)
  if access==UC_MEM_WRITE and a<0x20000:raise AssertionError('No flash writes permitted in this test')
 u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,memory)
 u.emu_start(0x1cd,0,count=100000)
 assert len(event)==1 and main_guards==[0,0,0] and not pre_main_external_reads
 expected='0x24c' if not clock_ok else ('0x848' if request==0x5ac396c5 else hex(app_reset))
 assert event==[expected],(label,event,expected)
 results.append(dict(case=label,initial_request=hex(request),initial_ram_pattern=hex(ram_pattern),
  clock_readback_matches=clock_ok,result=event[0],main_guard_words=main_guards,
  request_read_count=len(request_reads),request_after=hex(struct.unpack('<I',u.mem_read(0x4001400c,4))[0]),
  pre_main_external_reads=pre_main_external_reads,passed=True))
report=dict(passed=True,cases=results,case_count=len(results),hardware_access=False,
 body_sha256=hashlib.sha256(body).hexdigest(),metadata_sha256=hashlib.sha256(meta).hexdigest(),
 fixtures='Actual recovered reset/startup/main, current prepared QMK body/captured information block; originaldelay9bc bypassed, RAM-like MMIO; clock-mismatch fixture alters readback.',
 limitations='Does not model silicon power/reset retention, oscillator behavior, physical straps, or physical sensor state. RAM patterns are fixtures, not a claim that power removal preserves RAM.')
(ROOT/'firmware_dump/boot_reset_recovery_validation.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k!='cases'},indent=2))
