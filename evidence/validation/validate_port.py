"""Offline checks of the actual standard-QMK-build ELFs; no device access."""
from pathlib import Path
import hashlib
import json
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.tools'))
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_MEM_READ, UC_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_SP, UC_ARM_REG_PC, UC_ARM_REG_LR, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3

Q = ROOT / 'contributions/qmk_firmware'
NM = ROOT / '.build-tools/bin/arm-none-eabi-nm.exe'
results = []
for target in ['ranked_nova_n60_default', 'handwired_onekey_ry7203_default']:
    path = Q / '.build' / (target + '.elf')
    elf = path.read_bytes()
    symbols = {}
    data_symbols = {}
    for line in subprocess.check_output([str(NM), '-n', str(path)], text=True).splitlines():
        fields = line.split()
        if len(fields) == 3:
            symbols[fields[2]] = int(fields[0], 16)
            if fields[1] == 'd':
                data_symbols[fields[2]] = int(fields[0], 16)
    header = struct.unpack_from('<16sHHIIIIIHHHHHH', elf)
    flash = bytearray(b'\xff' * 0x20000)
    loads = []
    for i in range(header[10]):
        kind, offset, vaddr, paddr, filesz, memsz, flags, align = struct.unpack_from('<8I', elf, header[5] + i * header[9])
        if kind != 1:
            continue
        if filesz:
            assert 0x2000 <= paddr and paddr + filesz <= 0x1a000
            flash[paddr:paddr + filesz] = elf[offset:offset + filesz]
        if 0x20000000 <= vaddr:
            assert vaddr + memsz <= 0x20001c50
        loads.append((offset, vaddr, paddr, filesz, memsz))
    vectors = struct.unpack_from('<40I', flash, 0x2000)
    assert vectors[1] == header[4]
    assert vectors[15] == symbols['SysTick_Handler'] | 1
    assert vectors[20] == symbols['Vector50'] | 1
    u = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    for address, size in [(0, 0x20000), (0x20000000, 0x4000), (0x40000000, 0x20000), (0xe000e000, 0x2000)]:
        u.mem_map(address, size)
    u.mem_write(0, bytes(flash))
    u.mem_write(0x20000000, b'\xa5' * 0x4000)
    reached = []
    def stop_startup(uc, address, size, _):
        if address == symbols['main']:
            reached.append(address)
            uc.emu_stop()
    startup_hook = u.hook_add(UC_HOOK_CODE, stop_startup)
    u.reg_write(UC_ARM_REG_SP, 0x20001c50)
    u.emu_start(header[4], 0, count=50000)
    assert reached
    u.hook_del(startup_hook)
    assert u.mem_read(symbols['__bss_base__'], symbols['__bss_end__'] - symbols['__bss_base__']) == bytes(symbols['__bss_end__'] - symbols['__bss_base__'])
    for offset, vaddr, paddr, filesz, memsz in loads:
        if vaddr == symbols['__data_base__']:
            assert u.mem_read(vaddr, filesz) == elf[offset:offset + filesz]

    pressed = set()
    selected = 0
    minimum_stack = symbols['__process_stack_end__']
    def registers(uc, access, address, size, value, _):
        global selected
        if access == UC_MEM_WRITE and address == 0x40018010:
            for bank, pin in enumerate([24, 23, 22, 21, 20, 19]):
                if value == 1 << pin:
                    selected = bank
        if access == UC_MEM_READ and 0x4000e09c <= address <= 0x4000e0c4 and (address - 0x4000e09c) % 4 == 0:
            channel = (address - 0x4000e09c) // 4
            uc.mem_write(address, struct.pack('<I', 100 if (selected, channel) in pressed else 0))
    u.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, registers, begin=0x40000000, end=0x4001ffff)
    def runtime(uc, address, size, _):
        global minimum_stack
        minimum_stack = min(minimum_stack, uc.reg_read(UC_ARM_REG_SP))
        if address == symbols['nova_platform_delay_original_units']:
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        elif address == symbols['nova_platform_delay_original_long']:
            uc.reg_write(UC_ARM_REG_R0, 1)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE, runtime)
    def invoke(name, *args):
        for reg, value in zip([UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3], args):
            u.reg_write(reg, value)
        stack_args = max(0, len(args) - 4) * 4
        call_sp = symbols['__process_stack_end__'] - ((stack_args + 7) & ~7)
        u.reg_write(UC_ARM_REG_SP, call_sp)
        for i, value in enumerate(args[4:]):
            u.mem_write(call_sp + 4*i, struct.pack('<I', value))
        u.reg_write(UC_ARM_REG_LR, 0x1ff01)
        try:
            u.emu_start(symbols[name] | 1, 0x1ff00, count=400000)
        except Exception:
            print('Emulator failure', name, 'pc', hex(u.reg_read(UC_ARM_REG_PC)), 'lr', hex(u.reg_read(UC_ARM_REG_LR)), 'sp', hex(u.reg_read(UC_ARM_REG_SP)))
            raise
        assert u.reg_read(UC_ARM_REG_PC) == 0x1ff00, (name, hex(u.reg_read(UC_ARM_REG_PC)))
    length_ptr = symbols['__heap_base__'] + 32
    assert length_ptr + 2 < symbols['__heap_end__']
    expected_product = 'Ranked Nova N60' if target.startswith('ranked') else 'RY7203 Nova one-key test'
    expected_manufacturer = 'Ranked' if target.startswith('ranked') else 'QMK'
    for index, expected in [(1, expected_manufacturer), (2, expected_product)]:
        invoke('descriptor', 0, 3, index, 0x409, length_ptr)
        length = int.from_bytes(u.mem_read(length_ptr, 2), 'little')
        ptr = u.reg_read(UC_ARM_REG_R0)
        descriptor = bytes(u.mem_read(ptr, length))
        assert descriptor[:2] == bytes([length, 3])
        assert descriptor[2:].decode('utf-16-le') == expected
    invoke('keyboard_setup')
    invoke('keyboard_init')
    assert u.mem_read(symbols['nova_matrix_initialization_failed'], 1) == b'\0'
    invoke('host_set_driver', data_symbols['driver'])
    invoke('usb_device_state_set_configuration', 1, 1)
    invoke('usb_device_state_set_protocol', 0)
    now = 0
    cases = []
    def check(name, positions, mods, usages):
        global pressed, now
        pressed = set(positions)
        for _ in range(12):
            now += 1
            u.mem_write(symbols['timer_count'], struct.pack('<I', now))
            invoke('keyboard_task')
        report = bytes(u.mem_read(symbols['latest_report'], 8))
        assert report[0] == mods and set(report[2:]) - {0} == set(usages), (name, report.hex(), mods, usages)
        cases.append(name)
    check('released', [], 0, [])
    if target.startswith('handwired'):
        check('esc_reports_a', [(0, 0)], 0, [4])
        check('unmapped_sensor_is_silent', [(2, 9)], 0, [])
    else:
        # Independently enumerate base-map HID usages, including all row ends.
        banks = [list(range(0x29, 0x2a)) + list(range(0x1e, 0x28)),
                 [0x2b,0x14,0x1a,8,0x15,0x17,0x1c,0x18,0xc,0x12,0x13],
                 [0x39,4,0x16,7,9,0xa,0xb,0xd,0xe,0xf,0x33],
                 [0xe1,0x64,0x1d,0x1b,6,0x19,5,0x11,0x10,0x36,0x37],
                 [0xe0,0xe3,0xe2,0x2c,0xe6,None,None,0xe4,0x38,None,0xe5],
                 [None,0x2d,0x2e,0x2a,0x2f,0x30,None,0x34,0x32,0x28,None]]
        for bank, row in enumerate(banks):
            for channel, usage in enumerate(row):
                if usage is None:
                    continue
                mods = 1 << (usage - 0xe0) if usage >= 0xe0 else 0
                check(f'key_{bank}_{channel}', [(bank, channel)], mods, [] if mods else [usage])
                check(f'release_{bank}_{channel}', [], 0, [])
        check('fn1_held', [(4,5)], 0, [])
        check('fn1_f1', [(4,5),(0,1)], 0, [0x3a])
        check('fn2_held', [(4,6)], 0, [])
        check('fn2_f1', [(4,6),(0,1)], 0, [0x3a])
        check('both_fn_held', [(4,5),(4,6)], 0, [])
        check('both_fn_f1', [(4,5),(4,6),(0,1)], 0, [0x3a])
        check('release_fn_and_number', [], 0, [])
        check('shift_one', [(3,0),(0,1)], 2, [0x1e])
        check('ctrl_shift_one', [(4,0),(3,0),(0,1)], 3, [0x1e])
    check('final_release', [], 0, [])
    assert minimum_stack >= symbols['__process_stack_base__']
    result = dict(target=target, elf_sha256=hashlib.sha256(elf).hexdigest(), passed=True,
                  startup_reached_main=True, cases=len(cases), process_stack_used_bytes=symbols['__process_stack_end__']-minimum_stack,
                  hardware_tested=False, installed=False,
                  limitations='Synthetic ADC samples and milliseconds; delay helpers intercepted. No physical USB, timing, platform setup or flash test.')
    results.append(result)
    print(json.dumps(result))
(ROOT / 'contributions/port_validation.json').write_text(json.dumps(results, indent=2)+'\n')
