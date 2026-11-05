"""Offline native117-page stock transfer followed by a read-only START.
Never opens hardware. This intentionally reports whether that transition works.
"""
from pathlib import Path
import sys,struct,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'.tools'))
sys.path.insert(0,str(ROOT/'contributions/ry72xx-flasher/src'))
from ry72xx_flasher.loader import load_profile
from ry72xx_flasher.transport import start_frame,data_frame
from ry72xx_flasher.stubs import read_stub as payload_read,release_stub as payload_release
def build_block(address,length): return payload_read(address,length),{}
from unicorn import *
from unicorn.arm_const import *
CTX=0x20000324
flash=(ROOT/'firmware_dump/flash_cpu_pass1.bin').read_bytes()
ram=(ROOT/'firmware_dump/boot_initial_ram.bin').read_bytes()
header,profile_loader=load_profile(ROOT/'.local-flasher/loader.json')
original=start_frame(header,profile_loader)
body_path=Path(sys.argv[sys.argv.index('--body')+1]) if '--body' in sys.argv else ROOT/'stock_flash_preparation/20261103T052626Z/stock_application_pages.bin'
body=body_path.read_bytes()
masked='--masked' in sys.argv
release='--release' in sys.argv
v3='--v3' in sys.argv or release
v2='--v2' in sys.argv or v3
stub=profile_loader
def frame(image): return start_frame(header,image)
start=frame(stub);assert start[:52]==original[:52] and len(body)==117*512
read_stub,_=build_block(0,56)
packets=[('bounded_START',start)]+[(f'DATA_{i+1}',data_frame(i+1,body[i*512:(i+1)*512])) for i in range(117)]+[('reader_START',frame(read_stub))]
if v2:
    read2,_=build_block(0x2000,56)
    def build(address,length): return payload_read(address,length,True)
    packets.extend([('second_reader_START',frame(read2)),('metadata_START',frame(build(0x10000600,56)))])
if release:
    release_stub=payload_release()
    assert hashlib.sha256(release_stub).hexdigest()=='57332cb094949feeba32c44fa829bb57069eaef61d92bceab161601737af4323'
    packets.extend([('release_START',frame(release_stub)),('GETV',bytes.fromhex('0000000004000001')+b'getv')])
