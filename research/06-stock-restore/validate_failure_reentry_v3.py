"""Native outer error/timeout returns toUSBbootstrap with V3, offline only."""
from pathlib import Path
import sys,struct,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'.tools'))
from extract_vendor_stub import extract
from usb_block_reader import build_block
from unicorn import *
from unicorn.arm_const import *
flash=(ROOT/'firmware_dump/flash_cpu_pass1.bin').read_bytes();ram=(ROOT/'firmware_dump/boot_initial_ram.bin').read_bytes()
original,_=extract(ROOT/'fw_update.pcap');stub=(ROOT/'stock_restore/bounded_stock_stub_v3.bin').read_bytes()
stock=(ROOT/'stock_flash_preparation/20261103T052626Z/stock_application_pages.bin').read_bytes()
CTX=0x20000324
def frame(image):
    f=bytearray(original);f[52:492]=image;x=0
    for v in struct.unpack('<110I',image):x^=v
    struct.pack_into('<I',f,492,x);return bytes(f)
read,_=build_block(0,56);results=[]
for kind in ('error','timeout'):
    u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
    for a,n in [(0,0x20000),(0x20000000,0x10000),(0x40000000,0x20000),(0xe000e000,0x2000)]:u.mem_map(a,n)
    u.mem_write(0,flash);u.mem_write(0x20000000,ram)
    def w(a,v):u.mem_write(a,struct.pack('<I',v))
    def ret(v=0):u.reg_write(UC_ARM_REG_R0,v);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    w(0x20000754,0x5a5a5a5a);w(0x20000758,0xa5a5a5a5)
    w(0x20000234,CTX);w(CTX+0x214,0x20004005);w(CTX+0x218,0x20004001);w(CTX+0x21c,0xf01)
    packets=[('START',frame(stub)),('DATA1',bytes.fromhex('0201007300020177')+stock[:512])]
    if kind=='error':packets.append(('midtransfer_START',frame(read)))
    current=[''];acks=[];delays=[];reached=[];events=[]
    initial_sp=0x2000f000;saved=[0x44444444,0x55555555,0x66666666,0x77777777]
    def code(u,a,s,_):
        if a==0x20004000:
            if not packets:ret(0);return
            name,p=packets.pop(0);current[0]=name;u.mem_write(CTX,b'\0'*520);u.mem_write(CTX,p);ret(1)
        elif a==0x20004004:acks.append({'packet':current[0],'status':u.mem_read(CTX+8,1)[0]});ret()
        elif a==0x398:ret()
        elif a==0x29c:
            assert current[0]=='START';u.mem_write(u.reg_read(UC_ARM_REG_R1),struct.pack('<IIII',0x1cc00,0,(0xe908//4<<16)|0xa104,0));ret()
        elif a==0x9bc:delays.append(u.reg_read(UC_ARM_REG_R0));ret()
        elif a in (0x848,0x24c):reached.append(hex(a));u.emu_stop()
    def write(u,x,a,s,v,_):
        if a==initial_sp-4 or a==0x40013000:events.append({'address':hex(a),'value':v,'pc':hex(u.reg_read(UC_ARM_REG_PC))})
    u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_WRITE,write)
    u.reg_write(UC_ARM_REG_R0,CTX);u.reg_write(UC_ARM_REG_SP,initial_sp);u.reg_write(UC_ARM_REG_LR,0x87f)
    for reg,v in zip((UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7),saved):u.reg_write(reg,v)
    u.emu_start(0xbdd,0x1ff00,count=1000000)
    assert reached==['0x848'] and u.reg_read(UC_ARM_REG_SP)==initial_sp
    assert [u.reg_read(reg) for reg in (UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7)]==saved
    assert u.reg_read(UC_ARM_REG_R0)==(4 if kind=='error' else 5)
    patch=next(i for i,e in enumerate(events) if e['address']==hex(initial_sp-4) and e['value']==0x849)
    firstcommand=next(i for i,e in enumerate(events) if e['address']=='0x40013000')
    assert patch<firstcommand
    results.append({'kind':kind,'passed':True,'reached':reached,'native_return':u.reg_read(UC_ARM_REG_R0),'restored_sp':hex(u.reg_read(UC_ARM_REG_SP)),'restored_r4_r7':[hex(v) for v in saved],'saved_return_patch_before_first_flash_command':True,'delay_calls_modeled':len(delays),'acks':acks,'saved_return_patch':events[patch]})
result={'passed':True,'stub_sha256':hashlib.sha256(stub).hexdigest(),'cases':results,'no_hardware_access':True,'no_COMPLETE':True,'model':'OriginalnativeBDCouterhandlerandstub/nativeABIhelpers; STARTcryptooutputacceptedfixture;delay9bcskippedonlyforfasttimeout;RAM-likeMMIObusyclear. Stopsatbootstrap848beforephysicalUSBinit.','limitation':'SinglefailureUSBbootstrapreentry, not indefinitehold. NewBDCsessionwillstartwith87Funlessholdstubrenewsprotection. Powerloss recovery not established.'}
(ROOT/'stock_restore/failure_reentry_v3_validation.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
