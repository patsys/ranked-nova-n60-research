# Copyright 2026 patsys
# SPDX-License-Identifier: GPL-3.0-or-later
"""Ask the G65 QMK firmware to enter the bootloader over raw HID (no keys needed)."""
import ctypes
import time

import hid

ctypes.CDLL(hid.__file__).hid_darwin_set_open_exclusive(0)
REQUEST = bytes([0x07, 0x00, 0xB0]) + b"RYBL"
raw = [d for d in hid.enumerate(0x3532, 0xA0C2) if d["usage_page"] == 0xFF60 and d["usage"] == 0x61]
assert len(raw) == 1, f"Expected one QMK raw HID interface, found {len(raw)}"
h = hid.device()
h.open_path(raw[0]["path"])
try:
    h.write(b"\0" + REQUEST.ljust(32, b"\0"))
except OSError:
    pass  # the device may reset before the write completes
finally:
    h.close()
for _ in range(50):
    if hid.enumerate(0x352D, 0x1101):
        print("bootloader present")
        break
    time.sleep(0.1)
else:
    print("bootloader not seen")
