# Copyright 2026 patsys
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bootloader v1.0.7: one-byte START timing reads (the v1.0.5 method, whole-byte mode).

Every probe is register arithmetic plus at most one byte load from the boot
code (0..0x1fff) or the incoming stack frame (sp+0..sp+63), then a finite
countdown and `return 0`. No stores, no peripherals, no DATA/COMPLETE. The
builder executes every one of the six entries in Unicorn and rejects any write.
Each byte is accepted only when two independent sessions agree; calibration
(0 and 255 units) brackets every batch.

usage: v107_timing.py code 0x1044 6 | stack 52 4
"""
import ctypes
import json
import struct
import sys
import time
from pathlib import Path

import hid
from capstone import CS_ARCH_ARM, CS_MODE_MCLASS, CS_MODE_THUMB, Cs
from keystone import KS_ARCH_ARM, KS_MODE_THUMB, Ks
from unicorn import UC_ARCH_ARM, UC_HOOK_CODE, UC_HOOK_MEM_WRITE, UC_MODE_MCLASS, UC_MODE_THUMB, Uc
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_SP

import v107_lr_probe as lr

BASE = 0x20000000
ENTRIES = (0, 0x24, 0x6C, 0xDA, 0xFC, 0x13A)
BITS = 18   # nibble mode: ~21.9 ms per unit, host noise stays well below half a unit
LOG = Path(__file__).resolve().parent / "v107_timing_live.json"
ALLOWED = {"b", "bx", "movs", "mov", "lsls", "lsrs", "ands", "adds", "ldrb", "cmp", "beq", "subs", "bne"}


def build(kind, value=0, high=False):
    if kind == "cal":
        assert value in (0, 8)
        read, sample = f"movs r0, #{value}", value
    elif kind == "code":
        assert 0 <= value < 0x2000, "Code reads limited to the boot region"
        read, sample = f"movs r0, #{value >> 8}; lsls r0, #8; adds r0, #{value & 255}; ldrb r0, [r0]", 0xA5
    elif kind == "stack":
        assert 0 <= value < 64, "Stack reads limited to the incoming frame"
        read, sample = f"mov r0, sp; adds r0, #{value}; ldrb r0, [r0]", (0x12345679 >> 8 * (value - 52)) & 255 if 52 <= value < 56 else 0x5A
    else:
        raise ValueError(kind)
    if kind != "cal":
        read += ("; lsrs r0, #4" if high else "") + "; movs r1, #15; ands r0, r1"
        sample = sample >> 4 if high else sample & 15
    source = read + f"""
        cmp r0, #0
        beq done
        lsls r0, #{BITS}
    loop:
        subs r0, #1
        bne loop
    done:
        movs r0, #0
        bx lr
    """
    ks = Ks(KS_ARCH_ARM, KS_MODE_THUMB)
    image = bytearray(b"\x70\x47" * 220)
    for offset in ENTRIES:
        image[offset:offset + 2] = bytes(ks.asm("b #0x20000160", BASE + offset)[0])
    code = bytes(ks.asm(source, BASE + 0x160)[0])
    image[0x160:0x160 + len(code)] = code
    decoded = list(Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS).disasm(bytes(image), BASE))
    assert sum(i.size for i in decoded) == 440 and {i.mnemonic for i in decoded} <= ALLOWED
    cmp_pc = next(i.address for i in decoded if i.mnemonic == "cmp")
    for entry in ENTRIES:
        uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        uc.mem_map(BASE, 0x1000)
        uc.mem_write(BASE, bytes(image))
        uc.mem_map(0, 0x2000)
        uc.mem_write(0, b"\xa5" * 0x2000)
        stop, sp = BASE + 0x800, BASE + 0x400
        uc.mem_write(sp, b"\x5a" * 64)
        uc.mem_write(sp + 52, struct.pack("<I", 0x12345679))
        uc.reg_write(UC_ARM_REG_LR, stop | 1)
        uc.reg_write(UC_ARM_REG_SP, sp)
        writes, sampled = [], []
        uc.hook_add(UC_HOOK_MEM_WRITE, lambda *a: writes.append(a))
        uc.hook_add(UC_HOOK_CODE, lambda u, a, s, d: sampled.append(u.reg_read(UC_ARM_REG_R0)), begin=cmp_pc, end=cmp_pc)
        uc.emu_start((BASE + entry) | 1, stop, count=2 * (sample << BITS) + 100)
        assert uc.reg_read(UC_ARM_REG_PC) == stop and uc.reg_read(UC_ARM_REG_R0) == 0
        assert not writes and sampled == [sample], (writes, sampled, sample)
        assert uc.reg_read(UC_ARM_REG_SP) == sp and uc.reg_read(UC_ARM_REG_LR) == stop | 1
    return bytes(image)


def session(header, image):
    """One bootloader session; returns the post-write ACK delay in ms. Application must come back."""
    frame = lr.start_frame(header, image)
    time.sleep(2)
    h = lr.open_bootloader()
    record = {}
    try:
        assert lr.get_version(h) == lr.VERSION
        for offset in range(0, len(frame), 64):
            assert h.write(b"\0" + frame[offset:offset + 64].ljust(64, b"\0")) == 65
        sent = time.perf_counter_ns()
        reply = lr.read64(h, 3000)
        record.update(ms=(time.perf_counter_ns() - sent) / 1e6, reply=reply[:9].hex())
        assert len(reply) == 64 and reply[:9] == lr.ACK, reply.hex()
    finally:
        try:
            lr.get_version(h)
        except (OSError, AssertionError):
            pass
        h.close()
        for _ in range(60):
            if len(hid.enumerate(0x3532, 0xA0A3)) == 6 and not hid.enumerate(0x352D, 0x1101):
                break
            time.sleep(0.1)
        assert len(hid.enumerate(0x3532, 0xA0A3)) == 6 and not hid.enumerate(0x352D, 0x1101), "Application did not return"
    return record["ms"]


def main():
    ctypes.CDLL(hid.__file__).hid_darwin_set_open_exclusive(0)
    kind, start, count = sys.argv[1], int(sys.argv[2], 0), int(sys.argv[3], 0)
    header = lr.authored()[0]
    keys = [("cal", 0, False), ("cal", 8, False)] + [(kind, a, h) for a in range(start, start + count) for h in (False, True)]
    images = {k: build(*k) for k in keys}
    log = json.loads(LOG.read_text()) if LOG.exists() else {}
    batch = log.setdefault(f"{kind}:{start:#x}:{count}", dict(raw=[], values={}))
    save = lambda: LOG.write_text(json.dumps(log, indent=1))

    def measure(key):
        ms = session(header, images[key])
        batch["raw"].append([key[0], key[1], key[2], ms])
        save()
        return ms

    # Host noise only ever adds delay: the smaller of two calibration exchanges is kept.
    zero = min(measure(("cal", 0, False)) for _ in range(2))
    full = min(measure(("cal", 8, False)) for _ in range(2))
    unit = (full - zero) / 8
    assert 20 < unit < 24, unit
    batch["calibration_before"] = [zero, full, unit]

    def nibble(address, high):
        reads = []
        for _ in range(6):
            estimate = (measure((kind, address, high)) - zero) / unit
            value = round(estimate)
            if abs(estimate - value) < 0.25 and 0 <= value <= 15:
                reads.append(value)
            if len(reads) >= 2 and reads[-1] == reads[-2]:
                return value
        raise AssertionError(f"{kind} {address:#x} high={high}: no two agreeing reads {reads}")

    for address in range(start, start + count):
        if str(address) in batch["values"]:
            continue
        value = nibble(address, False) | nibble(address, True) << 4
        batch["values"][str(address)] = value
        save()
        print(f"{kind} {address:#06x}: {value:02x}", flush=True)
    drift = lambda z, f: abs(z - zero) < 3 and abs((f - z) / 8 - unit) / unit < 0.05
    for _ in range(2):  # a single noisy calibration exchange is repeated once
        zero2, full2 = measure(("cal", 0, False)), measure(("cal", 8, False))
        batch["calibration_after"] = [zero2, full2, (full2 - zero2) / 8]
        if drift(zero2, full2):
            break
    assert drift(zero2, full2), "Calibration drift"
    data = bytes(batch["values"][str(a)] for a in range(start, start + count))
    batch["hex"] = data.hex()
    save()
    print(kind, hex(start), data.hex())


if __name__ == "__main__":
    main()
