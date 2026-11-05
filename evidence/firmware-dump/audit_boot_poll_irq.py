"""Offline native boot USB polling with erased application and IRQ mask fixtures."""
from pathlib import Path
import sys,json,struct,hashlib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.tools'))
from unicorn import *
from unicorn.arm_const import *
flash=(ROOT/'firmware_dump/flash_cpu_pass1.bin').read_bytes();ram=(ROOT/'firmware_dump/boot_initial_ram.bin').read_bytes()
cases=[]
for primask in (0,1):
 for erased in (False,True):
    u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
    for a,n in [(0,0x20000),(0x10000000,0x1000),(0x20000000,0x10000),(0x40000000,0x20000),(0xe000e000,0x2000)]:u.mem_map(a,n)
    image=bytearray(flash)
    if erased:image[0x2000:]=b'\xff'*(len(image)-0x2000)
    u.mem_write(0,bytes(image));u.mem_write(0x20000000,ram)
    u.mem_write(0x10000600,(ROOT/'firmware_dump/boot_safety_audit/metadata_10000600.bin').read_bytes())
    def w(a,v):u.mem_write(a,struct.pack('<I',v))
    ctx=0x20000324;w(0x20000234,ctx);w(ctx+0x218,0x10e9);w(ctx+0x214,0x1125);w(ctx+0x21c,0xf01)
    packet=bytes.fromhex('0000000004000001')+b'getv'
    for i,b in enumerate(packet):w(0x40017300+4*i,b)
    w(0x40017f34,len(packet));w(0x40017ea0,0x3c);w(0x40016008,1)
    u.reg_write(UC_ARM_REG_PRIMASK,primask);u.reg_write(UC_ARM_REG_SP,0x2000f000);u.reg_write(UC_ARM_REG_LR,0x1ff01);u.reg_write(UC_ARM_REG_R0,ctx)
    calls=[];reads=[];reply=[]
    def code(u,a,s,_):
        if a in (0x10e8,0x1278,0x3ee,0xf00,0x1124,0x594):calls.append(hex(a))
        if a==0x9bc:u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    def read(u,x,a,s,v,_):
        if 0x2000<=a<0x20000:reads.append(hex(a))
    def write(u,x,a,s,v,_):
        if a==0x40017ef4:
            assert v==64
            reply.append(bytes(u.mem_read(0x40017400+4*i,1))[0] for i in range(64));u.emu_stop()
    u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_READ,read);u.hook_add(UC_HOOK_MEM_WRITE,write)
    u.emu_start(0xbdd,0x1ff00,count=100000)
    assert len(reply)==1 and not reads
    payload=bytes(reply[0]);assert payload[:8]==bytes.fromhex('0000000010000001') and payload[8:16]==b'version:'
    assert u.reg_read(UC_ARM_REG_PRIMASK)==primask
    cases.append({'primask':primask,'application_erased':erased,'reply_hex':payload.hex(),'native_calls':calls,'app_data_reads':reads,'passed':True})
result={'passed':True,'boot_sha256':hashlib.sha256(flash[:0x2000]).hexdigest(),'cases':cases,'method':'ActualnativeUSBOUTpoll/reassembly10e8->1278->3ee->10cc,GETV0xf00,andnativeTX1124->594. MMIOpacket/eventstate supplied,delay9bcskipped,no IRQs synthesized.','scope':'DemonstratespollingdoesnotneedappvectorsorPRIMASK0. DoesNOTprovehardwarehasnoenabledIRQ/SysTicksources or that erased/newvectorscouldsurvive an actual asynchronous exception.','hardware_access':False}
(ROOT/'firmware_dump/boot_poll_irq_validation.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k!='cases'},indent=2))
