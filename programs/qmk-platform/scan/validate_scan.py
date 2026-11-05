"""Offline evidence checks; runs the actual recovered acquisition routine."""
from pathlib import Path
import json, re, struct, sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.tools'))
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

flash = (ROOT / 'firmware_dump/flash_cpu_pass1.bin').read_bytes()
tables = json.loads((ROOT / 'firmware_dump/key_scan_tables.json').read_text())
source = Path(__file__).with_name('recovered_scan.c').read_text()
def values(name):
    body = re.search(r'const [^;]+\b' + name + r'\[[^=]+?=\s*\{(.*?)\};', source, re.S).group(1)
    return [int(x, 0) for x in re.findall(r'0x[0-9a-f]+|\b\d+\b', body)]
assert values('ranked_bank_pin_codes') == list(flash[0xf61a:0xf620])
assert values('ranked_channel_pin_codes') == list(flash[0xf620:0xf62b])
assert values('ranked_original_key_ids') == list(flash[0xf660:0xf6a2])
assert values('ranked_pin_config_bases') == [int(x,16) for x in tables['pin_config_bases']]

cases = []
for sample in (0, 19, 20, 25, 30, 31, 65535):
    for initial in (0, 63):
        u = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        u.mem_map(0, 0x20000); u.mem_write(0, flash)
        u.mem_map(0x20000000, 0x10000)
        u.mem_write(0x20000000, (ROOT / 'firmware_dump/startup_ram_20000000.bin').read_bytes())
        u.mem_map(0x40000000, 0x20000)
        for channel in range(11):
            u.mem_write(0x4000e09c + 4*channel, struct.pack('<I',sample))
            u.mem_write(0x20000bae + 2*channel,struct.pack('<H',initial))
        # The original delay helper depends on clocks and timer loops. Replacing
        # only this helper avoids pretending the offline MMIO model has timing.
        def code_hook(uc, address, size, data):
            if address == 0xdde8:
                uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        u.hook_add(UC_HOOK_CODE, code_hook)
        u.reg_write(UC_ARM_REG_SP, 0x2000f000)
        u.reg_write(UC_ARM_REG_LR, 0x1ff01)
        u.emu_start(0x4cb1, 0x1ff00, count=50000)
        assert u.reg_read(UC_ARM_REG_PC) == 0x1ff00
        for channel, row in enumerate(tables['logical_key_ids_by_channel_then_bank']):
            expected = initial
            for bank,key in enumerate(row):
                if key == 1: continue
                if sample > 30: expected |= 1 << bank
                elif sample < 20: expected &= ~(1 << bank)
                stored = struct.unpack('<H',u.mem_read(0x20000b2a+22*bank+2*channel,2))[0]
                assert stored == sample
            actual = struct.unpack('<H',u.mem_read(0x20000bae+2*channel,2))[0]
            assert actual == expected, (sample,initial,channel,actual,expected)
        count = u.mem_read(0x200002d0,1)[0]
        assert count == (62 if sample > 30 else 0)
        cases.append({'sample':sample,'initial_bank_bits':initial,'active_position_count':count,'passed':True})
result = {'tables_match_original':True,'original_routine_emulation_cases':cases,
          'limitations':'Offline MMIO storage model; delay helper bypassed. Does not validate physical timing, electrical behavior or C machine code.'}
Path(__file__).with_name('validation.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS: C table constants match original; 14 original-routine sample/hysteresis cases passed.')
