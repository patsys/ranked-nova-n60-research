"""Offline extraction of original analog scan tables and RAM pin configuration bases."""
from pathlib import Path
import hashlib, json, struct, sys
sys.path.insert(0, str(Path(__file__).resolve().parent / '.tools'))
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS
from unicorn.arm_const import UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2

root = Path(__file__).resolve().parent
flash = (root / 'firmware_dump/flash_cpu_pass1.bin').read_bytes()
assert hashlib.sha256(flash).hexdigest() == '5adca278d90a0672e05dfe5ad47d1635242f9ec0ff78827d83d9f28d6ccd8b49'
u = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
u.mem_map(0, 0x20000)
u.mem_write(0, flash)
u.mem_map(0x20000000, 0x10000)
u.reg_write(UC_ARM_REG_SP, 0x2000f000)
u.reg_write(UC_ARM_REG_LR, 0x1ff01)
# Exact first scatter-load record at 0x10614; no peripheral mappings exist.
for register, value in ((UC_ARM_REG_R0, 0x10644), (UC_ARM_REG_R1, 0x20000000), (UC_ARM_REG_R2, 0x554)):
    u.reg_write(register, value)
u.emu_start(0x22a9, 0x1ff00, count=100000)
pins = list(flash[0xf61a:0xf620])
channels = list(flash[0xf60f:0xf61a])
key_ids = [list(flash[0xf660 + 6*c:0xf666 + 6*c]) for c in range(11)]
result = {
    'source_sha256': hashlib.sha256(flash).hexdigest(),
    'method': 'Offline original scatter decompressor execution and literal table extraction; no hardware access',
    'scan_routine': '0x4cb0',
    'bank_pins_encoded': pins,
    'analog_pin_codes': list(flash[0xf620:0xf62b]),
    'result_channels': channels,
    'pin_config_bases': [hex(v) for v in struct.unpack('<4I', u.mem_read(0x20000458, 16))],
    'logical_key_ids_by_channel_then_bank': key_ids,
    'skip_id': 1,
    'populated_positions': sum(value != 1 for row in key_ids for value in row),
    'caveat': 'Encoded GPIO identifiers are not package pin numbers; register names and electrical polarity require further verification.'
}
(root / 'firmware_dump/key_scan_tables.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, indent=2))
