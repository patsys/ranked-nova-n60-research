"""Test actual linked upstream VIA handler and remapped QMK key reports offline."""
from pathlib import Path
import hashlib,json,struct,sys,argparse
parser=argparse.ArgumentParser();parser.add_argument('--diagnostic',action='store_true');args=parser.parse_args()
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.tools'))
from unicorn import *
from unicorn.arm_const import *

OUT=ROOT/('qmk_port/build/firmware_via_diagnostic' if args.diagnostic else 'qmk_port/build/firmware_via')
elf=(OUT/'nova_qmk_research.elf').read_bytes()
symbols={}
for line in (OUT/'nova_qmk_research.nm').read_text().splitlines():
    p=line.split()
    if len(p)==3:symbols[p[2]]=int(p[0],16)
for name in ('raw_hid_receive','raw_hid_send','dynamic_keymap_get_keycode','via_command_kb'):
    assert name in symbols,name
u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
u.mem_map(0,0x20000);u.mem_map(0x20000000,0x4000)
u.mem_map(0x40000000,0x20000);u.mem_map(0xe000e000,0x2000)
phoff=struct.unpack_from('<I',elf,28)[0];phsize,phnum=struct.unpack_from('<HH',elf,42)
for i in range(phnum):
    typ,offset,vaddr,paddr,size,memsize,flags,align=struct.unpack_from('<8I',elf,phoff+i*phsize)
    if typ==1 and size:u.mem_write(vaddr,elf[offset:offset+size])
u.mem_write(0x40014120,struct.pack('<I',1))
pressed=set();selected_bank=0;sample_reads=0;minimum_stack=symbols['__process_stack_end__'];raw_sends=0;flash_writes=[]
def memory(uc,access,address,size,value,data):
    global selected_bank,sample_reads
    if access==UC_MEM_WRITE and address<0x20000:flash_writes.append([address,size,value])
    if access==UC_MEM_WRITE and address==0x40018010:
        for bank,pin in enumerate((24,23,22,21,20,19)):
            if value==1<<pin:selected_bank=bank
    if access==UC_MEM_READ and 0x4000e09c<=address<=0x4000e0c4 and (address-0x4000e09c)%4==0:
        channel=(address-0x4000e09c)//4
        uc.mem_write(address,struct.pack('<I',100 if (selected_bank,channel) in pressed else 0));sample_reads+=1
u.hook_add(UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,memory)
def code(uc,address,size,data):
    global minimum_stack,raw_sends
    minimum_stack=min(minimum_stack,uc.reg_read(UC_ARM_REG_SP))
    if address in (symbols['nova_platform_delay_original_units'],symbols['nova_platform_delay_original_long']):
        uc.reg_write(UC_ARM_REG_R0,1);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    if address==symbols['send_raw']:raw_sends+=1
u.hook_add(UC_HOOK_CODE,code)
def invoke(name,*args):
    for register,arg in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(register,arg)
    u.reg_write(UC_ARM_REG_SP,symbols['__process_stack_end__']);u.reg_write(UC_ARM_REG_LR,0x1ff01)
    u.emu_start(symbols[name]|1,0x1ff00,count=1000000)
    assert u.reg_read(UC_ARM_REG_PC)==0x1ff00,(name,hex(u.reg_read(UC_ARM_REG_PC)))
    return u.reg_read(UC_ARM_REG_R0)

invoke('keyboard_init')
assert invoke('nova_usb_keyboard_init')==1
invoke('usb_device_state_set_configuration',1,1)
cases=[];PACKET=0x20001820;now=0
def command(name,values,length=32,response=True):
    payload=bytes(values).ljust(32,b'\x00')
    assert len(payload)==32
    u.mem_write(PACKET-32,b'\xa5'*32+payload+b'\x5a'*32)
    u.mem_write(symbols['raw_tx_pending'],b'\x00') # Fixture: previous response consumed by host.
    before=raw_sends
    invoke('raw_hid_receive',PACKET,length)
    assert bytes(u.mem_read(PACKET-32,32))==b'\xa5'*32
    assert bytes(u.mem_read(PACKET+32,32))==b'\x5a'*32
    pending=u.mem_read(symbols['raw_tx_pending'],1)[0]
    if response:
        assert pending and raw_sends==before+1,(name,pending,raw_sends,before)
        result=bytes(u.mem_read(symbols['raw_tx'],32))
    else:
        assert not pending and raw_sends==before
        result=b''
    cases.append({'case':name,'request':payload.hex(),'response':result.hex(),'passed':True})
    return result
