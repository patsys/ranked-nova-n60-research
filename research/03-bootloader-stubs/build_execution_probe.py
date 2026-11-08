"""Build argument-independent immediate/delayed no-store execution probes."""
from pathlib import Path
import sys
import hashlib
import json
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'.tools'))
from keystone import Ks, KS_ARCH_ARM, KS_MODE_THUMB
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_MEM_WRITE
from unicorn.arm_const import *

root=Path(__file__).resolve().parent
base=0x20000000
entries=[0,0x24,0x6c,0xda,0xfc,0x13a]
ks=Ks(KS_ARCH_ARM,KS_MODE_THUMB)
manifest={}
for power in [0,18]:
    blob=bytearray(b'\x70\x47'*220)
    for offset in entries:
        branch,_=ks.asm('b #0x20000160',base+offset)
        assert len(branch)==2
        blob[offset:offset+2]=bytes(branch)
    source=('movs r0, #0; bx lr' if power==0 else '''
        movs r0, #1
        lsls r0, r0, #18
    again:
        subs r0, #1
        bne again
        bx lr
    ''')
    code,_=ks.asm(source,base+0x160)
    blob[0x160:0x160+len(code)]=bytes(code)
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS)
    instructions=list(md.disasm(bytes(blob),base))
    assert sum(i.size for i in instructions)==440
    assert all(i.mnemonic in ['b','bx','movs','lsls','subs','bne'] for i in instructions)
    for offset in entries:
        uc=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
        uc.mem_map(base,0x1000)
        uc.mem_write(base,bytes(blob))
        stop=base+0x800
        uc.reg_write(UC_ARM_REG_LR,stop|1)
        uc.reg_write(UC_ARM_REG_R0,0xffffffff)
        writes=[]
        uc.hook_add(UC_HOOK_MEM_WRITE,lambda *args:writes.append(args))
        uc.emu_start((base+offset)|1,stop,count=600000)
        assert uc.reg_read(UC_ARM_REG_PC)==stop
        assert uc.reg_read(UC_ARM_REG_R0)==0 and not writes
    name=f'execution_{power}'
    (root/f'{name}.bin').write_bytes(blob)
    (root/f'{name}.disasm.txt').write_text('\n'.join(f'{i.address:08x}: {i.mnemonic} {i.op_str}' for i in instructions))
    manifest[name]=dict(sha256=hashlib.sha256(blob).hexdigest(),loop_iterations=2**power if power else 0,
                        entries=entries,bytes=440,emulated_calls=6)
(root/'execution_probes.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest,indent=2))
