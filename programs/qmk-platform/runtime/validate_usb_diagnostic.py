"""Actual diagnostic ELF deadline/fault/stack/boot-retention checks, offline."""
from pathlib import Path
import sys,struct,json,hashlib,argparse
parser=argparse.ArgumentParser();parser.add_argument('--keymap',choices=['default','neo2'],default='default');parser.add_argument('--rgb',action='store_true');args=parser.parse_args()
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'.tools'))
from unicorn import *
from unicorn.arm_const import *
TRACE=0x20003000;SIZE=256;MAGIC=0x4e554442;VERSION=2;cases=[]
class Model:
 def __init__(self,mode):
  folder=ROOT/f'qmk_port/build/{mode}';self.elf=(folder/'nova_qmk_research.elf').read_bytes()
  self.hash=hashlib.sha256(self.elf).hexdigest()
  self.s={p[2]:int(p[0],16) for line in (folder/'nova_qmk_research.nm').read_text().splitlines() if len(p:=line.split())==3}
  self.u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
  for a,n in [(0,0x20000),(0x20000000,0x4000),(0x40000000,0x20000),(0xe000e000,0x2000),(0x10000000,0x1000)]:self.u.mem_map(a,n)
  self.u.mem_write(0,(ROOT/'firmware_dump/flash_cpu_pass1.bin').read_bytes())
  h=struct.unpack_from('<16sHHIIIIIHHHHHH',self.elf)
  for i in range(h[10]):
   typ,offset,vaddr,paddr,size,memsz,flags,align=struct.unpack_from('<8I',self.elf,h[5]+i*h[9])
   if typ==1 and size:self.u.mem_write(vaddr,self.elf[offset:offset+size]);self.u.mem_write(paddr,self.elf[offset:offset+size])
  self.u.mem_write(0x40014120,struct.pack('<I',1))
  self.reset=[];self.writes=[];self.retention=False;self.native_writes=[];self.minsp=0xffffffff;self.fault_stack_writes=[]
  self.in_fault_stack=False;self.fault_sp_min=0xffffffff
  self.u.hook_add(UC_HOOK_CODE,self.code);self.u.hook_add(UC_HOOK_MEM_WRITE,self.write)
 def code(self,u,a,size,user):
  self.minsp=min(self.minsp,u.reg_read(UC_ARM_REG_SP))
  if a==self.s['nova_usb_diagnostic_fault']:self.in_fault_stack=True
  if self.in_fault_stack:self.fault_sp_min=min(self.fault_sp_min,u.reg_read(UC_ARM_REG_SP))
  if a in (self.s['nova_platform_delay_original_units'],self.s['nova_platform_delay_original_long']):
   u.reg_write(UC_ARM_REG_R0,1);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
 def write(self,u,access,a,size,value,user):
  assert a>=0x20000,('CPU flash write',hex(a))
  assert not 0x40013000<=a<0x40014000,('flash controller write',hex(a))
  self.writes.append((a,size,value))
  if self.retention:self.native_writes.append((a,size,value))
  if 0x20003100<=a<0x200031b4:self.fault_stack_writes.append((a,size))
  if a==0xe000ed0c:
   self.reset.append(value);u.emu_stop()
 def call(self,name,*args,sp=0x20000600,ipsr=0):
  u=self.u;u.reg_write(UC_ARM_REG_CONTROL,0);u.reg_write(UC_ARM_REG_IPSR,ipsr)
  u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,0x1ff01)
  for reg,arg in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2),args):u.reg_write(reg,arg)
  u.emu_start(self.s[name]|1,0x1ff00,count=1000000)
  return u.reg_read(UC_ARM_REG_R0)
 def words(self):return struct.unpack('<64I',self.u.mem_read(TRACE,SIZE))
 def init(self):self.call('nova_usb_diagnostic_init');assert self.words()[:3]==(MAGIC,VERSION,256)
 def setword(self,index,value):self.u.mem_write(TRACE+index*4,struct.pack('<I',value))
 def retention_check(self):
  saved=bytes(self.u.mem_read(TRACE,256));self.retention=True;self.native_writes=[]
  self.u.mem_write(0x10000600,(ROOT/'firmware_dump/boot_safety_audit/metadata_10000600.bin').read_bytes())
  self.u.mem_write(0xe000e010,struct.pack('<I',4));self.u.mem_write(0xe000e100,bytes(4))
  self.u.reg_write(UC_ARM_REG_CONTROL,0);self.u.reg_write(UC_ARM_REG_IPSR,0);self.u.reg_write(UC_ARM_REG_PRIMASK,0)
  self.u.reg_write(UC_ARM_REG_SP,0x20000bf0);seen=[]
  def native(u,a,size,user):
   if a==0x9bc:u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
   if a==0x11ae:
    # Host configuration completion is an explicit fixture, not USB proof.
    u.mem_write(0x2000024c,struct.pack('<I',1));u.mem_write(0x2000023e,b'\x04')
   if a==0xbdc:seen.append(a);u.emu_stop()
  handle=self.u.hook_add(UC_HOOK_CODE,native)
  self.u.emu_start(0x1cd,0,count=200000);self.u.hook_del(handle)
  assert seen==[0xbdc] and bytes(self.u.mem_read(TRACE,256))==saved
  assert not any(a<TRACE+256 and a+n>TRACE for a,n,v in self.native_writes)
  return dict(original_boot_reached='0xbdc',trace_unchanged=True,native_writes=len(self.native_writes),
              fixture='Core reset registers modeled; actual reset/scatter/main/USB init executes; host-config phase injected at11ae')

