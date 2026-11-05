"""Execute actual linked QMK keyboard task, acquisition, debounce and reports offline."""
from pathlib import Path
import hashlib,json,struct,sys,argparse
parser=argparse.ArgumentParser();parser.add_argument('--via',action='store_true');args=parser.parse_args()
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.tools'))
from unicorn import *
from unicorn.arm_const import *

OUT=ROOT/('qmk_port/build/firmware_via_diagnostic_neo2' if args.via else 'qmk_port/build/firmware_diagnostic_neo2')
elf=(OUT/'nova_qmk_research.elf').read_bytes()
assert elf[:5]==b'\x7fELF\x01'
symbols={};data_symbols={}
for line in (OUT/'nova_qmk_research.nm').read_text().splitlines():
    p=line.split()
    if len(p)==3:
        symbols[p[2]]=int(p[0],16)
        if p[1]=='d':data_symbols[p[2]]=int(p[0],16)
u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
u.mem_map(0,0x20000);u.mem_map(0x20000000,0x10000)
u.mem_map(0x40000000,0x20000);u.mem_map(0xe000e000,0x2000)
phoff=struct.unpack_from('<I',elf,28)[0]
phsize,phnum=struct.unpack_from('<HH',elf,42)
for i in range(phnum):
    typ,offset,vaddr,paddr,filesize,memsize,flags,align=struct.unpack_from('<8I',elf,phoff+i*phsize)
    if typ==1 and filesize:u.mem_write(vaddr,elf[offset:offset+filesize])

pressed=set();selected_bank=0;reports=[];sample_reads=0;delay_calls=0;flash_writes=[]
u.hook_add(UC_HOOK_MEM_WRITE,lambda uc,access,address,size,value,data:flash_writes.append([address,size,value]),begin=0,end=0x1ffff)
minimum_stack=symbols['__process_stack_end__']
bank_pins=[24,23,22,21,20,19]
def memory(uc,access,address,size,value,data):
    global selected_bank,sample_reads
    if access==UC_MEM_WRITE and address==0x40018010:
        for bank,pin in enumerate(bank_pins):
            if value==1<<pin:selected_bank=bank
    if access==UC_MEM_READ and 0x4000e09c<=address<=0x4000e0c4 and (address-0x4000e09c)%4==0:
        channel=(address-0x4000e09c)//4
        sample=100 if (selected_bank,channel) in pressed else 0
        uc.mem_write(address,struct.pack('<I',sample));sample_reads+=1
u.hook_add(UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,memory,begin=0x40000000,end=0x4001ffff)
def code(uc,address,size,data):
    global delay_calls,minimum_stack
    minimum_stack=min(minimum_stack,uc.reg_read(UC_ARM_REG_SP))
    if address==symbols['nova_platform_delay_original_units']:
        delay_calls+=1;uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    if address==symbols['nova_platform_delay_original_long']:
        # Startup settling is checked separately against the native call order.
        # This fixture models key/report behavior rather than elapsed time.
        uc.reg_write(UC_ARM_REG_R0,1);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    if address==symbols.get('wait_ms'):
        ticks=struct.unpack('<I',uc.mem_read(symbols['timer_count'],4))[0]
        uc.mem_write(symbols['timer_count'],struct.pack('<I',ticks+uc.reg_read(UC_ARM_REG_R0)))
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    if address==symbols['send_keyboard']:
        ptr=uc.reg_read(UC_ARM_REG_R0)
        reports.append({'time_ms':struct.unpack('<I',uc.mem_read(symbols['timer_count'],4))[0],
                        'report_hex':bytes(uc.mem_read(ptr,8)).hex()})
u.hook_add(UC_HOOK_CODE,code)
def invoke(name,*args):
    for register,arg in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(register,arg)
    u.reg_write(UC_ARM_REG_SP,symbols['__process_stack_end__']);u.reg_write(UC_ARM_REG_LR,0x1ff01)
    u.emu_start(symbols[name]|1,0x1ff00,count=300000)
    assert u.reg_read(UC_ARM_REG_PC)==0x1ff00,(name,hex(u.reg_read(UC_ARM_REG_PC)))

# Data/bss initialization above is an ELF loader fixture. Startup is independently
# tested by the platform tests. QMK initialization itself executes unmodified.
invoke('keyboard_init')
assert u.mem_read(symbols['nova_matrix_initialization_failed'],1)==b'\x00'
# Use the real runtime host driver and real send_keyboard RAM callback. No QMK
# action/report/debounce/matrix function is replaced. USB enumeration is out of scope.
invoke('host_set_driver',data_symbols['driver'])
if args.via:
    u.mem_write(0x40014120,struct.pack('<I',1))
    assert invoke('nova_usb_keyboard_init') is None
invoke('usb_device_state_set_configuration',1,1)
now=0
def settle(keys):
    global pressed,now
    pressed=set(keys)
    for _ in range(12):
        now+=1;u.mem_write(symbols['timer_count'],struct.pack('<I',now))
        invoke('keyboard_task')
    return bytes(u.mem_read(symbols['latest_report'],8))

cases=[]
for name,first,second,key,mods,usage in [('dual_Mod3',(2,0),(5,8),(2,3),0x40,0x24),('dual_Mod4',(3,1),(4,4),(2,2),0,0x50)]:
    settle([]);settle([first]);settle([first,second]);settle([second]);value=settle([second,key])
    passed=value[0]==mods and set(value[2:])-{0}=={usage}
    cases.append({'case':name,'report_hex':value.hex(),'expected_modifiers':mods,'expected_usage':usage,'passed':passed})
    settle([])
result={'passed':all(c['passed'] for c in cases),'elf_sha256':hashlib.sha256(elf).hexdigest(),'cases':cases}
Path(__file__).with_name('dual_modifiers_via_validation.json' if args.via else 'dual_modifiers_basic_validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))

