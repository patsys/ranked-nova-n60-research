# Copyright 2026 patsys
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bootloader v1.0.7: incoming-LR nibble timing, the v1.0.5 method unchanged.

Reuses the verified register-only probes (read-only-stubs/lr_probes.json): no
stack, no data-memory load or store, no peripheral access, no DATA/COMPLETE.
Each session: stock mode switch, getv (must report a1070000), START, measure
the ACK delay, getv exit, and require the six application collections back
before the next session. Stops at the first unexpected reply. Resumable.
"""
import ctypes
import functools
import hashlib
import json
import struct
import sys
import time
from pathlib import Path

import hid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if (ROOT / "read-only-stubs").is_dir():  # ranked-nova-n60-research layout
    STUBS = ROOT / "read-only-stubs"
else:  # original workspace layout
    STUBS = ROOT / "readonly_stub"
# ry72xx_flasher: a source checkout next to this folder, else the installed package
# (python -m pip install git+https://github.com/patsys/ry72xx-flasher).
for FLASHER_SRC in (ROOT / "flasher/src", ROOT / "contributions/ry72xx-flasher/src"):
    if FLASHER_SRC.is_dir():
        sys.path.insert(0, str(FLASHER_SRC))
        break
from ry72xx_flasher.loader import authored  # noqa: E402
from ry72xx_flasher.transport import QUERY, start_frame  # noqa: E402

VERSION = ["a1070000", "a1040000"]
LOG = Path(__file__).resolve().parent / "v107_lr_readback_live.json"
PLAN = ["cal0", "cal8"] + [f"lr{i}" for i in range(8)] + ["xorcheck", "lr0", "lr4", "cal8", "cal0"]
ACK = bytes.fromhex("010000730100017704")


def read64(h, timeout):
    reply = bytes(h.read(65, timeout))
    return reply[1:] if len(reply) == 65 and reply[0] == 0 else reply


def get_version(h):
    assert h.write(b"\0" + QUERY.ljust(64, b"\0")) == 65
    reply = read64(h, 2000)
    assert reply[:16] == bytes.fromhex("0000000010000001") + b"version:", reply.hex()
    return [reply[16:20].hex(), reply[20:24].hex()]


def open_bootloader():
    for attempt in range(2):  # the stock application occasionally ignores one mode switch
        apps = [d for d in hid.enumerate(0x3532, 0xA0A3) if d["usage_page"] == 0xFF00]
        assert len(apps) == 1 and not hid.enumerate(0x352D, 0x1101), "Expected the stock application only"
        app = hid.device()
        try:
            app.open_path(apps[0]["path"])
            assert app.write(bytes.fromhex("04a501") + bytes(61)) == 64
        finally:
            app.close()
        for _ in range(100):
            devices = hid.enumerate(0x352D, 0x1101)
            if devices:
                break
            time.sleep(0.1)
        if devices:
            break
        for _ in range(30):
            if len(hid.enumerate(0x3532, 0xA0A3)) == 6:
                break
            time.sleep(0.1)
    assert len(devices) == 1, "Bootloader did not appear"
    h = hid.device()
    h.open_path(devices[0]["path"])
    return h


def decode(log, t):
    zero, eight = log["sessions"][0]["post_write_ms"], log["sessions"][1]["post_write_ms"]
    unit = (eight - zero) / 8
    assert unit > 10, unit
    estimate = (t - zero) / unit
    value = round(estimate)
    residual = abs(estimate - value)
    assert 0 <= value <= 15 and residual < 0.25, (estimate, residual)
    return dict(value=value, estimate=estimate, residual_units=residual, unit_ms=unit)


def main():
    ctypes.CDLL(hid.__file__).hid_darwin_set_open_exclusive(0)
    header = authored()[0]  # the flasher's own plaintext START header; no vendor capture needed
    manifest = json.loads((STUBS / "lr_probes.json").read_text())
    log = json.loads(LOG.read_text()) if LOG.exists() else dict(bootloader=VERSION, sessions=[])
    save = lambda: LOG.write_text(json.dumps(log, indent=1))
    only = sys.argv[1:] and int(sys.argv[1])
    for index, name in enumerate(PLAN[:only] if only else PLAN):
        if index < len(log["sessions"]) and log["sessions"][index].get("complete"):
            continue
        assert len(log["sessions"]) in (index, index + 1)
        if len(log["sessions"]) == index + 1:
            assert "reply_hex" not in log["sessions"][index], "Partial exchange needs review"
            log["sessions"].pop()
        spec = manifest[name]
        blob = (STUBS / Path(spec["file"]).name).read_bytes()
        assert len(blob) == 440 and hashlib.sha256(blob).hexdigest() == spec["sha256"]
        frame = start_frame(header, blob)
        record = dict(index=index, probe=name, sha256=spec["sha256"])
        log["sessions"].append(record)
        save()
        time.sleep(3)
        h = open_bootloader()
        try:
            record["version"] = get_version(h)
            assert record["version"] == VERSION, record["version"]
            start = time.perf_counter_ns()
            for offset in range(0, len(frame), 64):
                assert h.write(b"\0" + frame[offset:offset + 64].ljust(64, b"\0")) == 65
            sent = time.perf_counter_ns()
            reply = read64(h, 2000)
            end = time.perf_counter_ns()
            record.update(total_ms=(end - start) / 1e6, post_write_ms=(end - sent) / 1e6, reply_hex=reply.hex())
            save()
            assert len(reply) == 64 and reply[:9] == ACK, reply.hex()
        finally:
            try:
                record["exit_query"] = get_version(h)
            except (OSError, AssertionError) as error:
                record["exit_query_error"] = str(error)
            h.close()
            for _ in range(50):
                apps = len(hid.enumerate(0x3532, 0xA0A3))
                if apps == 6 and not hid.enumerate(0x352D, 0x1101):
                    break
                time.sleep(0.1)
            record.update(final_application_collections=apps, final_bootloader_interfaces=len(hid.enumerate(0x352D, 0x1101)))
            save()
            assert apps == 6 and record["final_bootloader_interfaces"] == 0, "Application did not return"
        if name.startswith("lr") or name == "xorcheck":
            try:
                record["decoded"] = decode(log, record["post_write_ms"])
            except AssertionError:
                # Host timing noise: keep the raw exchange, repeat this probe at most twice.
                log.setdefault("rejected", []).append(log["sessions"].pop())
                save()
                retries = sum(r["probe"] == name and r["index"] == index for r in log["rejected"])
                assert retries <= 2, f"{name} not decodable after {retries} attempts"
                print(json.dumps(dict(probe=name, ms=round(record["post_write_ms"], 3), retry=retries)), flush=True)
                return main()
        record["complete"] = True
        save()
        print(json.dumps(dict(probe=name, ms=round(record["post_write_ms"], 3), decoded=record.get("decoded"))), flush=True)
    if len(log["sessions"]) == len(PLAN) and all(r.get("complete") for r in log["sessions"]):
        digits = [r["decoded"]["value"] for r in log["sessions"][2:10]]
        address = sum(v << (4 * i) for i, v in enumerate(digits))
        assert log["sessions"][10]["decoded"]["value"] == functools.reduce(int.__xor__, digits, 0), "LR XOR check failed"
        assert log["sessions"][11]["decoded"]["value"] == digits[0] and log["sessions"][12]["decoded"]["value"] == digits[4]
        log["lr"] = hex(address)
        save()
        print("incoming LR", hex(address))


if __name__ == "__main__":
    main()
