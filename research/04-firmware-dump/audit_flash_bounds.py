"""Offline only: native START/DATA bounds and supplied vendor stub commands.

Cipher output and controller completion are explicit model assumptions. This
never opens USB/HID or writes the recovered flash image/device.
"""
import sys,json,struct,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'.tools'))
from extract_vendor_stub import extract
from unicorn import *
from unicorn.arm_const import *
flash=(ROOT/'firmware_dump/flash_cpu_pass1.bin').read_bytes()
captured,stub=extract(ROOT/'fw_update.pcap')
CTX=0x20000324; CFG=0x200001ec
def w(u,a,v):u.mem_write(a,struct.pack('<I',v&0xffffffff))
def r(u,a):return struct.unpack('<I',u.mem_read(a,4))[0]
def ret(u,v=0):u.reg_write(UC_ARM_REG_R0,v);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
def machine():
    u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
    for a,n in [(0,0x20000),(0x20000000,0x10000),(0x40000000,0x20000),(0xe000e000,0x2000),(0x10000000,0x1000)]:u.mem_map(a,n)
    u.mem_write(0,flash);u.reg_write(UC_ARM_REG_SP,0x2000f000);u.reg_write(UC_ARM_REG_LR,0x1f001)
    # Original reset/scatter-load, stopped before boot main/peripheral access.
    u.emu_start(0x1cd,0x700,count=50000)
    assert u.reg_read(UC_ARM_REG_PC)==0x700
    u.reg_write(UC_ARM_REG_SP,0x2000f000);u.reg_write(UC_ARM_REG_LR,0x1f001)
    # Guards established by the boot/update session; DATA itself writes+8.
    w(u,0x20000754,0x5a5a5a5a);w(u,0x20000758,0xa5a5a5a5)
    return u
