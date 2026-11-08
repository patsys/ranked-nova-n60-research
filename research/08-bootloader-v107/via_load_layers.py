# Copyright 2026 patsys
# SPDX-License-Identifier: GPL-3.0-or-later
"""Load keymap layers into a running VIA image over raw HID (dynamic keymap, 32-byte reports).

Saves the current dynamic keymap first, writes only differing keys with
id_dynamic_keymap_set_keycode, then reads every key back.

usage: via_load_layers.py LAYERS.json BACKUP.json
       LAYERS.json: {"layers": [[[keycode x cols] x rows] x layers]}
"""
import ctypes
import json
import sys
import time
from pathlib import Path

import hid

GET_PROTOCOL, GET_KEYCODE, SET_KEYCODE, LAYER_COUNT = 0x01, 0x04, 0x05, 0x11


def command(h, *payload):
    """Send one VIA command and return its echo. Late replies from an earlier command are drained."""
    h.set_nonblocking(1)  # hidapi: read(n, 0) would block forever
    while h.read(32):
        pass
    h.set_nonblocking(0)
    report = bytes(payload).ljust(32, b"\0")
    assert h.write(b"\0" + report) == 33
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        reply = bytes(h.read(32, 500))
        if len(reply) == 32 and reply[:len(payload[:4])] == bytes(payload[:4]):
            return reply
    raise TimeoutError(f"No VIA reply to {bytes(payload).hex()}")


def main():
    layers = json.loads(Path(sys.argv[1]).read_text())["layers"]
    backup = Path(sys.argv[2])
    assert not backup.exists(), "Backup file already exists"
    if sys.platform == "darwin":
        ctypes.CDLL(hid.__file__).hid_darwin_set_open_exclusive(0)
    raw = [d for d in hid.enumerate(0x3532, 0xA0A3) if d["usage_page"] == 0xFF60 and d["usage"] == 0x61]
    assert len(raw) == 1, "Expected exactly one VIA raw HID interface"
    h = hid.device()
    h.open_path(raw[0]["path"])
    try:
        version = command(h, GET_PROTOCOL)
        count = command(h, LAYER_COUNT)[1]
        rows, cols = len(layers[0]), len(layers[0][0])
        assert count >= len(layers), f"Firmware has {count} dynamic layers, need {len(layers)}"
        read = lambda l, r, c: int.from_bytes(command(h, GET_KEYCODE, l, r, c)[4:6], "big")
        current = [[[read(l, r, c) for c in range(cols)] for r in range(rows)] for l in range(count)]
        backup.write_text(json.dumps(dict(protocol=version[1:3].hex(), layers=current)))
        changed = 0
        for l, layer in enumerate(layers):
            for r, row in enumerate(layer):
                for c, keycode in enumerate(row):
                    if current[l][r][c] != keycode:
                        command(h, SET_KEYCODE, l, r, c, keycode >> 8, keycode & 0xFF)
                        changed += 1
        time.sleep(0.2)
        mismatches = [(l, r, c) for l, layer in enumerate(layers) for r, row in enumerate(layer)
                      for c, keycode in enumerate(row) if read(l, r, c) != keycode]
        print(json.dumps(dict(protocol=version[1:3].hex(), dynamic_layers=count, keys_written=changed,
                              readback_mismatches=mismatches, backup=str(backup))))
        assert not mismatches
    finally:
        h.close()


if __name__ == "__main__":
    main()
