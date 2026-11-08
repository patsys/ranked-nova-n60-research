# Copyright 2026 patsys
# SPDX-License-Identifier: GPL-3.0-or-later
"""Unicorn self-test of diag_stub: native call path, reply layout and access bounds.

The controller model executes a command on the start bit and reports busy for a
configurable number of STATUS reads. It is a model, not the silicon: these
tests prove the stub's own behaviour and bounds, not controller semantics.
"""
import struct
import unittest

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_MEM_WRITE, UC_HOOK_MEM_READ
from unicorn.arm_const import UC_ARM_REG_R4, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PRIMASK, UC_ARM_REG_R1, UC_ARM_REG_PC

import diag_stub as d

CTX, STACK, CALLBACK, BOOT_RETURN = 0x20000324, 0x2000F000, 0x2000E000, 0xE70


class Model:
    """busy_delay: STATUS reads right after the start that still show only bit 0 (hardware: 1).
    Measured on v1.0.7 (flashdiag_v107_20261107T155719): while busy STATUS = 3, a new start is
    ignored, and the running operation completes with the ADDRESS/DATA present at its end,
    so DATA/ADDRESS written during busy redirect it (the first word stays erased)."""
    def __init__(self, busy_reads=5, busy_delay=0):
        self.busy_reads, self.busy_left = busy_reads, 0
        self.busy_delay, self.delay_left, self.lost, self.pending = busy_delay, 0, 0, None
        self.flash_writes, self.addresses, self.gates, self.commands = [], [], [], []


def run(stub, model, page, flash_fill=0xFF, frame=(0x1021, 52, 0xCC3, BOOT_RETURN)):
    lr, saved_offset, saved, boot_return = frame
    u = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    for base, size in [(0, 0x20000), (0x20000000, 0x10000), (d.CTRL, 0x1000)]:
        u.mem_map(base, size)
    u.mem_write(0, bytes([flash_fill]) * 0x20000)
    u.mem_write(0x20000000, stub)
    u.mem_write(boot_return, b"\xfe\xe7")
    u.mem_write(CALLBACK, b"\x70\x47")
    u.mem_write(CTX + 512 + 20, struct.pack("<I", CALLBACK | 1))
    regs = {}

    def on_write(uc, access, address, size, value, data):
        if address < 0x20000:
            model.flash_writes.append(address)
        if not d.CTRL <= address < d.CTRL + 0x1000:
            return
        offset = address - d.CTRL
        regs[offset] = value
        if offset == 0x04:
            model.addresses.append(value)
        elif offset == 0x00:
            model.commands.append(value)
        elif offset >= 0xD0:
            model.gates.append((offset, value))
        elif offset == 0x10 and value & 1:
            if model.busy_left or model.delay_left:
                model.lost += 1
                return
            model.pending = regs.get(0x00)
            if not model.busy_delay:
                complete(uc)
            model.busy_left = model.busy_reads
            model.delay_left = model.busy_delay

    def complete(uc):
        word = regs.get(0x04, 0)
        if model.pending == 2:
            uc.mem_write((word >> 7) * 512, b"\xff" * 512)
        elif model.pending == 1:
            old = struct.unpack("<I", uc.mem_read(word * 4, 4))[0]
            uc.mem_write(word * 4, struct.pack("<I", old & regs.get(0x08, 0)))
        model.pending = None

    def on_read(uc, access, address, size, value, data):
        if address == d.CTRL + 0x10:
            if model.delay_left:
                model.delay_left -= 1
                uc.mem_write(address, struct.pack("<I", 1))
                return
            busy = 3 if model.busy_left else 0
            model.busy_left = max(0, model.busy_left - 1)
            if not model.busy_left and model.pending is not None:
                complete(uc)
            uc.mem_write(address, struct.pack("<I", busy))
        elif address >= d.CTRL + 0xD0 and address < d.CTRL + 0xF0:
            uc.mem_write(address, b"\xff\xff\xff\xff")  # write-only gate reads all ones on silicon

    u.hook_add(UC_HOOK_MEM_WRITE, on_write)
    u.hook_add(UC_HOOK_MEM_READ, on_read, begin=d.CTRL, end=d.CTRL + 0xFFF)
    # Native init call: LR 0x1021 and outer saved return 0xcc3 at sp+52.
    u.mem_write(STACK + saved_offset, struct.pack("<I", saved))
    for register, value in [(UC_ARM_REG_SP, STACK), (UC_ARM_REG_LR, lr), (UC_ARM_REG_PRIMASK, 1)]:
        u.reg_write(register, value)
    u.mem_write(lr & ~1, b"\xfe\xe7")
    u.emu_start(0x20000000 + 0x13A | 1, lr & ~1, count=1000)
    redirected = struct.unpack("<I", u.mem_read(STACK + saved_offset, 4))[0]
    assert redirected == 0x20000141, hex(redirected)
    u.reg_write(UC_ARM_REG_R4, CTX)
    u.emu_start(redirected, boot_return, count=20_000_000)
    assert u.reg_read(UC_ARM_REG_PC) == boot_return
    length = u.reg_read(UC_ARM_REG_R1)
    reply = bytes(u.mem_read(CTX + 8, 40))
    assert struct.unpack("<H", u.mem_read(CTX + 4, 2))[0] == 40
    return d.parse(reply), u, length