def getkey(layer,row,col):return int.from_bytes(command(f'get_key_{layer}_{row}_{col}',[4,layer,row,col])[4:6],'big')
def readbuf(offset,size=28):return command(f'get_buffer_{offset}_{size}',[0x12,offset>>8,offset&255,size])[4:4+size]
def dumpmap():return b''.join(readbuf(i,min(28,396-i)) for i in range(0,396,28))
def report(keys):
    global pressed,now
    pressed=set(keys)
    for _ in range(12):
        now+=1;u.mem_write(symbols['timer_count'],struct.pack('<I',now));invoke('keyboard_task')
    return bytes(u.mem_read(symbols['latest_report'],8))
def check_report(name,keys,usage):
    value=report(keys)
    assert value[0]==0 and set(value[2:])-{0}==set(usage),(name,value.hex(),usage)
    cases.append({'case':name,'report_hex':value.hex(),'passed':True})

assert command('protocol_version',[1])[1:3]==b'\x00\x0d'
assert command('layer_count',[0x11])[1]==3
assert getkey(0,0,1)==0x1e
command('set_key_to_A',[5,0,0,1,0,4]);assert getkey(0,0,1)==4
check_report('VIA_remap_changes_real_report_to_A',[(0,1)],[4]);check_report('release_A',[],[])
command('reset_keymap',[6]);assert getkey(0,0,1)==0x1e
check_report('reset_restores_real_report_to_1',[(0,1)],[0x1e]);check_report('release_1',[],[])
original=dumpmap();assert original[:6]==bytes.fromhex('0029001e001f')
for layer,row,col in ((3,0,0),(0,6,0),(0,0,11),(255,255,255)):
    assert getkey(layer,row,col)==0
    command('invalid_key_set_ignored',[5,layer,row,col,0,4])
assert dumpmap()==original
for offset in (394,396,65535):
    actual=readbuf(offset)
    assert actual==(original[offset:offset+28]).ljust(28,b'\x00')
command('set_buffer_to_B',[0x13,0,2,2,0,5]);assert getkey(0,0,1)==5
check_report('VIA_buffer_remap_changes_report_to_B',[(0,1)],[5]);check_report('release_B',[],[])
command('reset_after_buffer_remap',[6]);assert dumpmap()==original
command('set_buffer_crosses_keymap_end',[0x13,1,138,28,*([0,6]+[0x7f]*26)])
changed=dumpmap();assert changed[:-2]==original[:-2] and changed[-2:]==b'\x00\x06'
command('set_buffer_fully_out_of_range',[0x13,0xff,0xff,28,*([0x7f]*28)])
assert dumpmap()==changed
command('reset_after_boundary_write',[6]);assert dumpmap()==original
for cmd in (0x0e,0x0f,0x12,0x13):
    for size in (29,255):
        assert command(f'oversized_buffer_rejected_{cmd}_{size}',[cmd,0,0,size])[0]==0xff
for length in (0,1,31):command(f'short_packet_rejected_{length}',[1],length=length,response=False)
assert command('unknown_command',[0x7f])[0]==0xff
assert dumpmap()==original
assert not flash_writes
assert minimum_stack>=symbols['__process_stack_base__'],hex(minimum_stack)
result={'elf_sha256':hashlib.sha256(elf).hexdigest(),'upstream_via_protocol':13,'cases':cases,
        'case_count':len(cases),'raw_responses_enqueued':raw_sends,'acquisition_reads':sample_reads,
        'flash_writes':flash_writes,'minimum_process_stack':hex(minimum_stack),
        'process_stack_used_bytes':symbols['__process_stack_end__']-minimum_stack,
        'actual_runtime':'Actual linked upstream raw_hid_receive/VIA/dynamic_keymap/NVM plus actual host raw callback and QMK keyboard task/acquisition/report path.',
        'fixtures':'ELF initialized data/bss loader; original delays intercepted; USB clock-ready bit and analog sample MMIO modeled; synthetic millisecond timer; consumed raw-response flag between requests.',
        'limitations':'No physical USB enumeration/endpoint transfer, sensor timing, persistence or hardware boot tested. EEPROM is RAM transient.'}
Path(__file__).with_name('via_protocol_diagnostic_result.json' if args.diagnostic else 'via_protocol_result.json').write_text(json.dumps(result,indent=2)+'\n')
print(f'PASS: {len(cases)} VIA/keypipeline cases; {raw_sends} actual raw responses; no flash writes.')
