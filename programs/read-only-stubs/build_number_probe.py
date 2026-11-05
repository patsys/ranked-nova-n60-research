"""Build register-only timing outputs: calibration 0/1 and computed number 7."""
from pathlib import Path
import sys,json,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'.tools'))
from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_MEM_WRITE
from unicorn.arm_const import *
root=Path(__file__).resolve().parent
base=0x20000000
entries=[0,0x24,0x6c,0xda,0xfc,0x13a]
ks=Ks(KS_ARCH_ARM,KS_MODE_THUMB)
manifest={}
for name,value in [('zero',0),('unit',1),('computed',7)]:
    blob=bytearray(b'\x70\x47'*220)
    for offset in entries:
        branch,_=ks.asm('b #0x20000160',base+offset)
        blob[offset:offset+2]=bytes(branch)
    calculate='movs r0, #0x12; movs r1, #0x15; eors r0, r1' if name=='computed' else f'movs r0, #{value}'
    source=calculate+'''
        cmp r0, #0
        beq done
        lsls r0, r0, #18
    loop:
        subs r0, #1
        bne loop
    done:
        movs r0, #0
        bx lr
    '''
    code,_=ks.asm(source,base+0x160)
    blob[0x160:0x160+len(code)]=bytes(code)
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS)
    decoded=list(md.disasm(bytes(blob),base))
    assert sum(i.size for i in decoded)==440
    assert all(i.mnemonic in ['b','bx','movs','eors','cmp','beq','lsls','subs','bne'] for i in decoded)
    for offset in entries:
        uc=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
        uc.mem_map(base,0x1000)
        uc.mem_write(base,bytes(blob))
        uc.reg_write(UC_ARM_REG_LR,(base+0x800)|1)
        writes=[]
        uc.hook_add(UC_HOOK_MEM_WRITE,lambda *args:writes.append(args))
        uc.emu_start((base+offset)|1,base+0x800,count=4000000)
        assert uc.reg_read(UC_ARM_REG_PC)==base+0x800 and uc.reg_read(UC_ARM_REG_R0)==0 and not writes
    stem='number_'+name
    (root/f'{stem}.bin').write_bytes(blob)
    (root/f'{stem}.disasm.txt').write_text('\n'.join(f'{i.address:08x}: {i.mnemonic} {i.op_str}' for i in decoded))
    manifest[stem]=dict(sha256=hashlib.sha256(blob).hexdigest(),encoded_number=value,
                        delay_iterations=value*(1<<18),emulated_calls=6)
(root/'number_probes.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest,indent=2))
