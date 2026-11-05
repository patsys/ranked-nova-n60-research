"""Execute compiled emergency hold/reset paths with modeled analog inputs.

No hardware. Original delays are intercepted, not asserted to have real units.
"""
from pathlib import Path
import hashlib,json,struct,sys,argparse
parser=argparse.ArgumentParser();parser.add_argument('--diagnostic',action='store_true');parser.add_argument('--keymap',choices=['default','neo2'],default='default');parser.add_argument('--rgb',action='store_true');args=parser.parse_args()
MODES=tuple(x+('_diagnostic' if args.diagnostic else '')+('_neo2' if args.keymap=='neo2' else '') for x in ('firmware','firmware_via'))
if args.rgb:MODES=tuple(x+'_rgb' for x in MODES)
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'.tools'))
from unicorn import *
from unicorn.arm_const import *
results=[]
class Fixture:
 def __init__(self,mode,sequence):
  self.out=ROOT/f'qmk_port/build/{mode}';self.elf=(self.out/'nova_qmk_research.elf').read_bytes()
  self.symbols={p[2]:int(p[0],16) for line in (self.out/'nova_qmk_research.nm').read_text().splitlines() if len(p:=line.split())==3}
  self.u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
  for a,n in [(0,0x20000),(0x10000000,0x1000),(0x20000000,0x4000),(0x40000000,0x20000),(0xe000e000,0x2000)]:self.u.mem_map(a,n)
  h=struct.unpack_from('<16sHHIIIIIHHHHHH',self.elf)
  for i in range(h[10]):
   kind,offset,vaddr,paddr,size,memsize,flags,align=struct.unpack_from('<8I',self.elf,h[5]+i*h[9])
   if kind==1 and size:
    self.u.mem_write(vaddr,self.elf[offset:offset+size]);self.u.mem_write(paddr,self.elf[offset:offset+size])
  self.u.mem_write(0x40014120,struct.pack('<I',1))
  self.u.mem_write(0x10000234,struct.pack('<I',0x06a20060)) # Captured factory word, nominal48MHz.
  self.sequence=sequence;self.scan=-1;self.bank=0;self.writes=[];self.samples=0
  self.stop_usb=False;self.fail_matrix=False;self.fail_usb=False;self.events=[]
  self.fail_calibration=False;self.clock_hz_override=None;self.cycle_sequence=False
  self.minsp=self.symbols['__process_stack_end__']
  self.u.hook_add(UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,self.memory)
  self.u.hook_add(UC_HOOK_CODE,self.code)
 def memory(self,u,access,a,size,value,user):
  if access==UC_MEM_WRITE:
   if a<0x20000:raise AssertionError(('flash write',hex(a)))
   if a==0x40018010:
    for bank,pin in enumerate((24,23,22,21,20,19)):
     if value==1<<pin:self.bank=bank
   if a in (0x4001400c,0xe000ed0c):
    self.writes.append((a,value))
    if a==0xe000ed0c:self.events.append('reset_requested');u.emu_stop()
  if access==UC_MEM_READ and 0x4000e09c<=a<=0x4000e0c4 and (a-0x4000e09c)%4==0:
   col=(a-0x4000e09c)//4
   index=max(self.scan,0)
   if self.sequence:index=index%len(self.sequence) if self.cycle_sequence else min(index,len(self.sequence)-1)
   pressed=self.sequence[index] if self.sequence else set()
   u.mem_write(a,struct.pack('<I',100 if (self.bank,col) in pressed else 0));self.samples+=1
 def code(self,u,a,size,user):
  self.minsp=min(self.minsp,u.reg_read(UC_ARM_REG_SP))
  if a in (self.symbols['nova_platform_delay_original_units'],self.symbols['nova_platform_delay_original_long']):
   u.reg_write(UC_ARM_REG_R0,1);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));return
  if a==self.symbols['matrix_scan_custom']:self.scan+=1
  if a==self.symbols['nova_original_clock_calibrate_4_0'] and self.fail_calibration:
   u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));return
  if a==self.symbols['nova_original_clock_effective_hz'] and self.clock_hz_override is not None:
   u.reg_write(UC_ARM_REG_R0,self.clock_hz_override);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));return
  if a==self.symbols['matrix_init_custom'] and self.fail_matrix:
   u.mem_write(self.symbols['nova_matrix_initialization_failed'],b'\x01');u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));return
  if a==self.symbols['nova_usb_keyboard_init']:
   self.events.append('usb_init')
   if self.stop_usb:u.emu_stop()
   if self.fail_usb:u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));return
  if a==self.symbols.get('nova_runtime_halt'):self.events.append('fatal_halt');u.emu_stop()
 def call(self,name,*args):
  self.u.reg_write(UC_ARM_REG_SP,self.symbols['__process_stack_end__']);self.u.reg_write(UC_ARM_REG_LR,0x1ff01)
  for reg,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):self.u.reg_write(reg,value)
  self.u.emu_start(self.symbols[name]|1,0x1ff00,count=2000000)
  returned=self.u.reg_read(UC_ARM_REG_PC)==0x1ff00
  stopped_reset=(name in ('main','mcu_reset','bootloader_jump') and self.events and self.events[-1]=='reset_requested')
  stopped_usb=(name=='main' and self.stop_usb and self.events and self.events[-1]=='usb_init')
  assert returned or stopped_reset or stopped_usb,('instruction budget exhausted or unexpected stop',name,hex(self.u.reg_read(UC_ARM_REG_PC)),self.events)
  return self.u.reg_read(UC_ARM_REG_R0)