class DiagStub(unittest.TestCase):
    PAGE = 0xA0

    def bounds(self, model, two=False):
        self.assertEqual(model.flash_writes, [], "CPU must never store to flash directly")
        for address in model.addresses:
            self.assertEqual(address >> 7, self.PAGE, f"ADDRESS {address:#x} outside the scratch page")
        gate_word = 0xD0 + (self.PAGE >> 5) * 4
        self.assertTrue(all(offset == gate_word for offset, _ in model.gates), model.gates)
        self.assertEqual(model.gates[0][1], 1 << (self.PAGE & 31), "gate opened one-hot")
        self.assertEqual(model.gates[-1][1] & (1 << (self.PAGE & 31)), 0, "page gate closed again")

    def test_rejects_pages_outside_scratch(self):
        for page in (0x10, 0x84, 0xD0, 0xFA, 0x00):
            with self.assertRaises(Exception):
                d.diag_stub(page)
        with self.assertRaises(Exception):
            d.diag_stub(self.PAGE, word=127, flags=d.TWO_OPS)

    def test_erase(self):
        model = Model()
        result, u, _ = run(d.diag_stub(self.PAGE, flags=d.ERASE), model, self.PAGE, flash_fill=0x00)
        self.bounds(model)
        self.assertEqual(model.commands, [2])
        self.assertEqual(bytes(u.mem_read(self.PAGE * 512, 512)), b"\xff" * 512)
        self.assertEqual(bytes(u.mem_read(self.PAGE * 512 - 4, 4)), b"\0" * 4, "neighbour page untouched")
        self.assertEqual(result["op0"]["status_after_start"], "0x3", "first sample sees busy (model without delay)")
        self.assertEqual(result["op0"]["busy_polls"], 4, "busy reads after the first sample")
        self.assertEqual(result["word0"], "0xffffffff")

    def test_single_program(self):
        model = Model(busy_reads=3)
        result, u, _ = run(d.diag_stub(self.PAGE, word=6, values=(0x12345678, 0)), model, self.PAGE)
        self.bounds(model)
        self.assertEqual(model.commands, [1])
        self.assertEqual(model.addresses, [self.PAGE << 7 | 6])
        self.assertEqual(result["word0"], "0x12345678")
        self.assertEqual(result["op0"]["busy_polls"], 2)
        self.assertEqual(result["op1"]["busy_polls"], 0)
        self.assertEqual(result["address_reg"], hex(self.PAGE << 7 | 6))
        self.assertEqual(result["gate_reg"], "0xffffffff")

    def test_two_ops_back_to_back(self):
        model = Model()
        result, u, _ = run(d.diag_stub(self.PAGE, word=2, values=(0xAAAA5555, 0x5555AAAA), flags=d.TWO_OPS), model, self.PAGE)
        self.bounds(model)
        self.assertEqual(model.commands, [1, 1])
        self.assertEqual((result["word0"], result["word1"]), ("0xaaaa5555", "0x5555aaaa"))
        self.assertEqual(result["op1"]["busy_polls"], 4)
        self.assertEqual(result["op1"]["status_end"], "0x0")

    def test_address_rewrite_and_delay_variants(self):
        for flags in (d.REWRITE_ADDRESS, d.DELAY, d.REWRITE_ADDRESS | d.DELAY | d.TWO_OPS):
            model = Model()
            result, _, _ = run(d.diag_stub(self.PAGE, word=4, values=(1, 2), flags=flags), model, self.PAGE)
            self.bounds(model)
            ops = 2 if flags & d.TWO_OPS else 1
            per_op = 2 if flags & d.REWRITE_ADDRESS else 1
            self.assertEqual(len(model.addresses), ops * per_op, flags)
            self.assertEqual(result["word0"], "0x1")