hashes={};fault_min=0xffffffff;largest_main_stack=0
for mode in tuple(x+('_neo2' if args.keymap=='neo2' else '')+('_rgb' if args.rgb else '') for x in ('firmware_diagnostic','firmware_via_diagnostic')):
 m=Model(mode);hashes[mode]=m.hash;m.init();m.call('nova_usb_diagnostic_mark',7);m.call('nova_usb_diagnostic_arm')
 # One full5000-tick path for each image. Repeated configuration0 and IRQ
 # entries simulate a reset/IRQ storm without giving it a fresh deadline.
 for tick in range(1,5000):
  m.call('nova_usb_diagnostic_irq',1);m.call('nova_usb_diagnostic_event',4)
  m.call('nova_usb_diagnostic_configured',0);m.call('SysTick_Handler',sp=0x20000200,ipsr=15)
  assert not m.reset
 m.call('SysTick_Handler',sp=0x20000200,ipsr=15)
 w=m.words();assert m.reset==[0x05fa0004] and w[6]==5000 and w[48]==1 and w[49]==0 and w[50]==15 and w[63]==7
 assert struct.unpack('<I',m.u.mem_read(0x4001400c,4))[0]==0x5ac396c5
 retention=m.retention_check()
 cases.append(dict(build=mode,case='full5000ticks repeatedUSBreset0 never renews deadline',passed=True,retention=retention))

 m=Model(mode);m.init();m.call('nova_usb_diagnostic_arm');m.call('nova_usb_diagnostic_configured',1)
 m.setword(6,4999);m.call('SysTick_Handler',sp=0x20000200,ipsr=15)
 assert not m.reset and m.words()[6]==5000 and m.words()[7]==1
 m.call('nova_usb_diagnostic_configured',0);m.call('SysTick_Handler',sp=0x20000200,ipsr=15)
 assert m.reset==[0x05fa0004] and m.words()[6]==5001
 cases.append(dict(build=mode,case='configured deadline allowed; later configuration loss returns boot',passed=True))

 m=Model(mode);m.init();m.u.mem_write(0xe000ed20,struct.pack('<I',0x80a5b6c7));m.u.mem_write(0xe000e404,struct.pack('<I',0x12345678))
 m.call('timer_init');assert struct.unpack('<I',m.u.mem_read(0xe000ed20,4))[0]==0x00a5b6c7
 assert m.call('nova_usb_keyboard_init')==1
 assert struct.unpack('<I',m.u.mem_read(0xe000e404,4))[0]==0x12345640
 assert struct.unpack('<I',m.u.mem_read(0xe000ed20,4))[0]==0x00a5b6c7
 cases.append(dict(build=mode,case='SysTickpriority0 aboveUSBpriority1; neighboringbytespreserved',passed=True))

 m=Model(mode);m.init();m.call('nova_usb_diagnostic_shared_startup',0x12345678)
 m.call('nova_usb_diagnostic_aux',0x80);m.call('nova_usb_diagnostic_aux',0x81)
 for event in (29,30,31,32,0xffffffff):m.call('nova_usb_diagnostic_event',event)
 m.call('nova_usb_diagnostic_event',4)
 assert m.words()[45:48]==(0x12345678,2,0x81) and m.words()[20]==1
 cases.append(dict(build=mode,case='V2 reserves sharedstatus/AUX slots against event overwrites',passed=True))

 m=Model(mode);m.init();m.call('nova_usb_diagnostic_arm');m.setword(6,4999)
 m.minsp=0xffffffff;m.call('SysTick_Handler',sp=0x20000100,ipsr=15)
 assert m.reset and m.minsp>=0x20000000
 used=0x20000200-m.minsp;largest_main_stack=max(largest_main_stack,used)
 cases.append(dict(build=mode,case='deadline with256B preexistingUSB/exceptionstack budget',passed=True,minimum_sp=hex(m.minsp),total_stack_used=used))

 for handler,number,exc,frameptr in [
  ('HardFault_Handler',3,0xfffffffd,0x200005c0),('HardFault_Handler',3,0xfffffff9,0x200001c0),
  ('NMI_Handler',2,0xfffffffd,0x200005c0),('HardFault_Handler',3,0xfffffffd,0x40000000),
  ('NMI_Handler',2,0xfffffff9,0x20003180),('HardFault_Handler',3,0xfffffffd,0x20003000)]:
  m=Model(mode);m.init();m.call('nova_usb_diagnostic_mark',3)
  expected=tuple(0x10001000+i for i in range(8))
  if frameptr!=0x40000000:m.u.mem_write(frameptr,struct.pack('<8I',*expected))
  if exc&4:m.u.reg_write(UC_ARM_REG_PSP,frameptr);m.u.reg_write(UC_ARM_REG_MSP,0x200001e0)
  else:m.u.reg_write(UC_ARM_REG_MSP,frameptr)
  m.u.reg_write(UC_ARM_REG_CONTROL,0);m.u.reg_write(UC_ARM_REG_IPSR,number);m.u.reg_write(UC_ARM_REG_LR,exc)
  m.u.emu_start(m.s[handler]|1,0,count=100000)
  w=m.words();assert m.reset==[0x05fa0004] and w[48]==(3 if number==2 else 2) and w[51:54]==(number,exc,frameptr)
  trustworthy=frameptr not in (0x40000000,0x20003180)
  assert w[54:62]==(expected if trustworthy else (0xffffffff,)*8)
  assert m.fault_stack_writes and min(a for a,n in m.fault_stack_writes)>=0x20003100
  # Include all actual C call-chain writes below the selected emergency MSP.
  upper=[a for a,n,v in m.writes if 0x20003100<=a<0x200031b0]
  minimum=min(min(upper),m.fault_sp_min);fault_min=min(fault_min,minimum)
  assert m.fault_sp_min>=0x20003100,hex(m.fault_sp_min)
  assert 0x200031b0-minimum<=176
  cases.append(dict(build=mode,case=handler+' '+hex(exc)+' frame'+hex(frameptr),passed=True,
                    minimum_fault_stack=hex(minimum),fault_stack_used=0x200031b0-minimum,frame_trustworthy=trustworthy))

