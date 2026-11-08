"""Build a no-load/no-store probe and test every halfword entry offline."""
from pathlib import Path
import sys
import json
import hashlib
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / '.tools'))
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_LR, UC_ARM_REG_PC

root = Path(__file__).resolve().parent
base = 0x20000000
entries = [0, 0x24, 0x6c, 0xda, 0xfc, 0x13a]
blob = bytearray(b'\x70\x47' * 220)  # bx lr at every unused halfword
for offset in entries:
    blob[offset:offset+4] = b'\x03\x20\x70\x47'  # movs r0,#3; bx lr
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
decoded = list(md.disasm(bytes(blob), base))
assert sum(i.size for i in decoded) == len(blob)
assert all(i.mnemonic in ('movs', 'bx') for i in decoded)
for offset in range(0, len(blob), 2):
    uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    uc.mem_map(base, 0x1000)
    uc.mem_write(base, bytes(blob))
    stop = base + 0x800
    uc.reg_write(UC_ARM_REG_LR, stop | 1)
    uc.reg_write(UC_ARM_REG_R0, 0x12345678)
    writes = []
    uc.hook_add(UC_HOOK_MEM_WRITE, lambda *args: writes.append(args))
    uc.emu_start((base + offset) | 1, stop, count=3)
    assert not writes and uc.reg_read(UC_ARM_REG_PC) == stop
    if offset in entries:
        assert uc.reg_read(UC_ARM_REG_R0) == 3
(root / 'stateless.bin').write_bytes(blob)
manifest = dict(bytes=len(blob), sha256=hashlib.sha256(blob).hexdigest(),
                return_code=3, entries=entries, emulated_entries=220,
                instructions=['movs r0, #3', 'bx lr'])
(root / 'stateless.json').write_text(json.dumps(manifest, indent=2))
print(json.dumps(manifest, indent=2))
