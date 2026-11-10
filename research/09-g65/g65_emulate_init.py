# Copyright 2026 patsys
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the G65 stock reset path in Unicorn until the I2C init (0x4cf8); report its inputs.

Offline only. Peripherals are plain RAM, so register reads return what was written.
"""
import struct
import sys

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE, UcError
from unicorn.arm_const import UC_ARM_REG_PC, UC_ARM_REG_SP, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_LR

flash = open(sys.argv[1], "rb").read()
u = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
u.mem_map(0, 0x20000)
u.mem_write(0, flash)
u.mem_map(0x10000000, 0x1000)
u.mem_map(0x20000000, 0x4000)
u.mem_map(0x40000000, 0x40000)
u.mem_map(0xE0000000, 0x100000)
# Peripheral "ready" bits polled during clock setup: pretend everything is ready.
for base in range(0x40010000, 0x40020000, 0x1000):
    u.mem_write(base, b"\xff" * 0x100)

sp, reset = struct.unpack_from("<II", flash, 0x2000)
u.reg_write(UC_ARM_REG_SP, sp)
seen = {}
STOP = {0x4CF8: "i2c_init", 0x45D8: "gpio_init"}


def hook(uc, address, size, _):
    if address in STOP and STOP[address] not in seen:
        seen[STOP[address]] = dict(r0=uc.reg_read(UC_ARM_REG_R0), r1=uc.reg_read(UC_ARM_REG_R1),
                                   lr=uc.reg_read(UC_ARM_REG_LR))
        if STOP[address] == "i2c_init":
            uc.emu_stop()


u.hook_add(UC_HOOK_CODE, hook)
try:
    u.emu_start(reset | 1, 0xFFFFFFFF, count=20_000_000)
except UcError as error:
    print("stopped:", error, hex(u.reg_read(UC_ARM_REG_PC)))
print("pc", hex(u.reg_read(UC_ARM_REG_PC)), seen)
ram = bytes(u.mem_read(0x20000000, 0x4000))
print("0x20000568:", ram[0x568:0x56C].hex())
print("0x200003f6:", list(ram[0x3F6:0x3F6 + 20]))
print("0x2000040a:", list(ram[0x40A:0x40A + 20]))
print("0x20000030:", ram[0x30:0x40].hex())
