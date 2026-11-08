# Copyright 2026 patsys
# SPDX-License-Identifier: GPL-3.0-or-later
"""Unicorn checks of the v1.0.7 read stub: native frame redirect, reply, resume, and wrong frames.

The frames are modelled from the timing-measured v1.0.7 identities (LR 0x1049,
[sp,#60] = 0xce7) and the v1.0.5 ones (LR 0x1021, [sp,#52] = 0xcc3).
"""
import struct
import unittest

from unicorn import UC_ARCH_ARM, UC_HOOK_MEM_WRITE, UC_MODE_MCLASS, UC_MODE_THUMB, Uc
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R1, UC_ARM_REG_R4, UC_ARM_REG_SP

import v107_stubs as v
from ry72xx_flasher import stubs as v105

CTX, STACK, CALLBACK = 0x20000324, 0x2000F000, 0x2000E000


def machine(stub, flash):
    u = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    u.mem_map(0, 0x20000)
    u.mem_map(0x20000000, 0x10000)
    u.mem_write(0, flash)
    u.mem_write(0x20000000, stub)
    u.mem_write(CALLBACK, b"\x70\x47")
    u.mem_write(CTX + 0x214, struct.pack("<I", CALLBACK | 1))
    return u


def init_call(u, lr, offset, saved):
    """Call the START init entry as the native handler does; return the stack words afterwards."""
    u.mem_write(STACK, bytes(64))
    u.mem_write(STACK + offset, struct.pack("<I", saved))
    u.reg_write(UC_ARM_REG_SP, STACK)
    u.reg_write(UC_ARM_REG_LR, lr)
    writes = []
    hook = u.hook_add(UC_HOOK_MEM_WRITE, lambda uc, a, addr, size, val, d: writes.append(addr))
    u.emu_start(0x2000013A | 1, lr & ~1, count=1000)
    u.hook_del(hook)
    return struct.unpack("<16I", u.mem_read(STACK, 64)), writes


class V107Stub(unittest.TestCase):
    def setUp(self):
        self.flash = bytes(range(256)) * 512

    def test_v107_frame_is_redirected_and_reply_resumes(self):
        stub = v.read_stub(0x1040, 12)
        u = machine(stub, self.flash)
        u.mem_write(v.LR & ~1, b"\xfe\xe7")
        words, writes = init_call(u, v.LR, v.SAVED_OFFSET, v.SAVED)
        self.assertEqual(words[v.SAVED_OFFSET // 4], 0x20000141)
        self.assertEqual(writes, [STACK + v.SAVED_OFFSET], "only the saved return word changes")
        u.mem_write(v.RESUME, b"\xfe\xe7")
        u.reg_write(UC_ARM_REG_R4, CTX)
        u.reg_write(UC_ARM_REG_SP, STACK + 0x100)
        writes = []
        u.hook_add(UC_HOOK_MEM_WRITE, lambda uc, a, addr, size, val, d: writes.append(addr))
        u.emu_start(0x20000141, v.RESUME, count=10000)
        self.assertEqual(u.reg_read(UC_ARM_REG_PC), v.RESUME)
        self.assertEqual(bytes(u.mem_read(CTX + 8, 12)), bytes(u.mem_read(0x1040, 12)))
        self.assertEqual(struct.unpack("<H", u.mem_read(CTX + 4, 2))[0], 12)
        self.assertEqual(u.reg_read(UC_ARM_REG_R1), 12)
        self.assertTrue(all(CTX + 4 <= a < CTX + 8 + 56 or a >= STACK for a in writes), [hex(a) for a in writes])

    def test_v107_stub_ignores_v105_frame(self):
        u = machine(v.read_stub(0, 4), self.flash)
        u.mem_write(0x1020, b"\xfe\xe7")
        words, writes = init_call(u, 0x1021, 52, 0xCC3)
        self.assertEqual(words[13], 0xCC3)
        self.assertEqual(writes, [], "the v1.0.7 stub must stay inert on a v1.0.5 frame")

    def test_v105_stub_ignores_v107_frame(self):
        u = machine(v105.read_stub(0, 4), self.flash)
        u.mem_write(v.LR & ~1, b"\xfe\xe7")
        words, writes = init_call(u, v.LR, v.SAVED_OFFSET, v.SAVED)
        self.assertEqual(words[v.SAVED_OFFSET // 4], v.SAVED)
        self.assertEqual(writes, [], "the shipped v1.0.5 stub must stay inert on v1.0.7")

    def test_wrong_saved_word_is_ignored(self):
        u = machine(v.read_stub(0, 4), self.flash)
        u.mem_write(v.LR & ~1, b"\xfe\xe7")
        words, writes = init_call(u, v.LR, v.SAVED_OFFSET, 0xCC3)
        self.assertEqual(writes, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