V107_FRAME = (0x1049, 60, 0xCE7, 0xE94)


class MeasuredRace(unittest.TestCase):
    """Model from the 2026-11-07 v1.0.7 measurement: first read after start = 0x1, then busy."""
    PAGE = 0xA0

    def run_case(self, flags):
        import v107_stubs as v
        model = Model(busy_reads=240, busy_delay=1)
        result, _, _ = run(v.diag_stub(self.PAGE, 2, (0x0F1E2D3C, 0x4B5A6978), d.TWO_OPS | flags), model, self.PAGE, frame=V107_FRAME)
        return result, model

    def test_sample_read_variant_matches_hardware(self):
        result, model = self.run_case(0)
        self.assertEqual((result["word0"], result["word1"], model.lost), ("0xf1e2d3c", "0x4b5a6978", 0))
        self.assertEqual(result["op0"]["status_after_start"], "0x1")

    def test_flash_go_replica_loses_first_word(self):
        result, model = self.run_case(d.IMMEDIATE | d.DELAY)
        self.assertEqual((result["word0"], result["word1"], model.lost), ("0xffffffff", "0x4b5a6978", 1))
        self.assertEqual(result["op0"]["busy_polls"], 0, "first poll already reports done")

    def test_poll_both_bits_keeps_both_words(self):
        result, model = self.run_case(d.IMMEDIATE | d.DELAY | d.POLL_BOTH)
        self.assertEqual((result["word0"], result["word1"], model.lost), ("0xf1e2d3c", "0x4b5a6978", 0))


class DiagStubV107(unittest.TestCase):
    """Same scenarios through the v1.0.7 native frame; the v1.0.5 build must stay inert there."""
    PAGE = 0xA0

    def test_matrix_on_v107_frame(self):
        import v107_stubs as v
        cases = [(0, (0, 0), d.ERASE), (0, (0x12345678, 0), 0), (1, (0x9ABCDEF0, 0), 0),
                 (2, (0x0F1E2D3C, 0x4B5A6978), d.TWO_OPS), (4, (0x11223344, 0x55667788), d.TWO_OPS | d.REWRITE_ADDRESS),
                 (6, (0x99AABBCC, 0xDDEEFF00), d.TWO_OPS | d.DELAY), (11, (0xA5A5A5A5, 0x5A5A5A5A), d.TWO_OPS)]
        for word, values, flags in cases:
            model = Model()
            fill = 0x00 if flags & d.ERASE else 0xFF
            result, u, length = run(v.diag_stub(self.PAGE, word, values, flags), model, self.PAGE, fill, V107_FRAME)
            self.assertEqual(model.flash_writes, [])
            self.assertTrue(all(a >> 7 == self.PAGE for a in model.addresses), model.addresses)
            if flags & d.ERASE:
                self.assertEqual(result["word0"], "0xffffffff")
            else:
                self.assertEqual(result["word0"], hex(values[0]))
                if flags & d.TWO_OPS:
                    self.assertEqual(result["word1"], hex(values[1]))
            self.assertEqual(length, 40)

    def test_v105_build_is_inert_on_v107_frame(self):
        with self.assertRaises(AssertionError):
            run(d.diag_stub(self.PAGE, 0, (1, 0)), Model(), self.PAGE, frame=V107_FRAME)


if __name__ == "__main__":
    unittest.main(verbosity=2)
