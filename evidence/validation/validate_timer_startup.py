"""Regression: standard VIA Bootmagic waits require unmasked SysTick delivery."""
from pathlib import Path
import hashlib
import json
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.tools'))
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_PRIMASK, UC_ARM_REG_R0

path = ROOT / 'contributions/qmk_firmware/.build/ranked_nova_n60_neo2_via.elf'
elf = path.read_bytes()
nm = subprocess.check_output([str(ROOT / '.build-tools/bin/arm-none-eabi-nm.exe'), '-n', str(path)], text=True)
symbols = {p[2]: int(p[0], 16) for line in nm.splitlines() if len(p := line.split()) == 3}
results = []
for enable_interrupts in (False, True):
    u = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    for address, size in [(0, 0x20000), (0x20000000, 0x4000), (0x40000000, 0x20000), (0xe000e000, 0x2000)]:
        u.mem_map(address, size)
    phoff = struct.unpack_from('<I', elf, 28)[0]
    phsize, phnum = struct.unpack_from('<HH', elf, 42)
    for i in range(phnum):
        kind, offset, vaddr, paddr, filesz, memsz, flags, align = struct.unpack_from('<8I', elf, phoff + i * phsize)
        if kind == 1 and filesz:
            u.mem_write(vaddr, elf[offset:offset + filesz])
    state = dict(instructions=0, ticks=0, wait_entered=False)
    def code(uc, address, size, _):
        state['instructions'] += 1
        if address == symbols['wait_ms']:
            state['wait_entered'] = True
        # Model delivery eligibility, not physical interrupt entry or clock rate.
        if state['instructions'] % 256 == 0 and uc.reg_read(UC_ARM_REG_PRIMASK) == 0 and int.from_bytes(uc.mem_read(0xe000e010, 4), 'little') & 3 == 3:
            count = int.from_bytes(uc.mem_read(symbols['timer_count'], 4), 'little')
            uc.mem_write(symbols['timer_count'], struct.pack('<I', count + 1))
            state['ticks'] += 1
        if address in (symbols['nova_platform_delay_original_units'], symbols['nova_platform_delay_original_long']):
            uc.reg_write(UC_ARM_REG_R0, 1)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE, code)
    def invoke(name):
        u.reg_write(UC_ARM_REG_SP, symbols['__process_stack_end__'])
        u.reg_write(UC_ARM_REG_LR, 0x1ff01)
        u.emu_start(symbols[name] | 1, 0x1ff00, count=150000)
        return u.reg_read(UC_ARM_REG_PC) == 0x1ff00
    u.reg_write(UC_ARM_REG_PRIMASK, 1)
    assert invoke('keyboard_setup')
    if enable_interrupts:
        assert invoke('protocol_pre_init')
        assert u.reg_read(UC_ARM_REG_PRIMASK) == 0
    returned = invoke('keyboard_init')
    assert state['wait_entered']
    assert returned == enable_interrupts
    assert (state['ticks'] > 0) == enable_interrupts
    results.append(dict(interrupts_enabled=enable_interrupts, initialization_returned=returned, **state))
report = dict(passed=True, elf_sha256=hashlib.sha256(elf).hexdigest(), cases=results,
              hardware_tested=False, limitation='Models timer delivery eligibility; physical SysTick exception entry and timing remain unverified.')
(ROOT / 'contributions/timer_startup_validation.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
