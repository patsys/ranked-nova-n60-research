"""Offline original bootloader entry-path audit; never opens a device."""
from pathlib import Path
import hashlib,json,struct,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.tools'))
from unicorn import *
from unicorn.arm_const import *

flash=(ROOT/'firmware_dump/flash_cpu_pass1.bin').read_bytes()
def new_cpu(image=flash):
    u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
    u.mem_map(0,0x20000);u.mem_write(0,image)
    u.mem_map(0x10000000,0x10000);u.mem_write(0x10000600,b'\xff'*512)
    u.mem_map(0x20000000,0x4000)
    u.mem_map(0x40000000,0x20000);u.mem_map(0xe000e000,0x2000)
    return u

# Execute unmodified original scatter-load startup to boot main, independently
# of current application vectors. No peripherals are used before main.
u=new_cpu();reached=[]
def stop_main(uc,address,size,data):
    if address==0x700:reached.append(address);uc.emu_stop()
handle=u.hook_add(UC_HOOK_CODE,stop_main)
u.reg_write(UC_ARM_REG_SP,struct.unpack_from('<I',flash)[0])
u.emu_start(struct.unpack_from('<I',flash,4)[0],0,count=50000)
assert reached and u.reg_read(UC_ARM_REG_PC)==0x700
initial_ram=bytes(u.mem_read(0x20000000,0xbf0))

def gate_case(name,pin_word=0xffffffff,gpio=0xffffffff,request=0,request_config=0xffffffff,
              blank_app=False,run_validity=False,patch_address=0xffffffff):
    image=bytearray(flash)
    if blank_app:image[0x2000:0x1a000]=b'\xff'*(0x1a000-0x2000)
    uc=new_cpu(bytes(image));uc.mem_write(0x20000000,initial_ram)
    for address,value in ((0x10000700,pin_word),(0x10000714,request_config),
                          (0x10000750,patch_address),(0x4001400c,request),(0x40018030,gpio)):
        uc.mem_write(address,struct.pack('<I',value))
    decisions=[];reads=[];writes=[];delay_calls=[]
    def code(cpu,address,size,data):
        if address==0x9bc:
            delay_calls.append(cpu.reg_read(UC_ARM_REG_R0))
            cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
        if address in (0x848,0x8b6,0x24c) or (address==0x7fe and not run_validity):
            decisions.append(address);cpu.emu_stop()
    def memory(cpu,access,address,size,value,data):
        if access==UC_MEM_READ:reads.append([address,size])
        else:writes.append([address,size,value])
    uc.hook_add(UC_HOOK_CODE,code)
    uc.hook_add(UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,memory)
    uc.reg_write(UC_ARM_REG_SP,0x20000bf0)
    uc.emu_start(0x701,0,count=50000)
    assert decisions,(name,hex(uc.reg_read(UC_ARM_REG_PC)))
    assert not any(address<0x20000 for address,size,value in writes)
    decision={0x848:'usb_bootstrap',0x7fe:'application_validity_path',0x8b6:'application_handoff',0x24c:'reset'}[decisions[0]]
    return {'case':name,'config_pin_word':hex(pin_word),'gpio_input':hex(gpio),
            'retained_request':hex(request),'config_request':hex(request_config),
            'application_blank':blank_app,'decision':decision,
            'mode_word_r5':hex(uc.reg_read(UC_ARM_REG_R5)),
            'gpio_reads':[hex(a) for a,s in reads if 0x40018030<=a<=0x4001803c],
            'app_reads_before_decision':[hex(a) for a,s in reads if 0x2000<=a<0x1a000],
            'request_register_after':hex(struct.unpack('<I',uc.mem_read(0x4001400c,4))[0]),
            'original_delay_arguments':delay_calls,'flash_writes':False,'passed':True}

cases=[]
for blank in (False,True):
    prefix='blank_app' if blank else 'original_app'
    a=gate_case(prefix+'_fallback_magic',request=0x5ac396c5,blank_app=blank)
    assert a['decision']=='usb_bootstrap' and not a['app_reads_before_decision']
    assert a['request_register_after']=='0x0';cases.append(a)
    a=gate_case(prefix+'_configured_magic',request=0x12345678,request_config=0x12345678,blank_app=blank)
    assert a['decision']=='usb_bootstrap' and not a['app_reads_before_decision'];cases.append(a)
    a=gate_case(prefix+'_configured_magic_mismatch',request=0x5ac396c5,request_config=0x12345678,blank_app=blank)
    assert a['decision']=='application_validity_path';cases.append(a)
    for gpio,expected in ((0,'usb_bootstrap'),(1,'application_validity_path'),(2,'application_validity_path'),(3,'application_validity_path')):
        a=gate_case(prefix+f'_synthetic_pin0_pin1_gpio_{gpio}',pin_word=0x100,gpio=gpio,blank_app=blank)
        assert a['decision']==expected
        if expected=='usb_bootstrap':assert not a['app_reads_before_decision']
        cases.append(a)
    a=gate_case(prefix+'_pin_override_disabled',gpio=0,blank_app=blank)
    assert a['decision']=='application_validity_path' and not a['gpio_reads'];cases.append(a)

