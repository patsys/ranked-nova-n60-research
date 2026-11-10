# Copyright 2026 patsys
# SPDX-License-Identifier: GPL-3.0-or-later
"""Set the G65 RGB Matrix over VIA (RAM only, no save): g65_via_color.py <effect> [hue sat] [brightness]."""
import ctypes
import sys

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


args = [int(a) for a in sys.argv[1:]]
effect = args[0]
command([0x07, 3, 2, effect])
if len(args) >= 3:
    command([0x07, 3, 4, args[1], args[2]])
if len(args) >= 4:
    command([0x07, 3, 1, args[3]])
print("effect", command([0x08, 3, 2])[3], "color", command([0x08, 3, 4])[3:5].hex(), "brightness", command([0x08, 3, 1])[3])
h.close()
