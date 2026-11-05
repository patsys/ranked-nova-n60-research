"""Offline assembly + Cortex-M emulation. No USB/device access."""
from pathlib import Path
import hashlib
import json
import struct
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / '.tools'))
from keystone import Ks, KS_ARCH_ARM, KS_MODE_THUMB
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_MEM_WRITE
from unicorn.arm_const import *

BASE = 0x20000000
INFO = 0x140
SIZE = 440
DENIED = [0x24, 0x6c, 0xda, 0xfc, 0x13a]
source = (ROOT / 'diagnostic.s').read_text()
# Strip C comments, retain the named section boundaries separately.
import re
sections = re.split(r'/\* @(PROBE|DENY|INFO) \*/', source)
blocks = {sections[i]: re.sub(r'/\*.*?\*/', '', sections[i+1], flags=re.S)
          for i in range(1, len(sections), 2)}
# Keystone's ARM frontend does not accept M-profile special-register names.
# Encode Thumb MRS (Rd=r1), then verify these encodings with Capstone below.
special = dict(ipsr=5, control=20, primask=16, msp=8, psp=9)
for name, selector in special.items():
    blocks['INFO'] = blocks['INFO'].replace(
        f'mrs r1, {name}', f'.hword 0xf3ef, {0x8100 + selector}')
ks = Ks(KS_ARCH_ARM, KS_MODE_THUMB)
image = bytearray(b'\x00\xbe' * (SIZE // 2))  # BKPT in unused gaps
used = set()
listing = []
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)

def place(name, offset):
    encoded, _ = ks.asm(blocks[name], BASE + offset)
    end = offset + len(encoded)
    assert end <= SIZE and not used.intersection(range(offset, end)), 'Overlap'
    used.update(range(offset, end))
    image[offset:end] = bytes(encoded)
    listing.extend(f'{i.address:08x}: {i.mnemonic:8} {i.op_str}'
                   for i in md.disasm(bytes(encoded), BASE + offset))

place('PROBE', 0)
for offset in DENIED:
    place('DENY', offset)
place('INFO', INFO)
decoded_mrs = [i.op_str for i in md.disasm(bytes(image[INFO:]), BASE + INFO)
               if i.mnemonic == 'mrs']
assert decoded_mrs == [f'r1, {s}' for s in special], decoded_mrs

def emulate(offset, expected, info=False):
    uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    uc.mem_map(BASE, 0x4000)
    uc.mem_write(BASE, bytes(image))
    uc.mem_map(0xe000e000, 0x1000)
    uc.mem_write(0xe000ed00, struct.pack('<I', 0x410cc200))
    dest = BASE + 0x1000
    uc.mem_write(dest - 16, b'\xa5' * 80)
    uc.reg_write(UC_ARM_REG_SP, BASE + 0x3000)
    uc.reg_write(UC_ARM_REG_R0, dest)
    stop = BASE + 0x2000
    uc.reg_write(UC_ARM_REG_LR, stop | 1)
    preserved = [UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6,
                 UC_ARM_REG_R7, UC_ARM_REG_R8, UC_ARM_REG_R9,
                 UC_ARM_REG_R10, UC_ARM_REG_R11]
    for reg in preserved:
        uc.reg_write(reg, 0x12340000 + reg)
    writes = []
    uc.hook_add(UC_HOOK_MEM_WRITE,
                lambda u, a, addr, size, val, data: writes.append((addr, size)))
    uc.emu_start((BASE + offset) | 1, stop, count=200)
    assert uc.reg_read(UC_ARM_REG_PC) == stop, 'Did not return'
    assert uc.reg_read(UC_ARM_REG_R0) == expected
    assert uc.reg_read(UC_ARM_REG_SP) == BASE + 0x3000
    assert all(uc.reg_read(r) == 0x12340000 + r for r in preserved)
    if info:
        assert all(dest <= a and a+s <= dest+48 for a,s in writes)
        assert len(writes) == 12
        words = struct.unpack('<12I', uc.mem_read(dest, 48))
        assert words[:4] == (0x524f5354, 1, 48, 0x410cc200)
        assert words[4:8] == (0, 0, 0, BASE + 0x3000)
        assert words[10:] == (stop | 1, 0)
    else:
        assert not writes
    assert uc.mem_read(dest - 16, 16) == b'\xa5' * 16
    assert uc.mem_read(dest + 48, 16) == b'\xa5' * 16

emulate(0, 0x524f5354)
for offset in DENIED:
    emulate(offset, 2)
emulate(INFO, 0, True)
(ROOT / 'diagnostic.bin').write_bytes(image)
(ROOT / 'diagnostic.disasm.txt').write_text('\n'.join(listing) + '\n')
manifest = dict(load_address=hex(BASE), bytes=SIZE,
                sha256=hashlib.sha256(image).hexdigest(),
                probe_offset=0, info_offset=INFO, denied_offsets=DENIED,
                validation='7 emulated entry calls passed; no hardware test')
(ROOT / 'diagnostic.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps(manifest, indent=2))