def session(mode=1,data_length=512,image_length=0x1cc00,sequence=1,metadata_length=None,code_length=0xe908,extra_packets=0,skip_prior=False):
    u=machine();start=bytearray(captured);start[6]=mode
    struct.pack_into('<I',start,8,image_length&0xffffffff)
    # Native START compares this16-bit word count*4 against image_length.
    struct.pack_into('<H',start,2,(image_length//4)&0xffff)
    packets=[bytes(start)]
    for i in range(extra_packets+1):
        packets.append(bytes([2,(sequence+i)&255,0,0x73,data_length&255,data_length>>8,1,0x77])+bytes([0xa5])*data_length)
    events=[];commands=[];acks=[];assumptions=[];finished=[];current=[None]
    w(u,0x20000234,CTX);w(u,CTX+0x218,0x20004001);w(u,CTX+0x214,0x20004005);w(u,CTX+0x21c,0xf01)
    def code(u,a,s,_):
        if a==0x20004000:
            if not packets:finished.append('input_exhausted');u.emu_stop();return
            p=packets.pop(0);current[0]=p[0]
            if skip_prior and p[0]==2:
                u.reg_write(UC_ARM_REG_R6,sequence-1)
                u.reg_write(UC_ARM_REG_R5,max(0,image_length-(sequence-1)*512))
            u.mem_write(CTX,b'\0'*520);u.mem_write(CTX,p);ret(u,1)
        elif a==0x20004004:acks.append({'packet':current[0],'status':u.mem_read(CTX+8,1)[0]});ret(u)
        elif a==0x398:ret(u)
        elif a==0x29c:
            src=u.reg_read(UC_ARM_REG_R0);dest=u.reg_read(UC_ARM_REG_R1)
            if current[0]==1:
                n=image_length if metadata_length is None else metadata_length
                u.mem_write(dest,struct.pack('<IIII',n&0xffffffff,0,((code_length//4)<<16|0xa104)&0xffffffff,0))
            else:u.mem_write(dest,bytes(u.mem_read(src,16)))
            ret(u)
        elif a in (0x214,0x220):events.append({'kind':'erase' if a==0x214 else 'program','page':u.reg_read(UC_ARM_REG_R0),'source':hex(u.reg_read(UC_ARM_REG_R1))})
        elif a in (0xe18,0xe38):events[-1]['returned_status']=u.reg_read(UC_ARM_REG_R0)
        elif a==0x1f000:finished.append('native_return');u.emu_stop()
    def write(u,x,a,s,v,_):
        if 0x40013000<=a<0x40013100:commands.append({'pc':hex(u.reg_read(UC_ARM_REG_PC)),'address':hex(a),'value':v,'size':s})
    u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_WRITE,write)
    u.reg_write(UC_ARM_REG_R0,CTX)
    try:u.emu_start(0xbdd,0x1f000,count=2000000)
    except UcError as error:finished.append(f'emulation_fault:{error};pc={hex(u.reg_read(UC_ARM_REG_PC))}')
    if u.reg_read(UC_ARM_REG_PC)==0x1f000:finished.append('native_return')
    if skip_prior:assumptions.append('PriorDATAstate injected: r6=sequence-1 andr5=image_length-(sequence-1)*512; earlierpacketsnotexecuted')
    return {'mode':mode,'image_length':image_length,'metadata_length':metadata_length,'data_length':data_length,'sequence':sequence,'cfg_base':hex(r(u,CFG+0x2c)),'native_return':u.reg_read(UC_ARM_REG_R0) if 'native_return' in finished else None,'finished':finished,'acks':acks,'calls':events,'flash_controller_stores':commands,'model_assumptions':sorted(set(assumptions))}

cases=[session(mode=m) for m in (0,1,2,255)]
assert [e['page'] for e in cases[0]['calls']]==[0,0]
assert [e['page'] for e in cases[1]['calls']]==[16,16]
assert not cases[2]['calls'] and not cases[3]['calls']
assert sum(w['address']=='0x40013008' for w in cases[0]['flash_controller_stores'])==128
for n in (0,4,508,512,516):cases.append(session(data_length=n))
for n in (0,4,512,0x1e000,0x20000,0x3fffc,0x40000,0xffffffff):cases.append(session(image_length=n))
cases.append(session(metadata_length=0x1cc04))
cases.append(session(code_length=0x1cc04))
for length,seq in [(0x1cc00,230),(0x1cc00,231),(0x1e000,240),(0x1e200,241),(0x3fffc,255),(0x3fffc,256)]:
    cases.append(session(image_length=length,sequence=seq,skip_prior=True))
def complete_case(mode):
    u=machine();u.mem_write(0x20000000,stub)
    u.mem_write(0x10000600,(ROOT/'firmware_dump/boot_safety_audit/metadata_10000600.bin').read_bytes())
    w(u,0x2000075c,0x5555aaaa)
    for off,v in [(0x14,mode),(0x18,0x1cc00),(0x20,0xe908),(0x1c,0x25a4f084),(0x24,0x25a4f084)]:w(u,CFG+off,v)
    stores=[]
    def write(u,x,a,s,v,_):
        if 0x40013000<=a<0x40013100:stores.append({'pc':hex(u.reg_read(UC_ARM_REG_PC)),'address':hex(a),'value':v,'size':s})
    u.hook_add(UC_HOOK_MEM_WRITE,write);u.reg_write(UC_ARM_REG_R0,0x2000 if mode else 0)
    u.emu_start(0xae9,0x1f000,count=100000)
    addresses=[s['value'] for s in stores if s['address']=='0x40013004']
    assert addresses==[0x10180]+list(range(0x10180,0x10200)),addresses
    return {'mode':mode,'native_function':'0xae8 calledby COMPLETE0xed2 afterchecksumchecks','controller_word_addresses':addresses,'flash_controller_stores':stores,'native_return':u.reg_read(UC_ARM_REG_R0),'full_complete_packet_validation_not_executed':True}
complete=[complete_case(m) for m in (0,1)]
out=ROOT/'firmware_dump/flash_bounds_audit.json'
out.write_text(json.dumps({'offline_only':True,'vendor_stub_sha256':hashlib.sha256(stub).hexdigest(),'native_flash_sha256':hashlib.sha256(flash).hexdigest(),'crypto_model':'Native START cryptographic helper0x29c is supplied valid decoded metadata; algorithm/key not emulated. DATA crypto output copied foraddress-path purposes. OuterSTART fields,metadatachecks,stubcopyandXOR,mode/base selection,DATAremainingchecks,erase/programcallpathsandvendorstub instructions executeoriginalcode.','controller_model':'All peripheral registers are emulated RAM with busybitclear; originalstartupRAMABI/nativehelpersandvendorstubtiminginit execute. RAMguardmagic initializedasnotedinsource; DATAsetsitsownthirdguardword. Controllercommandstores demonstrateCPUreachability, not physicalerase/programsuccess.','cases':cases,'complete_metadata_scope':complete},indent=2))
print(f'{len(cases)} offline bounds cases recorded: {out}')
for c in cases:print(c['mode'],c['image_length'],c['data_length'],c['cfg_base'],[(e['kind'],e['page']) for e in c['calls']],c['acks'],c['finished'])
