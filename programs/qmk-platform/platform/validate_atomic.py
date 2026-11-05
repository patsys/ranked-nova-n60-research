"""Execute compiled platform atomic sections, including early scope exits."""
from pathlib import Path
import subprocess,sys,json,struct
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'.tools'))
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS
from unicorn.arm_const import UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PRIMASK
P=ROOT/'qmk_port/platform';OUT=ROOT/'qmk_port/build/atomic';OUT.mkdir(parents=True,exist_ok=True)
BIN=ROOT/'.build-tools/bin'
def run(args):return subprocess.run([str(x) for x in args],check=True,capture_output=True,text=True).stdout
elf=OUT/'atomic_validation.elf'
run([BIN/'arm-none-eabi-gcc.exe','-mcpu=cortex-m0','-mthumb','-Os','-ffreestanding','-nostdlib',
     '-I',P,P/'atomic_validation.c','-Wl,-Ttext=0x1000,-Tdata=0x20000000,-e,nova_atomic_normal','-o',elf])
run([BIN/'arm-none-eabi-objcopy.exe','-O','binary','-j','.text',elf,OUT/'text.bin'])
symbols={line.split()[2]:int(line.split()[0],16) for line in run([BIN/'arm-none-eabi-nm.exe','-n',elf]).splitlines() if len(line.split())==3}
cases=[]
for name in ['normal','break','return','nested']:
 for previous in [0,1]:
    u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);u.mem_map(0,0x10000);u.mem_map(0x20000000,0x4000)
    u.mem_write(0x1000,(OUT/'text.bin').read_bytes());u.reg_write(UC_ARM_REG_SP,0x20003000)
    u.reg_write(UC_ARM_REG_LR,0x8001);u.reg_write(UC_ARM_REG_PRIMASK,previous)
    u.emu_start(symbols['nova_atomic_'+name]|1,0x8000,count=1000)
    after=u.reg_read(UC_ARM_REG_PRIMASK)
    inside=struct.unpack('<I',u.mem_read(symbols['nova_atomic_inside'],4))[0]
    assert after==previous and inside==(3 if name=='nested' else 1),(name,previous,after,inside)
    cases.append(dict(case=name,initial_primask=previous,inside=inside,restored_primask=after))
(OUT/'validation.json').write_text(json.dumps(dict(passed=True,cases=cases),indent=2))
print(f'PASS: {len(cases)} compiled atomic-section cases')
