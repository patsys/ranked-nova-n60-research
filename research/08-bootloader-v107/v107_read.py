# Copyright 2026 patsys
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bootloader v1.0.7: read CPU flash through the native USB reply path (v107_stubs.read_stub).

One bootloader session: stock mode switch, getv must report v1.0.7, then one
START per 56-byte block, getv exit and wait for the application. No DATA.

usage: v107_read.py check            (12 bytes at 0x1040 vs the timing readback)
       v107_read.py dump START LEN OUT
"""
import ctypes
import sys
import time
from pathlib import Path

import hid

import v107_lr_probe as lr
import v107_stubs as v


def reply(h, length):
    result = lr.read64(h, 3000)
    assert result[:4] == bytes([1, 0, 0, 0x73]) and result[6:8] == b"\x01\x77", result.hex()
    assert int.from_bytes(result[4:6], "little") == length, result.hex()
    return result[8:8 + length]


def exit_session(h, header):
    """getv resets only after a native START; the redirected reads leave the main loop idle.
    The inert cal0 START (verified register-only probe) restores that state first."""
    try:
        frame = lr.start_frame(header, (lr.STUBS / "probe_cal0.bin").read_bytes())
        for offset in range(0, len(frame), 64):
            assert h.write(b"\0" + frame[offset:offset + 64].ljust(64, b"\0")) == 65
        assert lr.read64(h, 3000)[:9] == lr.ACK
        lr.get_version(h)
    except (OSError, AssertionError):
        pass
    h.close()


def read(start, length):
    ctypes.CDLL(hid.__file__).hid_darwin_set_open_exclusive(0)
    header = lr.authored()[0]
    h = lr.open_bootloader()
    out = bytearray()
    try:
        assert lr.get_version(h) == lr.VERSION
        for address in range(start, start + length, 56):
            count = min(56, start + length - address)
            frame = lr.start_frame(header, v.read_stub(address, count))
            for offset in range(0, len(frame), 64):
                assert h.write(b"\0" + frame[offset:offset + 64].ljust(64, b"\0")) == 65
            out += reply(h, count)
    finally:
        exit_session(h, header)
        for _ in range(100):
            if len(hid.enumerate(0x3532, 0xA0A3)) == 6 and not hid.enumerate(0x352D, 0x1101):
                break
            time.sleep(0.1)
        print("application back:", len(hid.enumerate(0x3532, 0xA0A3)) == 6 and not hid.enumerate(0x352D, 0x1101), flush=True)
    return bytes(out)


if __name__ == "__main__":
    if sys.argv[1] == "exit":
        ctypes.CDLL(hid.__file__).hid_darwin_set_open_exclusive(0)
        header = lr.authored()[0]
        handle = hid.device()
        handle.open_path(hid.enumerate(0x352D, 0x1101)[0]["path"])
        assert lr.get_version(handle) == lr.VERSION
        exit_session(handle, header)
        for _ in range(100):
            if len(hid.enumerate(0x3532, 0xA0A3)) == 6 and not hid.enumerate(0x352D, 0x1101):
                break
            time.sleep(0.1)
        print("application back:", len(hid.enumerate(0x3532, 0xA0A3)) == 6)
    elif sys.argv[1] == "check":
        data = read(0x1040, 12)
        print(data.hex(), "matches timing:", data.hex() == "fff71afafff7f2f843e00820")
    else:
        start, length, out = int(sys.argv[2], 0), int(sys.argv[3], 0), Path(sys.argv[4])
        data = read(start, length)
        out.write_bytes(data)
        print(f"{len(data)} bytes -> {out}")