policies=[('no keys',1,[set()],False),('Esc held',1,[{(0,0)}],True),
 ('other populated key held',1,[{(5,1)}],True),('absent matrix position ignored',1,[{(5,0)}],False),
 ('released after first scan',1,[{(0,1)},set()],False),
 ('different keys do not count as one hold',1,[{(0,1)},{(0,2)},{(0,3)}],False),
 ('initial empty batch then Esc',1,[set(),{(0,0)}],True),
 ('late held key in readiness window',2,[set()]*50+[{(0,0)}],True),
 ('one shared held key across changes',1,[{(0,1),(0,2)},{(0,1)},{(0,1),(2,3)}],True),
 ('Esc-only accepts Esc',2,[{(0,0)}],True),('Esc-only ignores other key',2,[{(0,1)}],False),
 ('disabled ignores held key',0,[{(0,0)}],False)]
for mode in MODES:
 for name,policy,sequence,expected in policies:
  f=Fixture(mode,sequence);f.cycle_sequence=name=='different keys do not count as one hold'
  f.call('keyboard_init');actual=bool(f.call('nova_emergency_hold_detected',policy,3))
  assert actual==expected,(mode,name,actual)
  assert not f.writes and 'usb_init' not in f.events
  assert f.minsp>=f.symbols['__process_stack_base__']
  results.append(dict(build=mode,case=name,decision=actual,scans=f.scan+1,sample_reads=f.samples,
                      stack_used=f.symbols['__process_stack_end__']-f.minsp))
 for name,sequence,fail_matrix,fail_usb,expected in [
  ('main held key enters boot before USB',[{(0,0)}],False,False,['reset_requested']),
  ('main no key proceeds to USB',[set()],False,False,['usb_init']),
  ('matrix initialization failure requests boot',[set()],True,False,['reset_requested']),
  ('USB initialization failure requests boot',[set()],False,True,['usb_init','reset_requested']),
  ('clock calibration failure requests boot',[set()],False,False,['reset_requested']),
  ('unsupported clock requests boot',[set()],False,False,['reset_requested'])]:
  f=Fixture(mode,sequence);f.fail_matrix=fail_matrix;f.fail_usb=fail_usb;f.stop_usb=not fail_usb
  f.fail_calibration=name=='clock calibration failure requests boot'
  if name=='unsupported clock requests boot':f.clock_hz_override=24000000
  f.call('main');assert f.events==expected,(mode,name,f.events)
  if expected[-1]=='reset_requested':assert f.writes==[(0x4001400c,0x5ac396c5),(0xe000ed0c,0x05fa0004)]
  else:assert not f.writes
  results.append(dict(build=mode,case=name,events=f.events,reset_writes=[(hex(a),hex(v)) for a,v in f.writes],
                      failure_reason=struct.unpack('<I',f.u.mem_read(f.symbols['nova_runtime_failure'],4))[0]))
 for function,expected in [('mcu_reset',[(0xe000ed0c,0x05fa0004)]),
                           ('bootloader_jump',[(0x4001400c,0x5ac396c5),(0xe000ed0c,0x05fa0004)])]:
  f=Fixture(mode,[set()]);f.call(function);assert f.writes==expected
  results.append(dict(build=mode,case=function,reset_writes=[(hex(a),hex(v)) for a,v in f.writes]))

# Feed the emitted retained request to the ACTUAL original reset/main path.
boot=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
for a,n in [(0,0x20000),(0x20000000,0x4000),(0x40000000,0x20000),(0x10000000,0x1000)]:boot.mem_map(a,n)
original=(ROOT/'firmware_dump/flash_cpu_pass1.bin').read_bytes();boot.mem_write(0,original)
boot.mem_write(0x10000600,(ROOT/'firmware_dump/boot_safety_audit/metadata_10000600.bin').read_bytes())
boot.mem_write(0x4001400c,struct.pack('<I',0x5ac396c5));boot.reg_write(UC_ARM_REG_SP,0x20000bf0)
seen=[]
def bootcode(u,a,size,user):
 if a==0x9bc:u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
 if a==0x848:seen.append(a);u.emu_stop()
boot.hook_add(UC_HOOK_CODE,bootcode);boot.emu_start(0x1cd,0,count=100000)
assert seen==[0x848] and struct.unpack('<I',boot.mem_read(0x4001400c,4))[0]==0
results.append(dict(case='compiled boot request consumed by original bootloader',usb_boot_server_entry='0x848',request_cleared=True))
report=dict(passed=True,cases=results,case_count=len(results),completion_boundaries_checked=True,
 elf_sha256={mode:hashlib.sha256((ROOT/f'qmk_port/build/{mode}/nova_qmk_research.elf').read_bytes()).hexdigest() for mode in MODES},
 fixtures='Actual linked C/ARM acquisition/hold/reset and original boot code; modeled0/100 analog samples, captured factory word0x06a20060, ready-bit, no real delays. Failure paths injected at initialization boundary.',
 limitations='No physical key calibration, cold-power timing or SYSRESET retention hardware test. Captured factory word is replayed offline. Cannot recover before main/clock checks execute. Power removal does not preserve the request.')
Path(__file__).with_name('emergency_boot_neo2_rgb_validation.json' if args.rgb else 'emergency_boot_neo2_validation.json' if args.keymap=='neo2' else 'emergency_boot_diagnostic_validation.json' if args.diagnostic else 'emergency_boot_validation.json').write_text(json.dumps(report,indent=2))
print(f'PASS: {len(results)} emergency hold/reset/original-boot cases; no flash writes.')
