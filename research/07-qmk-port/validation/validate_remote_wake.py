"""Actual linked suspend scanning and remote wake, with modeled ADC/USB/timer."""
import hashlib
import json
import struct
from pathlib import Path
import validate_rgb_via as model
from unicorn import UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_MEM_READ, UC_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_R0

u, s, call, read32 = model.u, model.s, model.call, model.read32
p = s['__heap_base__'] + 32
pressed = set()
selected = 0
reads = 0
pins = [24,23,22,21,20,19]
def adc(uc, access, address, size, value, context):
    global selected, reads
    if access == UC_MEM_WRITE and address == 0x40018010:
        for bank, pin in enumerate(pins):
            if value == 1 << pin: selected = bank
    if access == UC_MEM_READ and 0x4000e09c <= address <= 0x4000e0c4 and (address-0x4000e09c)%4 == 0:
        channel = (address-0x4000e09c)//4
        uc.mem_write(address,struct.pack('<I',100 if (selected,channel) in pressed else 0))
        reads += 1
u.hook_add(UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,adc,begin=0x40000000,end=0x4001ffff)
assert bytes(u.mem_read(s['configuration']+7,1)) == b'\xa0'
u.mem_write(0x40014120,struct.pack('<I',1))
call('nova_usb_keyboard_init');assert u.reg_read(UC_ARM_REG_R0)==1
def clock(value):u.mem_write(s['timer_count'],struct.pack('<I',value))
def event(number, setup=None):
    if setup:
        for i, byte in enumerate(setup):u.mem_write(0x40017fa0+4*i,struct.pack('<I',byte))
    u.mem_write(0x40016000,struct.pack('<I',number))
    u.mem_write(0x40016008,struct.pack('<I',1))
    call('Vector50')
def request(type,number,value,index,length):event(0,struct.pack('<BBHHH',type,number,value,index,length))
clock(5000)
event(4);request(0,9,1,0,0);call('nova_usb_keyboard_pre_task')
event(1);event(3);call('nova_usb_keyboard_pre_task')
before=reads;clock(5020);call('nova_usb_keyboard_suspend_task')
assert reads==before
event(1);call('nova_usb_keyboard_pre_task')
request(0,3,1,0,0) # SET_FEATURE DEVICE_REMOTE_WAKEUP
request(0x80,0,0,0,2) # GET_STATUS exposes host-controlled permission
assert read32(0x40017c00)&255==2
clock(5100);event(1);event(3);call('nova_usb_keyboard_pre_task')
clock(5110);call('nova_usb_keyboard_suspend_task');assert reads==before
clock(5120);call('nova_usb_keyboard_suspend_task');assert reads>before
assert read32(0x40017f58)&3==0
pressed={(1,1)}
model.mmio.clear()
for t in [5140,5160,5180]:
    clock(t);call('nova_usb_keyboard_suspend_task')
pulse=[value for address,value in model.mmio if address=='0x40017f58']
assert pulse==[2,1,0],pulse
call('nova_usb_keyboard_suspended');assert u.reg_read(UC_ARM_REG_R0)==1
before=reads;clock(5200);call('nova_usb_keyboard_suspend_task');assert reads==before
event(1);call('nova_usb_keyboard_pre_task')
call('nova_usb_keyboard_suspended');assert u.reg_read(UC_ARM_REG_R0)==0
for t in range(5210,5222):clock(t);call('keyboard_task')
assert not any(u.mem_read(s['latest_nkro']+1,31)), 'wake key must not type after resume'
pressed=set()
for t in range(5230,5242):clock(t);call('keyboard_task')
pressed={(1,1)}
for t in range(5250,5262):clock(t);call('keyboard_task')
value=bytes(u.mem_read(s['latest_nkro'],32))
assert value[2+0x1b//8] & (1<<(0x1b%8))
pressed=set()
for t in range(5270,5282):clock(t);call('keyboard_task')
assert not any(u.mem_read(s['latest_nkro']+1,31))
request(0,1,1,0,0) # CLEAR_FEATURE
request(0x80,0,0,0,2)
assert read32(0x40017c00)&255==0
result=dict(passed=True,elf_sha256=hashlib.sha256(model.elf).hexdigest(),
    cases=['remote-wakeup capability advertised',
           'host permission controls GET_STATUS and scanning',
           'scans throttled to20ms; unchanged keys do not signal',
           'keypress sends one native-style prepare/pulse/release sequence',
           'software remains suspended until real host bus activity',
           'wake key suppressed until released; next press types normally',
           'CLEAR_FEATURE revokes wake permission'],
    hardware_tested=False,limitation='Synthetic bus/ADC/timer. Electrical pulse duration, Windows policy and physical wake remain unverified.')
(Path(__file__).parent/'remote_wake_validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