# Blank metadata (all FF) reaches the real invalid-tag path without reading any
# app byte, then enters the USB bootstrap. This is a conditional fixture only.
a=gate_case('blank_app_and_erased_metadata_fixture',blank_app=True,run_validity=True)
assert a['decision']=='usb_bootstrap';cases.append(a)
# If a register-patch list is enabled, invalid patch targets force USB mode.
a=gate_case('invalid_register_patch_target',patch_address=0x40000000)
assert a['decision']=='usb_bootstrap';cases.append(a)

# The original application primitive requests reset; stop at its terminal loop.
uc=new_cpu();app_writes=[]
def app_code(cpu,address,size,data):
    if address==0x3eec:cpu.emu_stop()
def app_write(cpu,access,address,size,value,data):app_writes.append([address,size,value])
uc.hook_add(UC_HOOK_CODE,app_code);uc.hook_add(UC_HOOK_MEM_WRITE,app_write)
uc.reg_write(UC_ARM_REG_SP,0x20001c50);uc.emu_start(0x3ed9,0,count=100)
assert app_writes==[[0x4001400c,4,0x5ac396c5],[0xe000ed0c,4,0x05fa0004]],app_writes
result={'source_sha256':hashlib.sha256(flash).hexdigest(),'boot_scatter_init_reaches_main':True,
        'cases':cases,'case_count':len(cases),'application_reset_primitive_writes':app_writes,
        'limitations':'Synthetic configuration and GPIO fixtures, not actual reads of 0x10000600 metadata or physical pins. Stops before USB initialization; no electrical enumeration or recovery operation tested.'}
captured=ROOT/'firmware_dump/boot_safety_audit/metadata_10000600.bin'
if captured.exists():
    metadata=captured.read_bytes();assert len(metadata)==512
    actual_cases=[]
    for app_kind in ('original','erased','invalid_reset','changed_body'):
        for request in (0,0x5ac396c5):
            image=bytearray(flash)
            if app_kind=='erased':image[0x2000:0x1a000]=b'\xff'*(0x1a000-0x2000)
            if app_kind=='invalid_reset':struct.pack_into('<I',image,0x2004,0xdeadbeef)
            if app_kind=='changed_body':image[0x2400]^=1
            cpu=new_cpu(bytes(image));cpu.mem_write(0x20000000,initial_ram)
            cpu.mem_write(0x10000600,metadata);cpu.mem_write(0x4001400c,struct.pack('<I',request))
            seen=[];actual_reads=[];actual_writes=[]
            def actual_code(uc,address,size,data):
                if address==0x9bc:uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
                if address==0x7fe:seen.append('checksum_gate_entered')
                if address in (0x848,0x8c0,0x24c):
                    seen.append({0x848:'usb_bootstrap',0x8c0:'application_blx',0x24c:'reset'}[address]);uc.emu_stop()
            def actual_mem(uc,access,address,size,value,data):
                if access==UC_MEM_READ:actual_reads.append([address,size])
                else:actual_writes.append([address,size,value])
            cpu.hook_add(UC_HOOK_CODE,actual_code);cpu.hook_add(UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,actual_mem)
            cpu.reg_write(UC_ARM_REG_SP,0x20000bf0);cpu.emu_start(0x701,0,count=50000)
            assert seen==(['usb_bootstrap'] if request else ['application_blx']),(app_kind,request,seen)
            target=cpu.reg_read(UC_ARM_REG_R0) if not request else None
            assert not request or not any(0x2000<=a<0x1a000 for a,s in actual_reads)
            if not request:assert target==struct.unpack_from('<I',image,0x2004)[0]
            actual_cases.append({'application':app_kind,'retained_request':hex(request),'decision':seen[-1],
                                 'attempted_application_target':hex(target) if target is not None else None,
                                 'checksum_gate_entered':False,
                                 'gpio_reads':[hex(a) for a,s in actual_reads if 0x40018030<=a<=0x4001803c],
                                 'app_reads':[hex(a) for a,s in actual_reads if 0x2000<=a<0x1a000],
                                 'configuration_patch_writes':[[hex(a),hex(v)] for a,s,v in actual_writes if a in (0x400130e8,0x400130ec)],
                                 'passed':True})
    result['captured_metadata_sha256']=hashlib.sha256(metadata).hexdigest()
    result['actual_metadata_cases']=actual_cases
    result['actual_metadata_conclusion']='Configured register-patch list bypasses checksum gate; GPIO override disabled. With request zero, even blank/bad-reset app reaches BLX of its reset vector. Existing default retained request still enters USB bootstrap first.'
    result['limitations']='Original code executed offline using captured metadata plus modeled peripheral register storage/delay interception. USB initialization/physical recovery not exercised; stop before application BLX.'
Path(__file__).with_name('recovery_entry_validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(f'PASS: {len(cases)} synthetic entry cases, {len(result.get("actual_metadata_cases",[]))} captured-metadata cases, boot initialization and app reset primitive.')
