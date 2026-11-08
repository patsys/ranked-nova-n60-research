"""Isolated ARM tests of corrected matrix settling and bounded emergency hold.

Builds only a test ELF, never firmware targets or installation manifests.
"""
from pathlib import Path
import json,struct,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.tools'))
from unicorn import *
from unicorn.arm_const import *
OUT=Path(__file__).resolve().parent/'cold_fix_tests';OUT.mkdir(exist_ok=True)
TOOLS=ROOT/'.build-tools/bin';P=ROOT/'qmk_port';Q=ROOT/'qmk_source'
def run(args):return subprocess.run([str(x) for x in args],cwd=ROOT,check=True,capture_output=True,text=True).stdout
sources=[P/'keyboard/matrix.c',P/'scan/nova_acquisition.c',P/'scan/recovered_scan.c',P/'runtime/emergency_boot.c',P/'platform/original_delay.c',P/'platform/original_delay_loop.S']
flags=['-mcpu=cortex-m0','-mthumb','-Os','-std=gnu11','-ffreestanding','-fno-builtin','-ffunction-sections','-fdata-sections','-Wall','-Wextra','-Werror','-include',P/'keyboard/config.h']
for directory in (Q/'platforms',P/'platform',Q/'quantum',P/'keyboard'):flags+=['-I',directory]
elfpath=OUT/'cold_fix.elf'
run([TOOLS/'arm-none-eabi-gcc.exe',*flags,'-nostdlib','-Wl,--gc-sections,-Ttext=0x18000,-Tdata=0x20000600,-e,nova_emergency_hold_detected,-u,matrix_init_custom',*sources,'-Wl,--start-group','-lc','-lgcc','-Wl,--end-group','-o',elfpath])
nm=run([TOOLS/'arm-none-eabi-nm.exe','-n',elfpath]);(OUT/'cold_fix.nm').write_text(nm)
symbols={p[2]:int(p[0],16) for line in nm.splitlines() if len(p:=line.split())==3}
elf=elfpath.read_bytes();results=[]
def test(name,mode,required,ready,expected,expected_scans,long_failure=0,init_failure=False):
    u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
    u.mem_map(0,0x20000);u.mem_map(0x20000000,0x4000);u.mem_map(0x40000000,0x20000)
    off=struct.unpack_from('<I',elf,28)[0];size,num=struct.unpack_from('<HH',elf,42)
    for i in range(num):
        typ,p,v,a,n,m,f,align=struct.unpack_from('<8I',elf,off+i*size)
        if typ==1 and n:u.mem_write(v,elf[p:p+n])
    bank=[0];scan=[-1];events=[];minimum_sp=[0x20001c50]
    def memory(uc,access,address,size,value,data):
        if access==UC_MEM_WRITE:
            assert address>=0x20000000,hex(address)
            if 0x40000000<=address<0x40020000:events.append(['write',address,value])
            if address==0x40018010:
                for b,pin in enumerate((24,23,22,21,20,19)):
                    if value==1<<pin:bank[0]=b
        if access==UC_MEM_READ and 0x4000e09c<=address<=0x4000e0c4 and (address-0x4000e09c)%4==0:
            channel=(address-0x4000e09c)//4
            uc.mem_write(address,struct.pack('<I',100 if (bank[0],channel) in ready(scan[0]) else 0))
    def code(uc,address,size,data):
        minimum_sp[0]=min(minimum_sp[0],uc.reg_read(UC_ARM_REG_SP))
        if address==symbols['matrix_scan_custom']:scan[0]+=1
        if address==symbols['nova_platform_delay_original_long']:
            value=uc.reg_read(UC_ARM_REG_R0);events.append(['long_delay',value])
            uc.reg_write(UC_ARM_REG_R0,int(value!=long_failure));uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
        if address==symbols['nova_platform_delay_original_units']:
            events.append(['short_delay',uc.reg_read(UC_ARM_REG_R0)])
            uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,memory);u.hook_add(UC_HOOK_CODE,code)
    def call(name,*args):
        for reg,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1),args):u.reg_write(reg,value)
        u.reg_write(UC_ARM_REG_SP,0x20001c50);u.reg_write(UC_ARM_REG_LR,0x1ff01);u.reg_write(UC_ARM_REG_PRIMASK,1)
        u.emu_start(symbols[name]|1,0x1ff00,count=2000000)
        assert u.reg_read(UC_ARM_REG_PC)==0x1ff00
        return u.reg_read(UC_ARM_REG_R0)
    call('matrix_init_custom')
    failed=bool(u.mem_read(symbols['nova_matrix_initialization_failed'],1)[0]);assert failed==init_failure
    if init_failure:
        if long_failure==100:assert events==[['long_delay',100]]
        if long_failure==300:assert not any(e[0]=='write' and e[1]==0x4001402c for e in events)
        actual=False
    else:
        first_write=next(i for i,e in enumerate(events) if e[0]=='write')
        wait100=events.index(['long_delay',100]);wait300=events.index(['long_delay',300])
        gate=next(i for i,e in enumerate(events) if e[:2]==['write',0x4001402c])
        assert wait100<first_write<wait300<gate
        assert all(not(e[0]=='write' and 0x4000e000<=e[1]<0x4000f000) for e in events[:wait300])
        actual=bool(call('nova_emergency_hold_detected',mode,required))
    assert actual==expected and scan[0]+1==expected_scans,(name,actual,scan[0]+1)
    assert u.reg_read(UC_ARM_REG_PRIMASK)==1
    results.append({'case':name,'decision':actual,'batches':scan[0]+1,'long_delays':[e[1] for e in events if e[0]=='long_delay'],
                    'init_failure':failed,'maximum_stack_bytes':0x20001c50-minimum_sp[0],'passed':True})
test('idle bounded timeout',1,3,lambda i:set(),False,100)
test('first zero batch then held Esc',1,3,lambda i:set() if i==0 else {(0,0)},True,4)
test('fifty settling batches then Esc',2,3,lambda i:set() if i<50 else {(0,0)},True,53)
test('last three allowed batches count',2,3,lambda i:set() if i<97 else {(0,0)},True,100)
test('last two batches insufficient',2,3,lambda i:set() if i<98 else {(0,0)},False,100)
test('rotating keys never one stable hold',1,3,lambda i:{(0,1+i%2)},False,100)
test('bounce restarts consecutive count',2,3,lambda i:set() if i==1 else {(0,0)},True,5)
test('Esc policy ignores other held key',2,3,lambda i:{(0,1)},False,100)
test('absent position cannot trigger',1,3,lambda i:{(5,0)},False,100)
test('disabled policy',0,3,lambda i:{(0,0)},False,0)
test('zero required scans',1,0,lambda i:{(0,0)},False,0)
test('impossible required scans rejected',1,101,lambda i:{(0,0)},False,0)
test('retry delay failure exits',1,3,lambda i:set(),False,1,long_failure=1)
test('pre GPIO settle failure aborts',1,3,lambda i:set(),False,0,long_failure=100,init_failure=True)
test('post GPIO settle failure aborts',1,3,lambda i:set(),False,0,long_failure=300,init_failure=True)
(OUT/'result.json').write_text(json.dumps({'cases':results,'case_count':len(results),'physical_timing_verified':False,'hardware_access':False,
    'method':'Actual edited ARM matrix/acquisition/emergency C; modeled ADC values and delay callbacks. Order and bounded readiness/failure routes tested; no firmware target rebuilt.'},indent=2)+'\n')
print(f'PASS: {len(results)} corrected settling/readiness ARM cases; no firmware targets/manifests rebuilt.')
