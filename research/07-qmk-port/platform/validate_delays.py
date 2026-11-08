"""Verify selected delay bytes and original wrapper calls, offline only."""
from pathlib import Path
import sys,json,subprocess
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.tools'))
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_R0,UC_ARM_REG_PC
b=(ROOT/'firmware_dump/flash_cpu_pass1.bin').read_bytes()
ram=(ROOT/'firmware_dump/startup_ram_20000000.bin').read_bytes()
out=ROOT/'qmk_port/build/delays';out.mkdir(parents=True,exist_ok=True)
tools=ROOT/'.build-tools/bin'
obj=out/'loop.o';raw=out/'loop.bin'
subprocess.run([str(tools/'arm-none-eabi-gcc.exe'),'-mcpu=cortex-m0','-mthumb','-c',str(ROOT/'qmk_port/platform/original_delay_loop.S'),'-o',str(obj)],check=True)
subprocess.run([str(tools/'arm-none-eabi-objcopy.exe'),'-O','binary',str(obj),str(raw)],check=True)
assert raw.read_bytes()==b[0x21c8:0x2200]
cases=[]
for entry in [0xdde8,0xdd80]:
    for n in [0,1,2,10]:
        u=Uc(UC_ARCH_ARM,UC_MODE_THUMB);u.mem_map(0,0x20000);u.mem_write(0,b)
        u.mem_map(0x20000000,0x10000);u.mem_write(0x20000000,ram)
        u.reg_write(UC_ARM_REG_SP,0x20002000);u.reg_write(UC_ARM_REG_LR,0x1ff01);u.reg_write(UC_ARM_REG_R0,n)
        calls=[];stopped=[]
        def code(uc,a,s,d):
            if a==0x1ff00:stopped.append(True);uc.emu_stop()
            if a==0x21c8:
                calls.append(uc.reg_read(UC_ARM_REG_R0));uc.reg_write(UC_ARM_REG_R0,0)
                uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
        u.hook_add(UC_HOOK_CODE,code);u.emu_start(entry|1,0,count=10000)
        expected=[] if not n else ([n] if entry==0xdde8 else [n<<7]+[999]*n)
        assert stopped and calls==expected,(entry,n,calls)
        cases.append(dict(entry=hex(entry),argument=n,selected_loop_arguments=calls))
report=dict(assembly_byte_exact=True,original_wrapper_cases=cases,
            limitation='Selected loop bypassed while tracing wrapper arguments; byte identity does not establish hardware duration')
(out/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('Delay loop byte-exact;8 original wrapper call traces passed')
