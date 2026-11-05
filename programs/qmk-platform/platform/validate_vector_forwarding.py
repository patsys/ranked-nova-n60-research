"""Original boot exception dispatch, synthetic IPSR only, no real hardware."""
from pathlib import Path
import sys, struct, json
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.tools'))
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_IPSR
image=(ROOT/'firmware_dump/flash_cpu_pass1.bin').read_bytes()
cases=[]
for index in [2,3,11,14,15,*range(16,38)]:
    u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
    u.mem_map(0,0x20000);u.mem_write(0,image)
    target=struct.unpack_from('<I',image,0x2000+4*index)[0]&~1
    assert target
    u.reg_write(UC_ARM_REG_IPSR,index);seen=[]
    def code(uc,address,size,data):
        if address==target:seen.append(address);uc.emu_stop()
    u.hook_add(UC_HOOK_CODE,code);u.emu_start(0x1df,0,count=20)
    assert seen==[target],(index,hex(target),seen)
    cases.append(dict(exception=index,forwarded_to=hex(target)))
report=dict(method='Actual boot dispatch with synthetic IPSR, stopped at app handler; no actual hardware exceptions triggered',cases_passed=len(cases),cases=cases)
(ROOT/'firmware_dump/vector_forwarding_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(len(cases),'fixed-vector forwarding cases passed')