report=dict(passed=True,elf_sha256=hashes,case_count=len(cases),cases=cases,deadline_ticks=5000,trace_version=VERSION,
 absolute_deadline_not_reset_by_USB=True,bounded_timeout=True,sysTick_priority=0,usb_priority=1,
 trace_address=hex(TRACE),trace_bytes=256,trace_retained_by_original_boot_code=True,
 faultstack_minSP=hex(fault_min),faultstack_top='0x200031b0',faultstack_lower_bound='0x20003100',
 faultstack_max_used=0x200031b0-fault_min,max_main_stack_model_used=largest_main_stack,
 noflashwrites=True,hardware_access=False,
 limits=['Synthetic ticks/exception IPSR entries; actual physical preemption/timing not emulated',
         'Failed exception stacking, unreadable code/vector or broken clocks can defeat this software guard',
         'Original boot writes tested not to clear trace; silicon SRAM retention across reset remains to be observed physically',
         'Native boot configuration completion injected; no physical USB recovery guarantee'])
(ROOT/('qmk_port/runtime/usb_diagnostic_neo2_rgb_validation.json' if args.rgb else 'qmk_port/runtime/usb_diagnostic_neo2_validation.json' if args.keymap=='neo2' else 'qmk_port/runtime/usb_diagnostic_validation.json')).write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k!='cases'},indent=2))
