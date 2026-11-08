"""Execute actual linked QMK keyboard task, acquisition, debounce and reports offline."""
from pathlib import Path
import hashlib,json,struct,sys,argparse
parser=argparse.ArgumentParser();parser.add_argument('--via',action='store_true');parser.add_argument('--rgb',action='store_true');parser.add_argument('--nkro',action='store_true');args=parser.parse_args()
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.tools'))
from unicorn import *
from unicorn.arm_const import *

OUT=ROOT/'contributions/qmk_firmware/.build'
elf=(OUT/'ranked_nova_n60_neo2_via.elf').read_bytes()
assert elf[:5]==b'\x7fELF\x01'
symbols={};data_symbols={}
import subprocess
for line in subprocess.check_output([str(ROOT/'.build-tools/bin/arm-none-eabi-nm.exe'),'-n',str(OUT/'ranked_nova_n60_neo2_via.elf')],text=True).splitlines():
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
# Existing Neo2 expectations exercise boot-protocol compatibility explicitly.
invoke('usb_device_state_set_protocol',0)
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
    value=settle(keys)
    assert value[0]==mods and set(value[2:])-{0}==set(usages),(name,value.hex(),mods,usages)
    cases.append({'case':name,'pressed_positions':sorted(keys),'report_hex':value.hex(),'passed':True})
def release():check('release_cleanup',[],0,[])
check('idle',[],0,[])
for name,key,usage in [('physical_Q_to_X',(1,1),0x1b),('physical_A_to_U',(2,1),0x18),('physical_Z_to_udia',(3,2),0x2f),('Neo_Z_German_host_Y_usage',(3,6),0x1c),('Neo_Y_German_host_Z_usage',(5,7),0x1d)]:
    check(name,[key],0,[usage]);release()
check('Shift_plus_Neo_X',[(3,0),(1,1)],2,[0x1b]);release()
check('Ctrl_plus_Neo_C',[(4,0),(1,4)],1,[6]);release()
for mod in [(2,0),(5,8)]:
    settle([mod])
    check('Mod3_left_brace_'+str(mod),[mod,(2,3)],0x40,[0x24]);release()
    settle([mod])
    check('Mod3_right_brace_'+str(mod),[mod,(2,4)],0x40,[0x27]);release()
for mod in [(3,1),(4,4)]:
    for name,key,usage in [('left',(2,2),0x50),('down',(2,3),0x51),('right',(2,4),0x4f),('up',(1,3),0x52)]:
        settle([mod])
        check('Mod4_'+str(mod)+'_'+name,[mod,key],0,[usage]);release()
for index,key in enumerate([(0,n) for n in range(1,11)]+[(5,1),(5,2)]):
    settle([(4,5)])
    check('Fn1_F'+str(index+1),[(4,5),key],0,[0x3a+index]);release()
check('both_layers_held',[(2,0),(3,1)],0,[])
settle([(2,0)])
check('release_Mod4_keep_Mod3',[(2,0),(2,3)],0x40,[0x24]);release()
check('both_layers_again',[(2,0),(3,1)],0,[])
settle([(3,1)])
check('release_Mod3_keep_Mod4',[(3,1),(2,3)],0,[0x51]);release()
for name,first,second,key,mods,usage in [('dual_Mod3_release_first',(2,0),(5,8),(2,3),0x40,0x24),('dual_Mod4_release_first',(3,1),(4,4),(2,2),0,0x50)]:
    settle([]);settle([first]);settle([first,second]);settle([second])
    check(name,[second,key],mods,[usage]);release()
# Windows German rendering is inferred from HID aliases; no Windows UI is used.
targets={'DE_DEG':(2,0x35),'DE_SECT':(2,0x20),'DE_DLR':(2,0x21),'DE_EURO':(0x40,8)}
for override in json.loads((ROOT/'qmk_port/neo2/shift_overrides.json').read_text(encoding='utf-8'))['overrides']:
    key=(override['bank'],override['channel']);name='Shift_override_'+override['base_alias']
    settle([(3,0)]);start=len(reports);settle([(3,0),key])
    seen=[bytes.fromhex(r['report_hex']) for r in reports[start:]]
    if override['available']:
        mods,usage=targets[override['shift_target_alias']]
        assert any(r[0]==mods and usage in r[2:] for r in seen),(name,[r.hex() for r in seen])
    else:
        assert all(not any(r[2:]) for r in seen),(name,[r.hex() for r in seen])
    cases.append({'case':name,'reports':[r.hex() for r in seen],'passed':True});release()
for name,key,mods,usage in [('German_dead_circumflex',(1,5),0,0x35),('German_dead_grave',(3,6),2,0x2e)]:
    settle([(2,0)]);check(name,[(2,0),key],mods,[usage]);release()
    check(name+'_manual_Space',[(4,3)],0,[0x2c]);release()
