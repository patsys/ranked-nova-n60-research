"""Build and execute real ChibiOS startup offline; never access the keyboard."""
from pathlib import Path
import json, subprocess, struct, sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'.tools'))
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_SP, UC_ARM_REG_PC, UC_ARM_REG_CONTROL
P = ROOT/'qmk_port/platform'
OUT = ROOT/'qmk_port/build/startup'
OUT.mkdir(parents=True, exist_ok=True)
BIN = ROOT/'.build-tools/bin'
CRT = ROOT/'qmk_source/lib/chibios/os/common/startup/ARMCMx/compilers/GCC'
def run(args):
    return subprocess.run([str(x) for x in args],cwd=ROOT,check=True,capture_output=True,text=True).stdout
flags=['-mcpu=cortex-m0','-mthumb','-Os','-g','-ffreestanding','-fno-common',
       '-ffunction-sections','-fdata-sections','-I',P,'-DCRT0_VTOR_INIT=FALSE',
       '-DCRT0_INIT_VECTORS=FALSE','-DCRT0_AREAS_NUMBER=1']
objects=[]
for src in [CRT/'crt0_v6m.S',CRT/'vectors.S',CRT/'crt1.c',P/'startup_validation_main.c']:
    obj=OUT/(src.stem+'.o')
    run([BIN/'arm-none-eabi-gcc.exe',*flags,'-c',src,'-o',obj]);objects.append(obj)
elf=OUT/'startup_validation.elf'
run([BIN/'arm-none-eabi-gcc.exe',*flags,'-nostdlib','-Wl,--gc-sections',
     '-Wl,--defsym=__main_stack_size__=0x200,--defsym=__process_stack_size__=0x400',
     '-Wl,-L'+str(CRT/'ld'),'-T',P/'NOVA_RESEARCH.ld',*objects,'-o',elf])
run([BIN/'arm-none-eabi-objcopy.exe','-O','binary',elf,OUT/'startup_validation.bin'])
syms={}
for line in run([BIN/'arm-none-eabi-nm.exe','-n',elf]).splitlines():
    parts=line.split()
    if len(parts)==3:syms[parts[2]]=int(parts[0],16)
image=(OUT/'startup_validation.bin').read_bytes()
vectors=struct.unpack('<40I',image[:160])
assert syms['_vectors']==0x2000 and vectors[1]&1
u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
u.mem_map(0,0x20000);u.mem_map(0x20000000,0x4000)
u.mem_write(0x2000,image);u.mem_write(0x20000000,b'\xa5'*0x4000)
u.reg_write(UC_ARM_REG_SP,0x20001c50)
writes=[];reached=[]
def code(uc,address,size,user):
    if address==syms['main']:
        reached.append(address);uc.emu_stop()
def write(uc,access,address,size,value,user):
    assert 0x20000000<=address and address+size<=0x20001c50,hex(address)
    writes.append((address,size))
u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_WRITE,write)
u.emu_start(vectors[1],0,count=20000)
assert reached,hex(u.reg_read(UC_ARM_REG_PC))
assert bytes(u.mem_read(syms['nova_test_initialized'],4))==struct.pack('<I',0x12345678)
assert bytes(u.mem_read(syms['nova_test_zero'],28))==bytes(28)
assert u.reg_read(UC_ARM_REG_CONTROL)==2
result=dict(kind='real upstream ChibiOS generic ARMv6-M startup validation, not QMK firmware',
            vectors_address=hex(syms['_vectors']),reset=hex(vectors[1]),
            initial_msp=hex(vectors[0]),runtime_stack=hex(u.reg_read(UC_ARM_REG_SP)),
            reached_main=True,data_initialized=True,bss_zeroed=True,
            control_psp_privileged=True,ram_writes=len(writes),
            ram_write_min=hex(min(a for a,s in writes)),
            ram_write_max_exclusive=hex(max(a+s for a,s in writes)),
            vtor_access=False,flash_window=['0x2000','0x1a000'],
            ram_allocation_window=['0x20000000','0x20001c50'],
            caveat='RAM window conservative original-used range, not total RAM; stack sizes are research budgets. No hardware test.')
(OUT/'validation.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
