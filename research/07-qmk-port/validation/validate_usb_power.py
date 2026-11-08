"""Compile and execute controller power transitions offline; no USB access."""
from pathlib import Path
import hashlib
import json
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.tools'))
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS
from unicorn.arm_const import UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_R0, UC_ARM_REG_PC

folder = ROOT / 'contributions'
driver = folder / 'qmk_firmware/platforms/ry72xx/usb'
target = folder / 'usb_power_test.elf'
subprocess.run([str(ROOT / '.build-tools/bin/arm-none-eabi-gcc.exe'),
    '-mcpu=cortex-m0', '-mthumb', '-Os', '-fno-builtin', '-nostdlib',
    '-Wl,-e,test', '-Wl,-Ttext=0x2000', '-Wl,-Tdata=0x20000000',
    '-I', str(driver), str(folder / 'usb_power_test.c'),
    str(driver / 'ranked_usb_device.c'), str(driver / 'ranked_usb_io.c'),
    '-lgcc', '-o', str(target)], check=True)
elf = target.read_bytes()
header = struct.unpack_from('<16sHHIIIIIHHHHHH', elf)
u = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
u.mem_map(0, 0x20000)
u.mem_map(0x20000000, 0x2000)
for i in range(header[10]):
    kind, offset, vaddr, paddr, filesz, memsz, flags, align = struct.unpack_from(
        '<8I', elf, header[5] + i * header[9])
    if kind == 1 and filesz:
        u.mem_write(vaddr, elf[offset:offset + filesz])
u.reg_write(UC_ARM_REG_SP, 0x20001c00)
u.reg_write(UC_ARM_REG_LR, 0x1ff01)
u.emu_start(header[4] | 1, 0x1ff00, count=1000000)
assert u.reg_read(UC_ARM_REG_PC) == 0x1ff00
assert u.reg_read(UC_ARM_REG_R0) == 0, u.reg_read(UC_ARM_REG_R0)
result = dict(passed=True, assertions=19, hardware_tested=False,
    elf_sha256=hashlib.sha256(elf).hexdigest(),
    limitation='Synthetic controller events; does not establish physical USB timing or suspend current.')
(folder / 'usb_power_validation.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result))
