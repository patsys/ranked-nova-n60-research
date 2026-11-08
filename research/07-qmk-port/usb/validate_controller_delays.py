"""Check actual runtime USB callback wiring against native long-delay semantics.
Builds isolated test objects/ELFs only; never rebuilds firmware targets or usesUSB.
"""
from pathlib import Path
import subprocess,sys,json,hashlib
ROOT=Path(__file__).resolve().parents[2];P=ROOT/'qmk_port';Q=ROOT/'qmk_source'
OUT=P/'usb/delay_validation';OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'.tools'))
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_CODE
from unicorn.arm_const import *
TOOLS=ROOT/'.build-tools/bin'
def run(args):return subprocess.run([str(x) for x in args],check=True,cwd=ROOT,capture_output=True,text=True).stdout
includes=[Q/'platforms',P/'platform',Q/'quantum',Q/'quantum/keymap_extras',Q/'quantum/logging',Q/'quantum/process_keycode',Q/'quantum/nvm',Q/'quantum/nvm/eeprom',Q/'tmk_core/protocol',Q/'tmk_core/common',Q/'lib/printf/src',P/'keyboard',P/'keyboard/keymaps/default',Q/'quantum/debounce',Q/'quantum/sequencer',Q/'drivers/eeprom',P/'runtime',P/'usb',P/'scan',Q/'quantum/send_string']
flags=['-mcpu=cortex-m0','-mthumb','-std=gnu11','-Os','-ffreestanding','-ffunction-sections','-fdata-sections','-Wall','-Wextra','-Werror','-include',P/'keyboard/config.h','-DQMK_KEYBOARD_H="research_keyboard.h"','-DKEYMAP_C="keymap.c"','-DNO_PRINT','-DNO_DEBUG','-DNVM_DRIVER_EEPROM','-DEEPROM_DRIVER="transient"','-DEEPROM_TRANSIENT','-DTRANSIENT_EEPROM_SIZE=1024','-DNO_ACTION_ONESHOT','-DNO_ACTION_TAPPING','-DNO_USB_STARTUP_CHECK']
for inc in includes:flags+=['-I',inc]
source=P/'runtime/usb_keyboard.c';text=source.read_text()
assert '.delay_original_units=delay_controller_long' in text
assert 'nova_original_gate_write(0x80000000u, true, nova_platform_delay_original_units)' in text
for filename in ('original_delay.c','original_delay_loop.S'):
    run([TOOLS/'arm-none-eabi-gcc.exe',*flags,'-c',P/'platform'/filename,'-o',OUT/(filename+'.o')])
def compile_callback(name,path,via=False):
    obj=OUT/(name+'.o');glob=OUT/(name+'_global.o');elf=OUT/(name+'.elf');binary=OUT/(name+'.bin')
    run([TOOLS/'arm-none-eabi-gcc.exe',*flags,*(['-DVIA_ENABLE','-DDYNAMIC_KEYMAP_ENABLE','-DRAW_ENABLE','-DDYNAMIC_KEYMAP_LAYER_COUNT=3','-DRAW_EPSIZE=32'] if via else []),'-c',path,'-o',obj])
    relocations=run([TOOLS/'arm-none-eabi-objdump.exe','-r',obj])
    # Actual compiled initializer must contain the callback relocation, rather
    # than validating a separately invented wrapper with the right delay.
    section=relocations.split('RELOCATION RECORDS FOR [.text.nova_usb_keyboard_init]:')[1].split('\n\n')[0]
    assert 'delay_controller_long' in section,section
    run([TOOLS/'arm-none-eabi-objcopy.exe','--globalize-symbol=delay_controller_long',obj,glob])
    run([TOOLS/'arm-none-eabi-gcc.exe','-mcpu=cortex-m0','-mthumb','-nostdlib','-Wl,--gc-sections,-e,delay_controller_long,-Ttext=0x20000000',glob,OUT/'original_delay.c.o',OUT/'original_delay_loop.S.o','-o',elf])
    run([TOOLS/'arm-none-eabi-objcopy.exe','-O','binary',elf,binary])
    symbols={}
    for line in run([TOOLS/'arm-none-eabi-nm.exe','-n',elf]).splitlines():
        fields=line.split()
        if len(fields)==3:symbols[fields[2]]=int(fields[0],16)
    return binary.read_bytes(),symbols,section
