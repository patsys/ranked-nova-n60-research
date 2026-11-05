"""Offline original lighting transport/packet observations; no device access."""
from pathlib import Path
import sys, struct, json
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.tools'))
from unicorn import *
from unicorn.arm_const import *
flash=(ROOT/'firmware_dump/flash_cpu_pass1.bin').read_bytes()
ram=(ROOT/'firmware_dump/startup_ram_20000000.bin').read_bytes()

def model():
    u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
    for a,n in [(0,0x20000),(0x20000000,0x10000),(0x40000000,0x20000),(0xe000e000,0x2000)]:u.mem_map(a,n)
    u.mem_write(0,flash);u.mem_write(0x20000000,ram)
    u.reg_write(UC_ARM_REG_SP,0x20008000);u.reg_write(UC_ARM_REG_LR,0x1ff01)
    return u

u=model();events=[]
def code(uc,a,size,data):
    if a in (0xdde8,0xdd80):
        events.append(dict(kind='short_delay' if a==0xdde8 else 'long_delay',value=uc.reg_read(UC_ARM_REG_R0)))
        uc.reg_write(UC_ARM_REG_R0,1);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
def write(uc,access,a,size,value,data):
    assert a>=0x20000 and not 0x40013000<=a<0x40014000
    if a>=0x40000000:events.append(dict(kind='write',address=hex(a),value=hex(value),bytes=size))
u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_WRITE,write)
u.emu_start(0x5a65,0x1ff00,count=100000)
assert u.reg_read(UC_ARM_REG_PC)==0x1ff00

p=model();frames=[]
# Original RGB source: 3 planes of 66 uint16 entries, with 6-byte prefix.
for plane in range(3):
    for channel in range(11):
        for bank in range(6):
            p.mem_write(0x20000944+6+plane*132+channel*12+bank*2,struct.pack('<H',(plane*70+channel*6+bank)%251))
p.mem_write(0x20000019,b'\1');p.mem_write(0x2000002b,b'\x09')
def intercept(uc,a,size,data):
    if a==0x5a74:
        address=uc.reg_read(UC_ARM_REG_R0);length=uc.reg_read(UC_ARM_REG_R2)
        frames.append(dict(tx=hex(address),rx=hex(uc.reg_read(UC_ARM_REG_R1)),length=length,hex=bytes(uc.mem_read(address,length)).hex()))
        uc.reg_write(UC_ARM_REG_R0,1);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
p.hook_add(UC_HOOK_CODE,intercept);p.reg_write(UC_ARM_REG_R0,0xc0)
p.emu_start(0x3bf9,0x1ff00,count=100000)
assert len(frames)==1 and frames[0]['length']==269
frame=bytes.fromhex(frames[0]['hex'])
assert frame[:6]==bytes.fromhex('c00b0600fa00')
for plane in range(3):
    for channel in range(11):
        for bank in range(6):assert frame[6+plane*88+channel*8+bank]==(plane*70+channel*6+bank)%251
result=dict(hardware_access=False,spi_init_events=events,frame=frames[0],enabled_brightness_level=9,enabled_timing_field=250,disabled_fallback_field=6250,
            frame_mapping='6-byte header; three88-byte planes;11channels,8-byte stride,6 populated bank bytes;269-byte transfer',
            interpretation='Observed transport for external RGB controller; exact controller identity and color plane names unconfirmed.')
out=Path(__file__).with_name('original_transport_observations.json');out.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
