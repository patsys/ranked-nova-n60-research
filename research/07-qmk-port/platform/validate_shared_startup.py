"""Original APP4A9C/BOOT5D0 enable path vs compiled C, offline only."""
from pathlib import Path
import sys,struct,json,subprocess,hashlib
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'.tools'))
from unicorn import *
from unicorn.arm_const import *
P=ROOT/'qmk_port/platform';OUT=ROOT/'qmk_port/build/shared_startup_validation';OUT.mkdir(parents=True,exist_ok=True)
BIN=ROOT/'.build-tools/bin'
def run(args):return subprocess.run([str(a) for a in args],check=True,text=True,capture_output=True).stdout
elfpath=OUT/'shared_startup_validation.elf'
run([BIN/'arm-none-eabi-gcc.exe','-mcpu=cortex-m0','-mthumb','-std=c11','-Os','-g','-ffreestanding','-Wall','-Wextra','-Werror','-nostdlib',
 P/'recovered_clock.c','-Wl,-Ttext=0x18000,-Tdata=0x20003000,-e,nova_original_shared_startup_enable','-o',elfpath])
elf=elfpath.read_bytes();head=struct.unpack_from('<16sHHIIIIIHHHHHH',elf)
syms={p[2]:int(p[0],16) for line in run([BIN/'arm-none-eabi-nm.exe','-n',elfpath]).splitlines() if len(p:=line.split())==3}
flash=(ROOT/'firmware_dump/flash_cpu_pass1.bin').read_bytes()
def model(kind,statuses):
 u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
 for a,n in [(0,0x20000),(0x20000000,0x10000),(0x40000000,0x20000)]:u.mem_map(a,n)
 u.mem_write(0,flash)
 ram=(ROOT/('firmware_dump/boot_initial_ram.bin' if kind=='boot' else 'firmware_dump/startup_ram_20000000.bin')).read_bytes()
 u.mem_write(0x20000000,ram)
 if kind=='compiled':
  for i in range(head[10]):
   typ,offset,vaddr,paddr,size,memsz,flags,align=struct.unpack_from('<8I',elf,head[5]+i*head[9])
   if typ==1 and size:u.mem_write(vaddr,elf[offset:offset+size])
 u.mem_write(0x1fe00,b'\x70\x47');u.mem_write(0x1fe04,b'\x01\x20\x70\x47')
 u.reg_write(UC_ARM_REG_SP,0x20008000);u.reg_write(UC_ARM_REG_LR,0x1ff01)
 u.reg_write(UC_ARM_REG_R0,0x1fe01 if kind=='compiled' else 0xffffffff)
 u.reg_write(UC_ARM_REG_R1,0x1fe05 if kind=='compiled' else 0)
 events=[];read_count=0
 def code(uc,a,size,user):
  if a in (0xdde8,0xdd80,0xa14,0x9bc,0x1fe00,0x1fe04):
   events.append(dict(kind='short_delay' if a in (0xdde8,0xa14,0x1fe00) else 'long_delay',argument=uc.reg_read(UC_ARM_REG_R0)))
   if a not in (0x1fe00,0x1fe04):uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 def memory(uc,access,a,size,value,user):
  nonlocal read_count
  if access==UC_MEM_READ and a==0x40015038:
   value=statuses[min(read_count,len(statuses)-1)];read_count+=1;uc.mem_write(a,struct.pack('<I',value))
   events.append(dict(kind='read',address=hex(a),bytes=size,value=hex(value)))
  if access==UC_MEM_WRITE and 0x40000000<=a<0x40020000:
   events.append(dict(kind='write',address=hex(a),bytes=size,value=hex(value)))
   assert a in (0x4001402c,0x40015000)
 u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,memory)
 entry={'app':0x4a9c,'boot':0x5d0,'compiled':syms['nova_original_shared_startup_enable']}[kind]
 u.emu_start(entry|1,0x1ff00,count=100000)
 assert u.reg_read(UC_ARM_REG_PC)==0x1ff00
 return dict(events=events,status_reads=read_count,returned_status=u.reg_read(UC_ARM_REG_R0))
cases=[]
for name,statuses in [('ready_immediate',[1]),('ready_second',[0,0x80]),('ready_last_allowed',[0]*100+[0x1234]),
                      ('timeout_all_zero',[0]*101),('ready_beyond_bound_not_observed',[0]*101+[1]),('arbitrary_ready_bits',[0xdeadbeef])]:
 values={kind:model(kind,statuses) for kind in ('app','boot','compiled')}
 assert values['app']==values['boot']==values['compiled'],json.dumps(values,indent=2)
 assert values['compiled']['status_reads']<=101
 cases.append(dict(case=name,matched_all_three=True,**values['compiled']))
report=dict(passed=True,cases=cases,case_count=len(cases),max_status_reads=101,
 source_sha256=hashlib.sha256((P/'recovered_clock.c').read_bytes()).hexdigest(),
 native_entries=dict(app='0x4a9c',boot='0x5d0'),
 preserves_original_zero_status_caller_behavior=True,hardware_access=False,
 scope='Exact ordered peripheral reads/writes and short10/long10 arguments; APP/BOOT originals and compiled C run, delays modeled.',
 limitations='Does not identify peripheral role, emulate completion semantics or establish physical USB improvement. No periodic feed requirement inferred.')
(OUT/'validation.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k!='cases'},indent=2))
