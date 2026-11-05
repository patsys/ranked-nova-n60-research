"""Compare compiled ARM MMIO implementation against original machine code."""
from pathlib import Path
import json,struct,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.tools'))
from unicorn import *
from unicorn.arm_const import *
TOOLS=ROOT/'.build-tools/bin'; OUT=Path(__file__).resolve().parent/'validation_build'
OUT.mkdir(exist_ok=True)
def run(args): return subprocess.run([str(x) for x in args],cwd=ROOT,check=True,capture_output=True,text=True).stdout
flags=['-mcpu=cortex-m0','-mthumb','-std=c11','-Os','-g','-ffreestanding','-fno-builtin','-ffunction-sections','-fdata-sections','-Wall','-Wextra','-Werror']
elf=OUT/'scan_validation.elf';binary=OUT/'scan_validation.bin'
run([TOOLS/'arm-none-eabi-gcc.exe',*flags,'-nostdlib','-Wl,-Ttext=0x18000,-Tdata=0x20005000,-e,nova_test_scan,--gc-sections,-u,nova_test_init',
     *[ROOT/'qmk_port/scan'/x for x in ('recovered_scan.c','nova_acquisition.c','validation_harness.c')],'-lgcc','-o',elf])
run([TOOLS/'arm-none-eabi-objcopy.exe','-O','binary',elf,binary])
symbols={}
for line in run([TOOLS/'arm-none-eabi-nm.exe','-n',elf]).splitlines():
    fields=line.split()
    if len(fields)==3: symbols[fields[2]]=int(fields[0],16)
flash=(ROOT/'firmware_dump/flash_cpu_pass1.bin').read_bytes()
ram=(ROOT/'firmware_dump/startup_ram_20000000.bin').read_bytes()
tables=json.loads((ROOT/'firmware_dump/key_scan_tables.json').read_text())
def emulate(compiled,operation,sample,initial):
    u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
    u.mem_map(0,0x40000);u.mem_write(0,flash)
    if compiled:u.mem_write(0x18000,binary.read_bytes())
    u.mem_map(0x20000000,0x10000);u.mem_write(0x20000000,ram)
    u.mem_map(0x40000000,0x20000)
    for channel in range(11):
        u.mem_write(0x4000e09c+4*channel,struct.pack('<I',sample))
        u.mem_write(0x20000bae+2*channel,struct.pack('<H',initial))
    if compiled:u.mem_write(symbols['nova_test_initial_bits'],struct.pack('<I',initial))
    trace=[]
    def mem(uc,access,address,size,value,data):
        if access==UC_MEM_WRITE:trace.append(['write',address,value])
        else:trace.append(['read',address,int.from_bytes(uc.mem_read(address,size),'little')])
    u.hook_add(UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,mem,begin=0x40000000,end=0x4001ffff)
    delay_address=symbols['nova_test_delay'] if compiled else 0xdde8
    def code(uc,address,size,data):
        if address==delay_address:
            trace.append(['delay',uc.reg_read(UC_ARM_REG_R0)])
            uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,code)
    def invoke(address):
        u.reg_write(UC_ARM_REG_SP,0x2000f000);u.reg_write(UC_ARM_REG_LR,0x17f01)
        u.emu_start(address|1,0x17f00,count=100000)
        assert u.reg_read(UC_ARM_REG_PC)==0x17f00
    if operation=='init':
        if compiled:invoke(symbols['nova_test_init'])
        else:invoke(0x4470);invoke(0x31b4)
    else:invoke(symbols['nova_test_scan'] if compiled else 0x4cb0)
    if operation=='scan':
        offset=symbols['nova_test_state']+148 if compiled else 0x20000bae
        bits=list(struct.unpack('<11H',u.mem_read(offset,22)))
        if compiled:
            rows=list(struct.unpack('<6H',u.mem_read(symbols['nova_test_rows'],12)))
            expected=[sum(1<<c for c,row in enumerate(tables['logical_key_ids_by_channel_then_bank']) if row[b]!=1 and bits[c]&(1<<b)) for b in range(6)]
            assert rows==expected
    else:bits=[]
    return trace,bits
cases=[]
native,_=emulate(False,'init',0,0);compiled,_=emulate(True,'init',0,0)
assert compiled==native,('init trace mismatch',compiled,native)
cases.append({'operation':'init','trace_operations':len(native),'passed':True})
for sample in (0,19,20,25,30,31,65535):
    for initial in (0,63):
        original=emulate(False,'scan',sample,initial);compiled=emulate(True,'scan',sample,initial)
        assert compiled==original,(sample,initial,compiled,original)
        cases.append({'operation':'scan','sample':sample,'initial':initial,'trace_operations':len(original[0]),'passed':True})
report={'compiled_arm_matches_original_mmio_and_delays':True,'cases':cases,
        'matrix_rows_checked':True,'limitations':'Offline MMIO storage, original delay calls intercepted; hardware timing and USB not validated.'}
(OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS: ARM compiled init and 14 acquisition scans match original MMIO/delay traces and bank bits; row conversion checked.')
