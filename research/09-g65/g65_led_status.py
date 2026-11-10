# Copyright 2026 patsys
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read the G65 LED controller status over raw HID ([0x08, 0x00, 0xB1]) and the RGB Matrix settings."""
import ctypes
import struct

import hid

ctypes.CDLL(hid.__file__).hid_darwin_set_open_exclusive(0)
raw = [d for d in hid.enumerate(0x3532, 0xA0C2) if d["usage_page"] == 0xFF60 and d["usage"] == 0x61]
assert len(raw) == 1, "Expected one G65 raw HID interface"
h = hid.device()
h.open_path(raw[0]["path"])


def command(packet):
    h.write(b"\0" + bytes(packet).ljust(32, b"\0"))
    reply = bytes(h.read(33, 1000))
    return reply[1:] if len(reply) == 33 else reply


r = command([0x08, 0x00, 0xB1])
usable, ready, attempts, reply = r[3:7]
completed, errors = struct.unpack_from("<II", r, 7)
print(f"usable={usable} ready={ready} attempts={attempts} last_reply=0x{reply:02x} frames={completed} errors={errors}")
print("effect", command([0x08, 3, 2])[3], "brightness", command([0x08, 3, 1])[3], "color", command([0x08, 3, 4])[3:5].hex())
h.close()
