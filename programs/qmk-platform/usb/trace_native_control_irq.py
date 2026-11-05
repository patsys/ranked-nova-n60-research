"""Offline native control IRQ evidence, including no-data status stages."""
import runpy,sys,json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
g=runpy.run_path(str(ROOT/'firmware_dump/recover_usb_control_offline.py'))
from unicorn import UC_HOOK_MEM_WRITE,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_PC,UC_ARM_REG_LR
cases=[]
for name,setup in [('set_address7',bytes.fromhex('0005070000000000')),('set_config1',bytes.fromhex('0009010000000000')),('set_config0',bytes.fromhex('0009000000000000')),('bad_address128',bytes.fromhex('0005800000000000'))]:
    u=g['prepare']();writes=[];skipped=[]
    def code(u,a,s,_):
        if a in (0xdd80,0xdde8):
            skipped.append(hex(a));u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    def write(u,x,a,s,v,_):
        if 0x40000000<=a<0x40020000:writes.append({'pc':hex(u.reg_read(UC_ARM_REG_PC)),'address':hex(a),'size':s,'value':v})
    u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_WRITE,write)
    for i,b in enumerate(setup):u.mem_write(0x40017fa0+4*i,struct.pack('<I',b))
    stages=[]
    for event in (0,6):
        writes.clear();u.mem_write(0x40016000,struct.pack('<I',event));g['run'](u,0xebf0)
        stages.append({'event':event,'writes':list(writes),'control_context':bytes(u.mem_read(0x20001418,32)).hex(),'usb_state':bytes(u.mem_read(0x2000051c,16)).hex()})
    cases.append({'name':name,'setup':setup.hex(),'stages':stages,'delay_helpers_skipped':skipped})
(ROOT/'qmk_port/usb/native_control_irq_traces.json').write_text(json.dumps(cases,indent=2))
print('Native SET_ADDRESS/SET_CONFIGURATION IRQ traces recorded:',len(cases))
