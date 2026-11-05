"""No-store challenge handler for the vendor's inferred programming ABI."""
from pathlib import Path
import sys
import json
import hashlib
timed = '--timed' in sys.argv
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / '.tools'))
from keystone import Ks, KS_ARCH_ARM, KS_MODE_THUMB
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_MEM_WRITE
from unicorn.arm_const import *

root = Path(__file__).resolve().parent
base = 0x20000000
ks = Ks(KS_ARCH_ARM, KS_MODE_THUMB)
blob = bytearray(b'\x70\x47' * 220)
for offset in [0, 0x24, 0xda, 0x13a]:
    blob[offset:offset+4] = b'\x00\x20\x70\x47'  # success, no operation
code = '''
    mov r2, r1
    lsrs r2, r2, #16
    movs r3, #0x20
    lsls r3, r3, #8
    cmp r2, r3
    bne denied
    ldrb r0, [r1]
    movs r2, #1
    ands r0, r2
    TIMING
    adds r0, #2
    bx lr
denied:
    movs r0, #2
    bx lr
'''
code = code.replace('TIMING', '''
    cmp r0, #0
    beq timing_done
    movs r2, #1
    lsls r2, r2, #20
delay_loop:
    subs r2, #1
    bne delay_loop
timing_done:
''' if timed else '')
encoded, _ = ks.asm(code, base + 0x6c)
blob[0x6c:0x6c+len(encoded)] = bytes(encoded)
alternate, _ = ks.asm('mov r1, r0; b #0x2000006c', base + 0xfc)
blob[0xfc:0xfc+len(alternate)] = bytes(alternate)
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
instructions = list(md.disasm(bytes(blob), base))
assert sum(i.size for i in instructions) == 440
assert all(i.mnemonic in ['bx','movs','mov','lsrs','lsls','cmp','bne','ldrb','ands','adds','b']
           for i in instructions if i.mnemonic not in ['beq','subs']), 'Unexpected instruction'
checks = 0
for offset in [0, 0x24, 0x6c, 0xda, 0xfc, 0x13a]:
    for pointer in [0, 0x40013000, base+0x1000]:
        for challenge in [0, 1]:
            uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
            uc.mem_map(base, 0x3000)
            uc.mem_write(base, bytes(blob))
            uc.mem_write(base+0x1000, bytes([challenge]))
            uc.reg_write(UC_ARM_REG_R0, pointer if offset == 0xfc else 0)
            uc.reg_write(UC_ARM_REG_R1, pointer)
            uc.reg_write(UC_ARM_REG_LR, (base+0x2000) | 1)
            writes=[]
            uc.hook_add(UC_HOOK_MEM_WRITE, lambda *args: writes.append(args))
            uc.emu_start((base+offset)|1, base+0x2000, count=2200000 if timed else 30)
            assert uc.reg_read(UC_ARM_REG_PC) == base+0x2000 and not writes
            expected = (2 + challenge if pointer == base+0x1000 else 2) if offset in [0x6c,0xfc] else 0
            assert uc.reg_read(UC_ARM_REG_R0) == expected
            checks += 1
stem = 'timing' if timed else 'echo'
(root/f'{stem}.bin').write_bytes(blob)
(root/f'{stem}.disasm.txt').write_text('\n'.join(f'{i.address:08x}: {i.mnemonic} {i.op_str}' for i in instructions))
manifest=dict(sha256=hashlib.sha256(blob).hexdigest(),bytes=440,checks=checks,
              operation='No-store handler returns 2+(RAM[source]&1); inferred vendor ABI')
(root/f'{stem}.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest,indent=2))
