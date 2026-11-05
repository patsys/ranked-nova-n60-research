"""Linked NKRO USB descriptors, control requests and endpoint transport model."""
import hashlib
import json
import struct
from pathlib import Path
import validate_rgb_via as model
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

u, s, call, read32 = model.u, model.s, model.call, model.read32
from unicorn import UC_HOOK_MEM_WRITE
def require_enabled_endpoint(uc, access, address, size, value, context):
    if 0x40017400 <= address < 0x40017480:
        assert read32(0x40017eb0) & 0x10, 'NKRO IN endpoint4 interrupt gate is disabled'
        assert read32(0x40017f78) & 0x10, 'NKRO endpoint4 is disabled after USB reset'
u.hook_add(UC_HOOK_MEM_WRITE, require_enabled_endpoint, begin=0x40017400, end=0x4001747f)
p = s['__heap_base__'] + 32
assert p + 128 < s['__heap_end__']
cases = []

def descriptor(kind, interface=0):
    for reg, value in [(UC_ARM_REG_R0, 0)]:
        u.reg_write(reg, value)
    from unicorn.arm_const import UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3
    for reg, value in [(UC_ARM_REG_R1, kind), (UC_ARM_REG_R2, 0), (UC_ARM_REG_R3, interface)]:
        u.reg_write(reg, value)
    stack = s['__process_stack_end__'] - 8
    u.mem_write(stack, struct.pack('<I', p))
    u.reg_write(UC_ARM_REG_SP, stack)
    u.reg_write(UC_ARM_REG_LR, 0x1ff01)
    u.emu_start(s['descriptor'] | 1, 0x1ff00, count=100000)
    assert u.reg_read(UC_ARM_REG_PC) == 0x1ff00
    length = int.from_bytes(u.mem_read(p, 2), 'little')
    return bytes(u.mem_read(u.reg_read(UC_ARM_REG_R0), length))

config = descriptor(2)
assert len(config) == 91 and int.from_bytes(config[2:4], 'little') == 91
assert config[4] == 3
assert config[-25:-16] == bytes([9,4,2,0,1,3,0,0,0])
assert config[-7:] == bytes([7,5,0x84,3,32,0,1])
nkro_descriptor = descriptor(0x22,2)
assert bytes([0x85,6]) in nkro_descriptor
assert bytes([0x95,240,0x75,1,0x81,2]) in nkro_descriptor
assert descriptor(0x21,2)[7] == len(nkro_descriptor)
assert descriptor(0x22,0) != nkro_descriptor
cases.append('three distinct interfaces; boot keyboard and 32-byte NKRO endpoint4')

def control(request_type, request, value, interface, length, accepted=True):
    u.mem_write(p, struct.pack('<BBHHH', request_type, request, value, interface, length))
    u.mem_write(p+16, bytes(16))
    call('control',0,p,p+16)
    assert bool(u.reg_read(UC_ARM_REG_R0)) == accepted
    return p+16

reply=control(0xa1,1,0x0106,2,32)
assert int.from_bytes(u.mem_read(reply+4,2),'little') == 32
control(0x21,0x0a,(5<<8)|6,2,0)
reply=control(0xa1,2,6,2,1)
assert bytes(u.mem_read(read32(reply),1)) == b'\5'
control(0x21,0x0a,7,2,0,False)
control(0x21,0x0b,0,2,0,False)
control(0xa1,3,0,2,1,False)
reply=control(0x21,9,0x0206,2,2)
assert int.from_bytes(u.mem_read(reply+12,2),'little') == 2
u.mem_write(p+64,bytes([6,2]))
call('control_complete',0,p,p+64,2)
call('leds');assert u.reg_read(UC_ARM_REG_R0)==2
cases.append('NKRO GET_REPORT, idle, LED output; invalid IDs and boot-only protocol rejected')

# Initialize the actual runtime controller using synthetic ready registers.
u.mem_write(0x40014120,struct.pack('<I',1))
call('nova_usb_keyboard_init')
assert u.reg_read(UC_ARM_REG_R0)==1
def event(number, setup=None):
    if setup is not None:
        for i, byte in enumerate(setup):
            u.mem_write(0x40017fa0+4*i,struct.pack('<I',byte))
    u.mem_write(0x40016000,struct.pack('<I',number))
    u.mem_write(0x40016008,struct.pack('<I',1))
    call('Vector50')
event(4)  # A real host bus reset must precede configuration.
event(0,struct.pack('<BBHHH',0,9,1,0,0))
call('nova_usb_keyboard_pre_task')
report=bytes([6,2])+bytes([0xff])*30
u.mem_write(p+64,report)
call('send_nkro',p+64)
call('nova_usb_keyboard_task')
fifo=lambda:bytes(read32(0x40017400+4*i)&255 for i in range(32))
assert fifo()==report
assert read32(0x40017ef4)&127==32
cases.append('all 32 NKRO bytes submitted to endpoint4 FIFO')
empty=bytes([6])+bytes(31)
u.mem_write(p+64,empty)
call('send_nkro',p+64)
call('nova_usb_keyboard_task')
assert fifo()==report
event(14)  # endpoint4 IN complete
call('nova_usb_keyboard_task')
assert fifo()==empty
cases.append('busy endpoint retains pending report; completion submits release')
u.mem_write(p+64,report)
call('send_nkro',p+64)
control(0x21,0x0b,0,0,0)
call('nova_usb_keyboard_pre_task')
call('host_can_send_nkro');assert u.reg_read(UC_ARM_REG_R0)==0
assert not any(u.mem_read(s['latest_nkro']+1,31))
assert not any(u.mem_read(s['latest_report'],8))
control(0x21,0x0b,1,0,0)
call('nova_usb_keyboard_pre_task')
call('host_can_send_nkro');assert u.reg_read(UC_ARM_REG_R0)==1
cases.append('boot-interface SET_PROTOCOL clears old keys and selects six-key fallback/report mode')
result=dict(passed=True,cases=cases,case_count=len(cases),hardware_tested=False,
    elf_sha256=hashlib.sha256(model.elf).hexdigest(),
    limitation='Modeled MMIO, IRQs and host requests; physical Windows enumeration and rollover remain pending.')
(Path(__file__).parent/'nkro_usb_validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
