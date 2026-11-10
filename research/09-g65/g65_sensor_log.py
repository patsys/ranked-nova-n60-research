# Copyright 2026 patsys
# SPDX-License-Identifier: GPL-3.0-or-later
"""Log raw G65 sensor samples over raw HID ([0x08, 0x00, 0xB2, bank]).

g65_sensor_log.py <seconds> <out.csv> [bank channel]: polls all 5 banks, prints the
watched key live and writes every sample to a CSV.
"""
import csv
import ctypes
import struct
import sys
import time

import hid

ctypes.CDLL(hid.__file__).hid_darwin_set_open_exclusive(0)
seconds, out = float(sys.argv[1]), sys.argv[2]
watch = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (2, 4)  # F key
raw = [d for d in hid.enumerate(0x3532, 0xA0C2) if d["usage_page"] == 0xFF60 and d["usage"] == 0x61]
assert len(raw) == 1, "Expected one G65 raw HID interface"
h = hid.device()
h.open_path(raw[0]["path"])


def bank(b):
    h.write(b"\0" + bytes([0x08, 0x00, 0xB2, b]).ljust(32, b"\0"))
    r = bytes(h.read(33, 1000))
    r = r[1:] if len(r) == 33 else r
    assert r[:4] == bytes([0x08, 0x00, 0xB2, b]), r.hex()
    return struct.unpack_from("<14H", r, 4)


rows, start, last_print = [], time.monotonic(), 0.0
while time.monotonic() - start < seconds:
    t = time.monotonic() - start
    sample = [bank(b) for b in range(5)]
    rows.append([round(t, 3)] + [v for b in sample for v in b])
    if t - last_print >= 0.1:
        v = sample[watch[0]][watch[1]]
        print(f"{t:5.1f}s  {v:5d}  " + "#" * min(60, v // 40), flush=True)
        last_print = t
h.close()
with open(out, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["t"] + [f"b{b}c{c}" for b in range(5) for c in range(14)])
    w.writerows(rows)
cols = list(zip(*rows))[1:]
moved = sorted(((max(c) - min(c), i) for i, c in enumerate(cols)), reverse=True)[:5]
print("samples", len(rows), "rate %.0f/s" % (len(rows) / seconds))
for span, i in moved:
    print(f"bank {i // 14} channel {i % 14}: min {min(cols[i])} max {max(cols[i])} span {span}")