def compiled_trace(code,syms,n):
    u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);u.mem_map(0,0x20000);u.mem_map(0x20000000,0x10000);u.mem_write(0x20000000,code)
    calls=[]
    def hook(u,a,s,_):
        if a==syms['nova_delay48_loop']:
            calls.append(u.reg_read(UC_ARM_REG_R0));u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,hook);u.reg_write(UC_ARM_REG_SP,0x2000f000);u.reg_write(UC_ARM_REG_LR,0x1ff01);u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_R1,n)
    u.emu_start(syms['delay_controller_long']|1,0x1ff00,count=10000);assert u.reg_read(UC_ARM_REG_PC)==0x1ff00
    return calls
flash=(ROOT/'firmware_dump/flash_cpu_pass1.bin').read_bytes();ram=(ROOT/'firmware_dump/startup_ram_20000000.bin').read_bytes()
u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
for a,n in [(0,0x20000),(0x20000000,0x10000),(0x40000000,0x20000),(0xe000e000,0x2000)]:u.mem_map(a,n)
u.mem_write(0,flash);u.mem_write(0x20000000,ram);u.mem_write(0x20000510,(0x20001418).to_bytes(4,'little'))
native_args=[];native_loop_calls=[]
def native_hook(u,a,s,_):
    if a==0xf0dc:u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    elif a==0xdd80:native_args.append(u.reg_read(UC_ARM_REG_R0))
    elif a==0x21c8:
        native_loop_calls.append(u.reg_read(UC_ARM_REG_R0));u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,native_hook);u.reg_write(UC_ARM_REG_SP,0x2000f000);u.reg_write(UC_ARM_REG_LR,0x1ff01)
u.emu_start(0x46fd,0x1ff00,count=10000);assert u.reg_read(UC_ARM_REG_PC)==0x1ff00
assert native_args==[1,1,6]
cases=[]
for via in (False,True):
    code,syms,reloc=compile_callback('via' if via else 'basic',source,via)
    loops=[]
    for n in native_args:loops.extend(compiled_trace(code,syms,n))
    assert loops==native_loop_calls,(loops,native_loop_calls)
    boundary=[]
    for n in (0,1,6,10):
        got=compiled_trace(code,syms,n);expected=[] if n==0 else [n<<7]+[999]*n
        assert got==expected;boundary.append({'argument':n,'loop_arguments':got})
    cases.append({'via':via,'compiled_callback_matches_native_init':True,'loop_arguments':loops,'compiled_initializer_relocation':reloc.strip(),'boundary_cases':boundary})
# Negative control: reproduce the old callback body and require the semantic
# comparison to detect its much shorter delays.
old=OUT/'old_wiring.c';old.write_text(text.replace('(void)nova_platform_delay_original_long(value);','nova_platform_delay_original_units(value);'))
code,syms,_=compile_callback('old_wiring',old,True)
wrong=[]
for n in native_args:wrong.extend(compiled_trace(code,syms,n))
assert wrong==[1,1,6] and wrong!=native_loop_calls
result={'passed':True,'source':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'native_init_long_helper_arguments':native_args,'native_raw_loop_arguments':native_loop_calls,'cases':cases,'old_wiring_negative_control':{'loop_arguments':wrong,'mismatch_detected':True},'clock_gate_short_delay_wiring_preserved':True,'hardware_access':False,'method':'Actualnative46fc/longdd80wrappers andactualcompiledruntimecallback;rawlooponlybypassedtocaptureloopcounts.Initclockenablef0dcskipped,MMIOstorage-backed.Confirmscallsemantics,nothardwaretimingorenumeration.'}
(OUT/'validation.json').write_text(json.dumps(result,indent=2))
print('PASS basic+VIA actualcallback/initrelocations matchnative long1/1/6 delaysemantics; oldshortwiringnegativecontrolfailsasexpected')
