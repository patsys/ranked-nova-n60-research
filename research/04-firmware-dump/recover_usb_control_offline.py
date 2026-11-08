"""Reconstruct startup RAM and test USB requests using original code offline."""
import sys,struct,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'.tools'))
from unicorn import *
from unicorn.arm_const import *
flash=(ROOT/'firmware_dump/flash_cpu_pass1.bin').read_bytes()
def machine(ram=None):
    u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
    for a,n in [(0,0x20000),(0x20000000,0x10000),(0x40000000,0x20000),(0xe000e000,0x2000)]:u.mem_map(a,n)
    u.mem_write(0,flash)
    if ram:u.mem_write(0x20000000,ram)
    u.reg_write(UC_ARM_REG_SP,0x2000f000);u.reg_write(UC_ARM_REG_LR,0x1f001)
    return u
u=machine();u.emu_start(0x2285,0x20e0,count=1000000)
assert u.reg_read(UC_ARM_REG_PC)==0x20e0
ram=bytes(u.mem_read(0x20000000,0x4000))
out=ROOT/'qmk_port/usb';out.mkdir(parents=True,exist_ok=True)
(out/'original_initialized_ram.bin').write_bytes(ram)
def word(a):return struct.unpack_from('<I',ram,a-0x20000000)[0]
manifest={'initialized_ram_sha256':hashlib.sha256(ram).hexdigest(),'scatter_table':[],'tables':{},'requests':[],'rx_cases':[],'descriptors':[]}
for a in range(0x10614,0x10644,16):
    manifest['scatter_table'].append([hex(v) for v in struct.unpack_from('<IIII',flash,a)])
for a,n in [(0x20000378,8),(0x200003cc,12),(0x200003fc,8),(0x20000510,4)]:
    manifest['tables'][hex(a)]=[hex(word(a+4*i)) for i in range(n)]
for name,offset,length in [('device',0x104a7,18),('configuration',0x104b9,66),('language',0x104fb,4),('hid_report_interface0',0x104ff,65),('hid_report_interface1',0x10540,211),('manufacturer',0xf5c7,14),('product',0xf5d5,36),('serial',0xf5f9,22)]:
    data=flash[offset:offset+length]
    (out/(name+'.bin')).write_bytes(data)
    manifest['descriptors'].append({'name':name,'address':hex(offset),'length':length,'sha256':hashlib.sha256(data).hexdigest(),'hex':data.hex()})
def run(u,entry):
    u.reg_write(UC_ARM_REG_SP,0x2000f000);u.reg_write(UC_ARM_REG_LR,0x1f001)
    u.emu_start(entry|1,0x1f000,count=1000000)
    assert u.reg_read(UC_ARM_REG_PC)==0x1f000,hex(u.reg_read(UC_ARM_REG_PC))
def prepare():
    u=machine(ram)
    # Reproduce three pointer assignments at0xf004, without calling hardware init.
    u.mem_write(0x20000510,struct.pack('<III',0x20001418,0x200003cc,0x200003fc))
    u.mem_write(0x20001420,b'\x02')
    return u
for name,dtype,index,iface,requestlen,expected in [
    ('device_first8',1,0,0,8,flash[0x104a7:0x104af]),
    ('device_full',1,0,0,18,flash[0x104a7:0x104b9]),
    ('configuration_header',2,0,0,9,flash[0x104b9:0x104c2]),
    ('configuration_full',2,0,0,255,flash[0x104b9:0x104fb]),
    ('hid_report_interface0',0x22,0,0,255,flash[0x104ff:0x10540]),
    ('hid_report_interface1',0x22,0,1,255,flash[0x10540:0x10613]),
    ('hid_descriptor_interface0',0x21,0,0,9,flash[0x104cb:0x104d4]),
    ('hid_descriptor_interface1',0x21,0,1,9,flash[0x104e4:0x104ed]),
    ('string_language',3,0,0,255,flash[0x104fb:0x104ff]),
    ('string_manufacturer',3,1,0x409,255,flash[0xf5c7:0xf5d5]),
    ('string_product',3,2,0x409,255,flash[0xf5d5:0xf5f9]),
    ('string_serial',3,3,0x409,255,flash[0xf5f9:0xf60f]),
]:
    u=prepare();writes=[]
    def write(u,access,a,s,v,_):
        if 0x40000000<=a<0x40020000:writes.append({'pc':hex(u.reg_read(UC_ARM_REG_PC)),'address':hex(a),'size':s,'value':v})
    u.hook_add(UC_HOOK_MEM_WRITE,write)
    setup=struct.pack('<BBHHH',0x81 if dtype in (0x21,0x22) else 0x80,6,(dtype<<8)|index,iface,requestlen)
    for i,b in enumerate(setup):u.mem_write(0x40017fa0+i*4,struct.pack('<I',b))
    run(u,0xdf90)
    packets=[]
    def packet():
        n=struct.unpack('<I',u.mem_read(0x40017ed4,4))[0]
        return bytes(u.mem_read(0x40017c00+i*4,1)[0] for i in range(n))
    packets.append(packet())
    for _ in range(100):
        remaining=struct.unpack('<H',u.mem_read(0x20001428,2))[0]
        if not remaining:break
        run(u,0x2520);packets.append(packet())
    observed=b''.join(packets)
    assert observed==expected,(name,observed.hex(),expected.hex())
    manifest['requests'].append({'name':name,'setup':setup.hex(),'packet_lengths':[len(p) for p in packets], 'response_sha256':hashlib.sha256(observed).hexdigest(),'response_hex':observed.hex(),'passed':True,'mmio_writes':writes})
for fifo,lengths in [(0x40017b00,(0,1,8)),(0x40017500,(0,1,8,64))]:
    for length in lengths:
        u=machine(ram);reads=[]
        data=bytes(0x80+i for i in range(length))
        for i,b in enumerate(data):u.mem_write(fifo+i*4,struct.pack('<I',0xdeadbe00|b))
        def read(u,access,a,s,v,_):
            if 0x40000000<=a<0x40020000:reads.append({'address':hex(a),'size':s})
        u.hook_add(UC_HOOK_MEM_READ,read)
        for reg,value in [(UC_ARM_REG_R0,0x20002000),(UC_ARM_REG_R1,fifo),(UC_ARM_REG_R2,length)]:u.reg_write(reg,value)
        run(u,0xd4d4)
        assert bytes(u.mem_read(0x20002000,length))==data
        assert reads==[{'address':hex(fifo+i*4),'size':1} for i in range(length)]
        manifest['rx_cases'].append({'fifo':hex(fifo),'length':length,'reads':reads,'passed':True})
print(f"Startup RAM recovered; {len(manifest['requests'])} descriptor requests and {len(manifest['rx_cases'])} RX cases passed offline")
(out/'control_recovery.json').write_text(json.dumps(manifest,indent=2))
