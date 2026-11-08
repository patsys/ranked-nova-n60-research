# Copyright 2026 patsys
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bootloader v1.0.7 hardware runner: flash-controller experiments on one scratch page, no DATA.

The run_diag.py sequence on the v1.0.7 native path (v107_stubs), in one bootloader session:
getv v1.0.7 → core mask check → whole-flash and info-flash backup (persisted, boot SHA and
application compared with today's dump) → controller timing registers must hold the measured
48 MHz values → scratch page must be erased → EXPERIMENTS → scratch page must be erased again
→ whole flash and info flash must equal the backup → inert cal0 START + getv (reset to app).
Any failed check stops before the next experiment; nothing outside the scratch page is addressed.

usage: run_diag_v107.py [--page 0xA0]
"""
import argparse
import ctypes
import hashlib
import json
import os
import struct
import sys
import time
from pathlib import Path

import hid

import diag_stub as d
import v107_lr_probe as lr
import v107_read
import v107_stubs as v
from run_diag import EXPERIMENTS

# Reproduce the authored-loader race (flash_go: delay, start, one instruction, poll bit 1) and the fix.
RACE = [
    ("erase", 0, (0, 0), d.ERASE),
    ("flash_go replica, two words (predict word1 lost)", 2, (0x0F1E2D3C, 0x4B5A6978), d.TWO_OPS | d.IMMEDIATE | d.DELAY),
    ("flash_go replica polling bits 0+1, two words (predict ok)", 4, (0x11223344, 0x55667788), d.TWO_OPS | d.IMMEDIATE | d.DELAY | d.POLL_BOTH),
    ("flash_go replica, single word", 8, (0x13579BDF, 0), d.IMMEDIATE | d.DELAY),
    ("final erase", 0, (0, 0), d.ERASE),
]
from ry72xx_flasher.session import durable_write

HERE = Path(__file__).resolve().parent
STATE = Path.home() / ".local/state/ry72xx-flasher"
BOOT_SHA_V107 = "eae819e411e7a1d336f75567e0aa7b2e432311694ae73ecdce4c417d548f3c01"
TIMING = {0x14: 0x207, 0x18: 0x0B, 0x20: 0x40, 0x24: 0x137, 0x28: 0x144, 0x30: 0x104,
          0x38: 0x114, 0x3C: 0x34BC0, 0x40: 0x15F900, 0x4C: 6}


class Session:
    def __init__(self, header, handle):
        self.header, self.h = header, handle

    def start(self, image, length):
        frame = lr.start_frame(self.header, image)
        for offset in range(0, len(frame), 64):
            assert self.h.write(b"\0" + frame[offset:offset + 64].ljust(64, b"\0")) == 65
        return v107_read.reply(self.h, length)

    def read(self, address, length):
        out = bytearray()
        for current in range(address, address + length, 56):
            count = min(56, address + length - current)
            out += self.start(v.read_stub(current, count), count)
        return bytes(out)

    def core(self, mask):
        before, after, cpuid, iser, systick = struct.unpack("<5I", self.start(v.core_stub(mask), 20))
        assert cpuid == 0x410CC200 and iser == 0 and systick & 3 == 0, "Unexpected core/IRQ/SysTick state"
        assert after == 1, "Interrupt mask not held"
        if not mask:
            assert before == 1, "Interrupt mask changed during the experiments"
        return dict(before=before, after=after, cpuid=hex(cpuid), nvic_iser=iser, systick=systick)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--page", type=lambda x: int(x, 0), default=0xA0)
    parser.add_argument("--matrix", choices=("plan", "race"), default="plan")
    args = parser.parse_args()
    assert d.SCRATCH_FIRST <= args.page <= d.SCRATCH_LAST, "Page outside the scratch window"
    ctypes.CDLL(hid.__file__).hid_darwin_set_open_exclusive(0)
    header = lr.authored()[0]
    reference = (HERE / "v107_dump/flash_pass1.bin").read_bytes()

    output = STATE / time.strftime("flashdiag_v107_%Y%m%dT%H%M%S")
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    log = dict(page=hex(args.page), bootloader="v1.0.7", experiments=[])
    def save():
        # durable_write refuses to overwrite (O_EXCL); the log is rewritten after every step.
        temporary = output / "result.json.tmp"
        with open(temporary, "wb") as handle:
            handle.write(json.dumps(log, indent=1).encode())
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output / "result.json")
    print(f"Output {output}", flush=True)

    h = lr.open_bootloader()
    try:
        assert lr.get_version(h) == lr.VERSION, "Not bootloader v1.0.7"
        s = Session(header, h)
        log["core_before"] = s.core(True)
        print("Backing up whole flash and info flash", flush=True)
        before = s.read(0, 0x20000)
        info = s.read(0x10000000, 0x800)
        durable_write(output / "before_flash.bin", before)
        durable_write(output / "before_info.bin", info)
        assert (output / "before_flash.bin").read_bytes() == before, "Backup persistence check failed"
        assert hashlib.sha256(before[:0x2000]).hexdigest() == BOOT_SHA_V107, "Bootloader bytes differ from v1.0.7"
        assert before[:0x10A00] == reference[:0x10A00], "Bootloader/application differ from today's dump"
        page = before[args.page * 512:(args.page + 1) * 512]
        assert page == b"\xff" * 512, "Scratch page not erased on this board"
        controller = struct.unpack("<64I", s.read(0x40013000, 0x100))
        log["timing_before"] = {hex(k): hex(controller[k // 4]) for k in TIMING}
        assert all(controller[k // 4] == want for k, want in TIMING.items()), log["timing_before"]
        log["before_sha256"] = hashlib.sha256(before).hexdigest()
        save()

        log["matrix"] = args.matrix
        for name, word, values, flags in (RACE if args.matrix == "race" else EXPERIMENTS):
            result = d.parse(s.start(v.diag_stub(args.page, word, values, flags), 40))
            expected = None if flags & d.ERASE else [hex(values[0])] + ([hex(values[1])] if flags & d.TWO_OPS else [])
            got = [result["word0"]] + ([result["word1"]] if flags & d.TWO_OPS else [])
            entry = dict(name=name, word=word, flags=flags, values=[hex(x) for x in values], result=result,
                         ok=(result["word0"] == "0xffffffff") if expected is None else got == expected)
            log["experiments"].append(entry)
            save()
            print(f"{'OK  ' if entry['ok'] else 'DIFF'} {name}: {result}", flush=True)

        assert s.read(args.page * 512, 512) == b"\xff" * 512, "Scratch page not erased after the final erase"
        log["core_after"] = s.core(False)
        after = s.read(0, 0x20000)
        after_info = s.read(0x10000000, 0x800)
        durable_write(output / "after_flash.bin", after)
        log.update(whole_flash_unchanged=after == before, info_flash_unchanged=after_info == info)
        save()
        assert after == before and after_info == info, "Flash differs from the backup; keyboard left in the bootloader"
    except BaseException as error:
        log["error"] = repr(error)
        save()
        # Leave the bootloader holding the session: nothing is released after a failed check.
        h.close()
        raise
    v107_read.exit_session(h, header)
    for _ in range(100):
        if len(hid.enumerate(0x3532, 0xA0A3)) == 6 and not hid.enumerate(0x352D, 0x1101):
            break
        time.sleep(0.1)
    log["application_back"] = len(hid.enumerate(0x3532, 0xA0A3)) == 6 and not hid.enumerate(0x352D, 0x1101)
    save()
    print(json.dumps({k: log[k] for k in ("whole_flash_unchanged", "info_flash_unchanged", "application_back")}, indent=1))


if __name__ == "__main__":
    sys.exit(main())
