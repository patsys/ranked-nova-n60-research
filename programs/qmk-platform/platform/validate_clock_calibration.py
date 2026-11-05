"""Compare compiled EA20(4,0) transcription with actual original instructions.

Only hardware callbacks/delays are modeled; trim values are read from fixed
factory memory in both runs. No target firmware rebuild or device access.
"""
from pathlib import Path
import json,subprocess,struct,sys,hashlib
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'.tools'))
from unicorn import *
from unicorn.arm_const import *
P=ROOT/'qmk_port/platform';OUT=ROOT/'qmk_port/build/clock_calibration_validation';OUT.mkdir(parents=True,exist_ok=True)
BIN=ROOT/'.build-tools/bin'
def run(args):return subprocess.run([str(x) for x in args],check=True,capture_output=True,text=True).stdout
elfpath=OUT/'clock_calibration_validation.elf'
run([BIN/'arm-none-eabi-gcc.exe','-mcpu=cortex-m0','-mthumb','-std=c11','-Os','-g','-ffreestanding',
 '-Wall','-Wextra','-Werror','-nostdlib',P/'recovered_clock.c',
 '-Wl,-Ttext=0x18000,-Tdata=0x20003000,-e,nova_original_clock_calibrate_4_0','-o',elfpath])
elf=elfpath.read_bytes();header=struct.unpack_from('<16sHHIIIIIHHHHHH',elf)
symbols={p[2]:int(p[0],16) for line in run([BIN/'arm-none-eabi-nm.exe','-n',elfpath]).splitlines() if len(p:=line.split())==3}
flash=(ROOT/'firmware_dump/flash_cpu_pass1.bin').read_bytes()
initialized=(ROOT/'firmware_dump/startup_ram_20000000.bin').read_bytes()
watched={0x10000234,0x4001900c,0x40019010,0x40014018,0xe000ed20,0xe000e400,0xe000e404}
def execute(compiled,factory_values,seed,units_callback=True,long_callback=True,long_success=True):
 u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
 for a,n in [(0,0x20000),(0x20000000,0x10000),(0x40000000,0x20000),(0x10000000,0x1000),(0xe000e000,0x2000)]:u.mem_map(a,n)
 u.mem_write(0,flash);u.mem_write(0x20000000,initialized)
 if compiled:
  for i in range(header[10]):
   kind,offset,vaddr,paddr,size,memsz,flags,align=struct.unpack_from('<8I',elf,header[5]+i*header[9])
   if kind==1 and size:u.mem_write(vaddr,elf[offset:offset+size])
  state=symbols['nova_clock_state']
 else:state=0x20000428
 for address in watched-{0x10000234}:u.mem_write(address,struct.pack('<I',seed))
 u.mem_write(0x1fe00,b'\x70\x47');u.mem_write(0x1fe04,b'\x01\x20\x70\x47' if long_success else b'\x00\x20\x70\x47')
 u.reg_write(UC_ARM_REG_SP,0x20008000);u.reg_write(UC_ARM_REG_LR,0x1ff01)
 u.reg_write(UC_ARM_REG_R0,(0x1fe01 if units_callback else 0) if compiled else 4)
 u.reg_write(UC_ARM_REG_R1,(0x1fe05 if long_callback else 0) if compiled else 0)
 events=[];factory_reads=[]
 def memory(uc,access,a,size,value,user):
  if access==UC_MEM_READ and a==0x10000234:
   v=factory_values[min(len(factory_reads),len(factory_values)-1)];factory_reads.append(v);uc.mem_write(a,struct.pack('<I',v))
  if a in watched:
   val=value if access==UC_MEM_WRITE else int.from_bytes(uc.mem_read(a,size),'little')
   events.append(dict(kind='write' if access==UC_MEM_WRITE else 'read',address=hex(a),bytes=size,value=hex(val)))
  elif access==UC_MEM_WRITE and state<=a<state+16:
   events.append(dict(kind='bookkeeping',offset=hex(a-state),bytes=size,value=hex(value)))
 def code(uc,a,size,user):
  if a in ((0x1fe00,0x1fe04) if compiled else (0xdde8,0xdd80)):
   events.append(dict(kind='delay_units' if a in (0x1fe00,0xdde8) else 'delay_long',argument=uc.reg_read(UC_ARM_REG_R0)))
   if not compiled:uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,memory);u.hook_add(UC_HOOK_CODE,code)
 u.emu_start((symbols['nova_original_clock_calibrate_4_0'] if compiled else 0xea20)|1,0x1ff00,count=100000)
 assert u.reg_read(UC_ARM_REG_PC)==0x1ff00
 result=dict(events=events,factory_reads=[hex(x) for x in factory_reads],
             state=list(struct.unpack('<4I',u.mem_read(state,16))),return_value=u.reg_read(UC_ARM_REG_R0))
 return result
fixtures=[]
for value in [i<<4 for i in range(8)]+[0xffffffff,0,0x06a20060,0xdab37f60]:
 for seed in [0,0xffffffff,0xa55a1234]:fixtures.append(([value],seed))
fixtures.append(([0x10,0x12ab0020,0x0d340030,0x06a20060],0x98765432))
cases=[]
for values,seed in fixtures:
 original=execute(False,values,seed);compiled=execute(True,values,seed)
 assert original['events']==compiled['events'],json.dumps(dict(values=values,native=original,compiled=compiled),indent=2)
 assert original['state']==compiled['state'] and compiled['factory_reads']==original['factory_reads']
 expected=24000000+4000000*((values[-1]>>4)&7)
 assert compiled['state']==[expected,expected,0x2000,0x2000] and compiled['return_value']==1
 cases.append(dict(factory_values=[hex(v) for v in values],seed=hex(seed),effective_hz=expected,
  exact_ordered_events_match=True,events=compiled['events'],native_and_compiled_bookkeeping=compiled['state']))
for units,long in [(False,True),(True,False),(False,False)]:
 result=execute(True,[0x06a20060],0,units,long)
 assert not result['events'] and result['return_value']==0
result=execute(True,[0x06a20060],0,True,True,False)
assert result['return_value']==0 and not any(e.get('address') in ('0x40014018','0xe000ed20','0xe000e400','0xe000e404') and e['kind']=='write' for e in result['events'])
report=dict(passed=True,equivalent_cases=len(cases),callback_failure_cases=4,
 source_sha256=hashlib.sha256((P/'recovered_clock.c').read_bytes()).hexdigest(),
 actual_captured_word_included='0x06a20060',factory_address='0x10000234',
 cases=cases,hardware_access=False,
 scope='OriginalEA20(4,0)+EAB4+F3A8+2BA8 and compiledC; ordered factory/MMIO reads+writes, delay-call arguments, relocated bookkeeping compared.',
 limits='Factory/MMIO modeled asRAM; originaldelay functions bypassed. Does not prove oscillator/PLL settling, frequency, hardwaretrim side effects, cold USB enumeration or recovery. No full target rebuild.')
(OUT/'validation.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k!='cases'},indent=2))
