"""Offline execution of original clock setup; no peripheral hardware model."""
from pathlib import Path
import hashlib, json, struct, sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.tools'))
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_R0, UC_ARM_REG_PC

image = (ROOT / 'firmware_dump/flash_cpu_pass1.bin').read_bytes()

def trace(entry, seed, argument=0, compiled_blob=None):
    uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    uc.mem_map(0, 0x20000); uc.mem_write(0, image)
    if compiled_blob is not None: uc.mem_write(0x18000, compiled_blob)
    uc.mem_map(0x20000000, 0x10000)
    uc.mem_map(0x40014000, 0x1000)
    for offset in range(0, 0x100, 4):
        uc.mem_write(0x40014000 + offset, struct.pack('<I', seed))
    uc.reg_write(UC_ARM_REG_SP, 0x20002000)
    uc.reg_write(UC_ARM_REG_LR, 0x1ff01)
    uc.reg_write(UC_ARM_REG_R0, argument)
    writes = []; stopped = []
    def code(u, address, size, data):
        if address == 0x1ff00:
            stopped.append(True); u.emu_stop()
    def write(u, access, address, size, value, data):
        if address >= 0x40000000:
            assert 0x40014000 <= address < 0x40014100 and size == 4
            writes.append([address, value])
    uc.hook_add(UC_HOOK_CODE, code); uc.hook_add(UC_HOOK_MEM_WRITE, write)
    uc.emu_start(entry | 1, 0, count=1000)
    assert stopped
    return writes

def setup_expected(seed):
    result = [[0x40014028, 0], [0x40014060, seed | 2]]
    v = seed | 0x1000000
    result += [[0x40014050, v], [0x4001404c, 0]]
    for mask, value in [(0x1f, 0x11), (0, 0x1000000),
                        (0xe0, 0x40), (0x1f00, 0x1100),
                        (0, 0x1000000), (0xe000, 0x4000)]:
        v = (v & ~mask) | value
        result.append([0x40014050, v])
    return result

def main():
    cases = []
    for seed in [0, 0xffffffff, 0xaaaaaaaa, 0x55555555, 0x12345678]:
        writes = trace(0xd5f0, seed)
        assert writes == setup_expected(seed)
        cases.append(dict(entry='0xd5f0', initial_register_value=seed, writes=writes))
        for argument in [0, 2, 0xffffffff]:
            writes = trace(0xd57c, seed, argument)
            assert writes == [[0x40014050, seed | 0x1000000], [0x4001404c, argument]]
            cases.append(dict(entry='0xd57c', initial_register_value=seed,
                              argument=argument, writes=writes))
    report = dict(source_sha256=hashlib.sha256(image).hexdigest(),
                  method='Actual original machine-code execution; synthetic RAM-like MMIO contents; no clock physics emulated',
                  cases_passed=len(cases), cases=cases)
    path = ROOT / 'firmware_dump/clock_offline_traces.json'
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f'{len(cases)} original-code register-sequence cases passed; {path}')
    build = ROOT/'qmk_port/build'
    if (build/'clock_validation.bin').exists():
        blob = (build/'clock_validation.bin').read_bytes()
        symbols = {}
        for line in (build/'clock_validation.nm').read_text().splitlines():
            fields = line.split()
            if len(fields) == 3: symbols[fields[2]] = int(fields[0], 16)
        for case in cases:
            name = 'nova_original_clock_setup' if case['entry'] == '0xd5f0' else 'nova_original_domain_select'
            observed = trace(symbols[name], case['initial_register_value'],
                             case.get('argument', 0), compiled_blob=blob)
            assert observed == case['writes'], (name, case, observed)
        result = dict(cases_passed=len(cases), compiled_blob_sha256=hashlib.sha256(blob).hexdigest(),
                      comparison='Actual GCC ARM output versus actual original firmware instructions; ordered MMIO writes match',
                      caveat='MMIO is synthetic memory; no oscillator/clock hardware behavior is modeled')
        (build/'clock_compiled_comparison.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(f'{len(cases)} compiled-C versus original-code cases passed')

if __name__ == '__main__': main()
