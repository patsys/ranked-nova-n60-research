"""Offline bounded stock stub v2: last valid page releases DATA state for readback.
Keeps v1 artifact unchanged. No real hardware is accessed.
"""
from pathlib import Path
import runpy,sys,struct,json,hashlib,contextlib,io
ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent
with contextlib.redirect_stdout(io.StringIO()):g=runpy.run_path(str(OUT/'build_bounded_stub.py'))
stub=g['stub'];asm=g['asm']
# Program prologue is already pushed32bytes before this branch. Native outer
# localactive[outerSP+8] is therefore[SP+40]. Only accepted lastpage132 clears it.
asm(0x110,'b #0x2000012c',2)
asm(0x12c,'''
    cmp r0,#132
    bne #0x20000070
    movs r2,#0
    str r2,[sp,#40]
    b #0x20000070
''',10)
stub[0x136:0x13a]=b'\x00\xde'*2
binary=OUT/'bounded_stock_stub_v2.bin';binary.write_bytes(stub)
cs=g['cs'];BASE=g['BASE']
(OUT/'bounded_stock_stub_v2.disasm.txt').write_text('\n'.join(f'{i.address:08x} {i.bytes.hex():12s} {i.mnemonic:8s} {i.op_str}' for i in cs.disasm(bytes(stub),BASE)))
cases=[]
for old in g['cases']:
    cases.append(g['case'](int(old['entry'],16),page=old['page'],length=old['length'],context=int(old['context'],16),source=int(old['source'],16)))
# Trace the extra state write independently of all ordinary push/pop RAM stores.
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_MEM_WRITE
from unicorn.arm_const import *
stack_cases=[]
for page in (16,131,132,133):
    for bad_source in (False,True):
        u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
        for a,n in [(0,0x20000),(BASE,0x10000),(0x40013000,0x1000)]:u.mem_map(a,n)
        u.mem_write(0,g['flash']);u.mem_write(BASE,g['ram']);u.mem_write(BASE,bytes(stub))
        u.mem_write(0x20000754,struct.pack('<III',0x5a5a5a5a,0xa5a5a5a5,0x5555aaaa))
        u.mem_write(g['CTX']+4,struct.pack('<H',512));u.mem_write(g['SRC'],b'\xa5'*512)
        initial_sp=0x2000f000;u.mem_write(initial_sp+8,struct.pack('<I',1))
        for reg,v in [(UC_ARM_REG_SP,initial_sp),(UC_ARM_REG_LR,0x1ff01),(UC_ARM_REG_R0,page),(UC_ARM_REG_R1,g['SRC']+(4 if bad_source else 0)),(UC_ARM_REG_R4,g['CTX'])]:u.reg_write(reg,v)
        writes=[]
        def write(u,x,a,s,v,_):
            if initial_sp<=a<BASE+0x10000:writes.append({'address':hex(a),'size':s,'value':v,'pc':hex(u.reg_read(UC_ARM_REG_PC))})
        u.hook_add(UC_HOOK_MEM_WRITE,write);u.emu_start(BASE+0x6d,0x1ff00,count=100000)
        expected=[{'address':hex(initial_sp+8),'size':4,'value':0,'pc':'0x20000132'}] if page==132 and not bad_source else []
        assert writes==expected,(page,bad_source,writes)
        stack_cases.append({'page':page,'invalid_source':bad_source,'outer_local_writes':writes,'passed':True})
xor=0
for v in struct.unpack('<110I',stub):xor^=v
result={'passed':True,'byte_length':440,'sha256':hashlib.sha256(stub).hexdigest(),'xor32':hex(xor),'v1_sha256':g['result']['sha256'],'valid_page_operations':234,'cases':cases,'last_page_handoff':'Only afterpage16..132/context/512bytes/sourceguards andoriginalprogram32-byteprologue, lastpage132 writeszero to nativeouteractive[SP+8] via currentSP+40. Allowsread-onlySTARTafterlastDATAwithoutCOMPLETE/appjump.','stack_write_cases':stack_cases,'model':'Original vendor operationbodies/nativehelpers andRAM-likeMMIO. No mocked functionreturns. Physicalflashbehaviornotverified. Native117pageprotocolintegration is a separate requiredtest.'}
(OUT/'bounded_stock_stub_v2_validation.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k not in ('cases','stack_write_cases')},indent=2))