if args.nkro:
    release()
    invoke('usb_device_state_set_protocol',1)
    invoke('host_can_send_nkro')
    assert u.reg_read(UC_ARM_REG_R0)==1
    positions=[(1,n) for n in range(1,11)]+[(2,n) for n in range(1,11)]
    usages=[]
    for position in positions:
        settle([position])
        value=bytes(u.mem_read(symbols['latest_nkro'],32))
        bits={n for n in range(240) if value[2+n//8] & (1<<(n%8))}
        assert len(bits)==1,(position,bits)
        usages.append(next(iter(bits)))
        settle([])
    assert len(set(usages))==20
    for count in [7,10,20]:
        settle(positions[:count])
        value=bytes(u.mem_read(symbols['latest_nkro'],32))
        bits={n for n in range(240) if value[2+n//8] & (1<<(n%8))}
        assert value[0]==6 and value[1]==0 and bits==set(usages[:count]),(count,value.hex())
        cases.append({'case':'NKRO_'+str(count)+'_simultaneous_keys','passed':True})
        settle([])
        assert not any(u.mem_read(symbols['latest_nkro']+1,31))
    settle([(3,0)]+positions[:10])
    value=bytes(u.mem_read(symbols['latest_nkro'],32))
    assert value[1]==2
    assert {n for n in range(240) if value[2+n//8] & (1<<(n%8))}==set(usages[:10])
    settle([])
    invoke('usb_device_state_set_protocol',0)
    invoke('host_can_send_nkro')
    assert u.reg_read(UC_ARM_REG_R0)==0
    check('boot_protocol_after_NKRO',[(1,1)],0,[0x1b]);release()
via_cases=[]
if args.via:
    PACKET=0x20001820
    def command(name,values):
        payload=bytes(values).ljust(32,b'\0');assert len(payload)==32
        u.mem_write(PACKET,payload);u.mem_write(symbols['raw_tx_pending'],b'\0')
        invoke('raw_hid_receive',PACKET,32)
        assert u.mem_read(symbols['raw_tx_pending'],1)==b'\1',name
        response=bytes(u.mem_read(symbols['raw_tx'],32))
        via_cases.append({'case':name,'request':payload.hex(),'response':response.hex(),'passed':True})
        return response
    assert command('protocol_13',[1])[1:3]==b'\0\x0d'
    assert command('layer_count_3',[0x11])[1]==3
    compiled=bytes(u.mem_read(symbols['keymaps'],396))
    expected=b''.join(compiled[n:n+2][::-1] for n in range(0,396,2))
    actual=b''.join(command('read_default_buffer_'+str(i),[0x12,i>>8,i&255,min(28,396-i)])[4:4+min(28,396-i)] for i in range(0,396,28))
    assert actual==expected,(actual.hex(),expected.hex())
    for layer in range(3):
        for row in range(6):
            for col in range(11):
                offset=((layer*6+row)*11+col)*2
                assert command('get_default_'+str((layer,row,col)),[4,layer,row,col])[4:6]==expected[offset:offset+2]
    assert expected[130:132]==b'\0\0' # layer0,row5,col10 unused physical slot.
    command('remap_unused_slot',[5,0,5,10,0,4])
    assert command('read_remapped_unused_slot',[4,0,5,10])[4:6]==b'\0\4'
    command('restore_unused_slot',[5,0,5,10,0,0])
    assert command('verify_restored_unused_slot',[4,0,5,10])[4:6]==b'\0\0'
assert not flash_writes,flash_writes
assert minimum_stack>=symbols['__process_stack_base__'],hex(minimum_stack)
result={'passed':True,'elf_sha256':hashlib.sha256(elf).hexdigest(),'candidate_keymap_sha256':hashlib.sha256((ROOT/'contributions/qmk_userspace/keyboards/ranked/nova_n60/keymaps/neo2_via/keymap.c').read_bytes()).hexdigest(),'cases':cases,'case_count':len(cases),'via_cases':via_cases,'via_case_count':len(via_cases),'minimum_process_stack':hex(minimum_stack),'acquisition_reads':sample_reads,'flash_writes':flash_writes,'fixtures':'Actual linked keyboard_init/task, analog MMIO samples100/0, debounce, QMK actions, runtime host reports. ELF data loaded directly; original delays bypassed; synthetic timer. VIA actual upstream handlers and transient EEPROM.','limitations':'No physical hardware, USB transfer, Windows rendering, timing or cold boot test. Neo2 core first four levels only; unsupported characters and layers5/6 excluded.'}
(ROOT/'contributions/neo2_validation.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS',len(cases),'keypipeline cases',len(via_cases),'VIA cases',result['elf_sha256'])


