"""Execute actual linked QMK keyboard task, acquisition, debounce and reports offline."""
from pathlib import Path
import hashlib,json,struct,sys,argparse
parser=argparse.ArgumentParser();parser.add_argument('--diagnostic',action='store_true');args=parser.parse_args()
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.tools'))
from unicorn import *
from unicorn.arm_const import *

OUT=ROOT/('qmk_port/build/firmware_diagnostic' if args.diagnostic else 'qmk_port/build/firmware')
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

pressed=set();selected_bank=0;reports=[];sample_reads=0;delay_calls=0
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
def check(name,keys,mods,usages):
    report=settle(keys)
    assert report[0]==mods,(name,report.hex(),mods)
    assert set(report[2:])-{0}==set(usages),(name,report.hex(),usages)
    cases.append({'case':name,'pressed_positions':sorted(keys),'report_hex':report.hex(),'passed':True})
check('idle',[],0,[])
check('bank0_channel1_press',[(0,1)],0,[0x1e])
check('release',[],0,[])
check('left_shift_plus_1',[(3,0),(0,1)],2,[0x1e])
check('release_shift_keep_1',[(0,1)],0,[0x1e])
check('left_ctrl_left_shift_plus_1',[(4,0),(3,0),(0,1)],3,[0x1e])
check('two_keys_1_and_q',[(0,1),(1,1)],0,[0x1e,0x14])
check('all_released',[],0,[])
check('ff_function_selector_only',[(4,5)],0,[])
check('ff_plus_1_is_f1',[(4,5),(0,1)],0,[0x3a])
check('ff_selector_release_key',[(4,5)],0,[])
check('both_function_selectors',[(4,5),(4,6)],0,[])
check('both_selectors_ff_priority_f1',[(4,5),(4,6),(0,1)],0,[0x3a])
check('function_keys_released',[],0,[])
check('fe_function_selector_only',[(4,6)],0,[])
check('fe_plus_1_disabled_original_layer2',[(4,6),(0,1)],0,[])
check('final_release',[],0,[])
assert minimum_stack>=symbols['__process_stack_base__'],hex(minimum_stack)
result={'elf_sha256':hashlib.sha256(elf).hexdigest(),'actual_linked_qmk_pipeline':True,
        'cases':cases,'reports_observed':reports,'sample_reads':sample_reads,'delay_calls_intercepted':delay_calls,
        'minimum_process_stack':hex(minimum_stack),'process_stack_used_bytes':symbols['__process_stack_end__']-minimum_stack,
        'executed':'Real acquisition MMIO/addressing + custom matrix + QMK debounce + keyboard_task + action/layer/keymap + runtime host report callback',
        'fixtures':'ELF initialized data/bss loaded; analog result values supplied through mapped MMIO; synthetic millisecond timer; original delay calls bypassed; real runtime host driver installed without USB hardware initialization.',
        'limitations':'Does not test USB hardware, enumeration, physical sampling/timing, startup or device boot acceptance.'}
Path(__file__).with_name('qmk_pipeline_diagnostic_result.json' if args.diagnostic else 'qmk_pipeline_result.json').write_text(json.dumps(result,indent=2)+'\n')
print(f'PASS: {len(cases)} real QMK pipeline cases; {len(reports)} reports; {sample_reads} acquisition reads.')