u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
for a,n in [(0,0x20000),(0x10000000,0x1000),(0x20000000,0x10000),(0x40000000,0x20000),(0xe000e000,0x2000)]:u.mem_map(a,n)
u.mem_write(0,flash);u.mem_write(0x20000000,ram)
metadata=(ROOT/'firmware_dump/boot_safety_audit/metadata_10000600.bin').read_bytes();u.mem_write(0x10000600,metadata)
def w(a,v):u.mem_write(a,struct.pack('<I',v))
def ret(v=0):u.reg_write(UC_ARM_REG_R0,v);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
w(0x20000754,0x5a5a5a5a);w(0x20000758,0xa5a5a5a5)
w(0x20000234,CTX);w(CTX+0x214,0x20004005);w(CTX+0x218,0x20004001);w(CTX+0x21c,0xf01)
current=[''];acks=[];pages=[];start_callbacks=[];fmc_words=[];remaining=[];cleanup=[];commands=[];word_addresses=[];return_writes=[];controller_address=[0];controller_data=[0];mask_checks=[0]
def code(u,a,s,_):
    if a==0x20004000:
        if not packets:u.emu_stop();return
        name,p=packets.pop(0);current[0]=name
        remaining.append({'packet':name,'active':int.from_bytes(u.mem_read(u.reg_read(UC_ARM_REG_SP)+8,4),'little'),'r5_remaining':u.reg_read(UC_ARM_REG_R5)})
        u.mem_write(CTX,b'\0'*520);u.mem_write(CTX,p);ret(1)
    elif a==0x20004004:
        n=int.from_bytes(u.mem_read(CTX+4,2),'little')
        acks.append({'packet':current[0],'status':u.mem_read(CTX+8,1)[0],'length':n,'payload_hex':bytes(u.mem_read(CTX+8,n)).hex()});ret()
    elif a==0xf00:start_callbacks.append(current[0])
    elif a==0x398:ret()
    elif a==0x29c:
        assert current[0].endswith('START')
        u.mem_write(u.reg_read(UC_ARM_REG_R1),struct.pack('<IIII',0x1cc00,0,(0xe908//4<<16)|0xa104,0));ret()
    elif a in (0x214,0x220):pages.append({'packet':current[0],'operation':'erase' if a==0x214 else 'program','page':u.reg_read(UC_ARM_REG_R0),'context':hex(u.reg_read(UC_ARM_REG_R4)),'source':hex(u.reg_read(UC_ARM_REG_R1))})
    elif release and a in (0x87e,0x24c):
        cleanup.append({'address':hex(a),'sp':hex(u.reg_read(UC_ARM_REG_SP)),'r4_r7':[hex(u.reg_read(r)) for r in (UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7)],'native_return':u.reg_read(UC_ARM_REG_R0)})
        if a==0x24c:u.emu_stop()
def write(u,x,a,s,v,_):
    if masked:
        assert u.reg_read(UC_ARM_REG_PRIMASK)==1
        mask_checks[0]+=1
    if a==0x40013004:controller_address[0]=v
    if a==0x40013008:controller_data[0]=v
    if a==0x40013000:
        target=controller_address[0]*4
        assert 0x2000<=target<0x10a00
        if v==2:u.mem_write(target,b'\xff'*512)
        elif v==1:u.mem_write(target,struct.pack('<I',controller_data[0]))
    if a==0x40013008:fmc_words.append(v)
    if a==0x40013000:commands.append(v)
    if a==0x40013004:word_addresses.append(v)
    if a==0x2000effc:return_writes.append({'packet':current[0],'value':hex(v),'pc':hex(u.reg_read(UC_ARM_REG_PC))})
u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_WRITE,write)
u.reg_write(UC_ARM_REG_R0,CTX);u.reg_write(UC_ARM_REG_SP,0x2000f000);u.reg_write(UC_ARM_REG_LR,0x87f if release else 0x1ff01)
if masked:u.reg_write(UC_ARM_REG_PRIMASK,1)
if release:
    for r,v in zip((UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7),(CTX+0x200,2,0x20000754,0x40014000)):u.reg_write(r,v)
u.emu_start(0xbdd,0x1ff00,count=10000000)
assert len(pages)==234 and [p['page'] for p in pages[::2]]==list(range(16,133))
assert fmc_words==list(struct.unpack('<14976I',body))
assert bytes(u.mem_read(0x2000,59904))==body
assert all(a['status']==4 for a in acks[:118])
if v2:
    assert len(acks)==(123 if release else 121)
    for reply,expected in zip(acks[118:121],[flash[:56],body[:56],metadata[:56]]):
        assert reply['length']==56 and bytes.fromhex(reply['payload_hex'])==expected
    assert start_callbacks==['bounded_START','reader_START','second_reader_START','metadata_START']+(['release_START'] if release else [])
    if release:
        assert acks[-2]['packet']=='release_START' and acks[-2]['status']==4
        assert acks[-1]['packet']=='GETV' and acks[-1]['status']==5
        assert [c['address'] for c in cleanup]==['0x87e','0x24c']
        assert all(c['sp']=='0x2000f000' and c['r4_r7']==['0x20000524','0x2','0x20000754','0x40014000'] for c in cleanup)
        assert return_writes[-1]['packet']=='release_START' and return_writes[-1]['value']=='0x87f'
        assert commands.count(1)==14976 and commands.count(2)==117 and len(commands)==15093
        assert min(word_addresses)==0x800 and max(word_addresses)==0x427f
        assert bytes(u.mem_read(0x10000600,512))==metadata
else:
    assert len(acks)==119 and acks[-1]['packet']=='reader_START' and acks[-1]['status']==5
    assert start_callbacks==['bounded_START'] and u.reg_read(UC_ARM_REG_PC)==0x1ff00 and u.reg_read(UC_ARM_REG_R0)==4
result={'passed_native_protocol_audit':True,'requested_in_place_reader_transition_works':v2,'reason':'Lastpagehandoffclearsactive; threeguardedreadonlySTARTsreturnexactboot/app/metadata56-bytepayloadswithoutCOMPLETEorappjump.' if v2 else 'Native0xcaa rejects START whileDATAactive, sendsNACK5 andreturns4; readerstubnevercopiedorcalled.','stub_sha256':hashlib.sha256(stub).hexdigest(),'bounded_START_header_first52_unchanged':True,'clear_image_length':'0x1cc00','crypto_model':'Only originalSTART0x29c acceptedmetadata modeled as1cc00/E908/A104; DATAusesrealplaintextflagclearedbyboundedstub.','body_sha256':hashlib.sha256(body).hexdigest(),'stock_pages_programmed_in_model':117,'all_14976_program_words_match_stock':True,'first_page':16,'last_page':132,'no_COMPLETE':True,'final_native_return':None if v2 else 4,'reader_START_reply':acks[-1],'start_callbacks':start_callbacks,'remaining_state_last':remaining[-1],'acks':acks,'model':'Originalouterhandler,stock117actual512-bytepayloads,boundedstubandnativeABIhelpers;RAM-likeMMIOwithbusyclear.No physicalflashupdated.','hardware_access':False}
if release:result.update(release_checked=True,release_stub_sha256=hashlib.sha256(release_stub).hexdigest(),release_then_GETV_no_extra_START=True,native_cleanup=cleanup,final_native_return=4,final_saved_return_write=return_writes[-1],only_original_117_pages_controller_commands=True,metadata_window_unchanged=True,reason='After117pagesandthreecorrectreaders, guardedrelease restores87F; GETVreturns4through87Etonativereset24Cwithrestoredstack/registers. NoadditionalFMCcommandsorCOMPLETE.')
result.update(packaged_start_data_and_probe_generators=True,passed=True,all_program_words_match_body=True,emulated_readback_matches_body=True,primask_initial=1 if masked else 0,primask_final=u.reg_read(UC_ARM_REG_PRIMASK),mask_checks=mask_checks[0],controller_storage_model='RAM-likeFMCcommandsupdateemulatedCPUflash;thisisnotphysicalprogrammingproof')
if '--body' in sys.argv:
    result.pop('stock_pages_programmed_in_model',None);result.pop('all_14976_program_words_match_stock',None)
    result.update(body_file=str(body_path),pages_programmed_in_model=117,model='Originalnativeouterhandler,target117actual512-bytepayloads,boundedstubandnativeABIhelpers;modeledFMCupdatesemulatedCPUflashonly.No physicalflashupdated.')
if masked:assert result['primask_final']==1
output=ROOT/'contributions/flasher_native_protocol_validation.json'
output.write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k!='acks'},indent=2))
