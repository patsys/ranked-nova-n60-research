"""Build read-LR timing probes, without data loads/stores or stack use."""
from pathlib import Path
import sys,json,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'.tools'))
from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_MEM_WRITE,UC_HOOK_CODE
from unicorn.arm_const import *
root=Path(__file__).resolve().parent
base=0x20000000
entries=[0,0x24,0x6c,0xda,0xfc,0x13a]
ks=Ks(KS_ARCH_ARM,KS_MODE_THUMB)
manifest={}
names=['cal0','cal8']+[f'lr{i}' for i in range(8)]+['xorcheck']
for name in names:
    blob=bytearray(b'\x70\x47'*220)
    for offset in entries:
        branch,_=ks.asm('b #0x20000160',base+offset)
        blob[offset:offset+2]=bytes(branch)
    if name.startswith('cal'):
        read=f'movs r0, #{name[-1]}'
    elif name=='xorcheck':
        read='mov r0, lr; mov r1, r0; lsrs r1, #16; eors r0, r1; mov r1, r0; lsrs r1, #8; eors r0, r1; mov r1, r0; lsrs r1, #4; eors r0, r1; movs r1, #15; ands r0, r1'
    else:
        shift=4*int(name[-1])
        read='mov r0, lr; '+(f'lsrs r0, #{shift}; ' if shift else '')+'movs r1, #15; ands r0, r1'
    source=read+'''
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
    assert 0x160+len(code)<=440
    blob[0x160:0x160+len(code)]=bytes(code)
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS)
    decoded=list(md.disasm(bytes(blob),base))
    assert sum(i.size for i in decoded)==440
    assert all(i.mnemonic in ['b','bx','movs','mov','lsrs','eors','ands','cmp','beq','lsls','subs','bne'] for i in decoded)
    for offset in entries:
        uc=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
        uc.mem_map(base,0x1000)
        uc.mem_write(base,bytes(blob))
        stop=base+0x800
        uc.reg_write(UC_ARM_REG_LR,stop|1)
        writes=[]
        sampled=[]
        uc.hook_add(UC_HOOK_MEM_WRITE,lambda *args:writes.append(args))
        cmp_address=next(i.address for i in decoded if i.mnemonic=='cmp')
        uc.hook_add(UC_HOOK_CODE,lambda u,a,s,d:sampled.append(u.reg_read(UC_ARM_REG_R0)),begin=cmp_address,end=cmp_address)
        uc.emu_start((base+offset)|1,stop,count=8500000)
        assert uc.reg_read(UC_ARM_REG_PC)==stop and uc.reg_read(UC_ARM_REG_R0)==0 and not writes
        assert uc.reg_read(UC_ARM_REG_LR)==stop|1
        value=stop|1
        expected=(int(name[-1]) if name.startswith('cal') else
                  __import__('functools').reduce(int.__xor__,[(value>>s)&15 for s in range(0,32,4)],0)
                  if name=='xorcheck' else (value>>(4*int(name[-1])))&15)
        assert sampled==[expected],(name,sampled,expected)
    stem='probe_'+name
    (root/f'{stem}.bin').write_bytes(blob)
    (root/f'{stem}.disasm.txt').write_text('\n'.join(f'{i.address:08x}: {i.mnemonic} {i.op_str}' for i in decoded))
    manifest[name]=dict(file=f'readonly_stub/{stem}.bin',sha256=hashlib.sha256(blob).hexdigest(),emulated_calls=6)
(root/'lr_probes.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(dict(probes=len(manifest),emulated_calls=6*len(manifest)),indent=2))
