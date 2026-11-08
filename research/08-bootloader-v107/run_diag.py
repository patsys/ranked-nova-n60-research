# Copyright 2026 patsys
# SPDX-License-Identifier: GPL-3.0-or-later
"""Hardware runner: flash-controller experiments on one scratch page, no DATA.

Follows ry72xx-flasher's probe-only session (backup, verify, readback, release)
and inserts diag_stub experiments between backup and readback. The application,
bootloader, settings and hidden metadata are never addressed. The scratch page
must be erased (all FF) before the first experiment and is erased again before
the final whole-flash comparison.

usage: run_diag.py [--enter-stock] [--identify-only] [--page 0xA0] [--wait 600]
"""
import argparse
import ctypes
import json
import sys
import time
from pathlib import Path

import diag_stub as d
import identify
from ry72xx_flasher.image import START, digest, require
from ry72xx_flasher.profiles import V105
from ry72xx_flasher.loader import authored
from ry72xx_flasher.session import durable_write
from ry72xx_flasher.transport import HIDTransport

STATE = Path.home() / ".local/state/ry72xx-flasher"

# Each program experiment uses fresh words: NOR cells cannot be re-programmed without erase.
EXPERIMENTS = [
    ("erase", 0, (0, 0), d.ERASE),
    ("single even word (QMK style)", 0, (0x12345678, 0), 0),
    ("single odd word (QMK style)", 1, (0x9ABCDEF0, 0), 0),
    ("two words back to back (loader style)", 2, (0x0F1E2D3C, 0x4B5A6978), d.TWO_OPS),
    ("two words + ADDRESS rewrite (stock style)", 4, (0x11223344, 0x55667788), d.TWO_OPS | d.REWRITE_ADDRESS),
    ("two words + delay", 6, (0x99AABBCC, 0xDDEEFF00), d.TWO_OPS | d.DELAY),
    ("two words + rewrite + delay", 8, (0x13579BDF, 0x2468ACE0), d.TWO_OPS | d.REWRITE_ADDRESS | d.DELAY),
    ("two words starting odd", 11, (0xA5A5A5A5, 0x5A5A5A5A), d.TWO_OPS),
    ("final erase", 0, (0, 0), d.ERASE),
]


def shared_hid_open():
    """macOS hidapi seizes devices by default; the stock vendor collection shares the keyboard interface."""
    if sys.platform == "darwin":
        import hid
        ctypes.CDLL(hid.__file__).hid_darwin_set_open_exclusive(0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--enter-stock", action="store_true", help="send the stock mode-switch command")
    parser.add_argument("--page", type=lambda v: int(v, 0), default=0xA0)
    parser.add_argument("--wait", type=float, default=600)
    parser.add_argument("--identify-only", action="store_true", help="backup and read-only identification; no flash operation")
    args = parser.parse_args()
    require(d.SCRATCH_FIRST <= args.page <= d.SCRATCH_LAST, "Page outside the scratch window")

    output = STATE / time.strftime("flashdiag_%Y%m%dT%H%M%S")
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    log = dict(page=hex(args.page), experiments=[])
    save = lambda: durable_write(output / "result.json", json.dumps(log, indent=1).encode())
    shared_hid_open()
    header = authored()[0]  # the flasher's own plaintext START header
    transport = HIDTransport(header, enter_stock=args.enter_stock, wait_seconds=args.wait)
    print(f"Output {output}\nWaiting for the bootloader...", flush=True)
    log["boot_version"] = transport.open()
    try:
        log["core_before"] = transport.core(True)
        boot = transport.read(0, START)
        require(digest(boot) == V105.boot_sha, "Unsupported bootloader; nothing sent")
        print("Bootloader verified; backing up whole flash (about a minute)", flush=True)
        before = transport.read(0, 0x20000)
        metadata = transport.read(0x10000600, 512, metadata=True)
        durable_write(output / "before_flash.bin", before)
        durable_write(output / "before_metadata.bin", metadata)
        require((output / "before_flash.bin").read_bytes() == before, "Backup persistence verification failed")
        page = before[args.page * 512:(args.page + 1) * 512]
        require(page == b"\xff" * 512, "Scratch page is not erased on this board; refusing to use it")
        log.update(before_flash_sha256=digest(before), before_metadata_sha256=digest(metadata))
        save()

        print("Read-only identification: ROM table, controller registers, info flash", flush=True)
        log["identify"], controller, info = identify.identify(transport)
        durable_write(output / "flash_controller_regs.bin", controller)
        durable_write(output / "info_flash_10000000.bin", info)
        save()
        print(json.dumps(log["identify"]["rom_table"], indent=1), flush=True)

        for name, word, values, flags in [] if args.identify_only else EXPERIMENTS:
            stub = d.diag_stub(args.page, word, values, flags)
            result = d.parse(transport.start(stub, 40))
            expected = None if flags & d.ERASE else [hex(values[0])] + ([hex(values[1])] if flags & d.TWO_OPS else [])
            got = [result["word0"]] + ([result["word1"]] if flags & d.TWO_OPS else [])
            entry = dict(name=name, word=word, flags=flags, values=[hex(v) for v in values], result=result,
                         ok=(result["word0"] == "0xffffffff") if expected is None else got == expected)
            log["experiments"].append(entry)
            save()
            print(f"{'OK  ' if entry['ok'] else 'DIFF'} {name}: {result}", flush=True)

        after_page = transport.read(args.page * 512, 512)
        require(after_page == b"\xff" * 512, "Scratch page not erased after the final erase")
        log["core_after"] = transport.core(False)
        after = transport.read(0, 0x20000)
        after_metadata = transport.read(0x10000600, 512, metadata=True)
        durable_write(output / "after_flash.bin", after)
        log.update(whole_flash_unchanged=after == before, hidden_metadata_unchanged=after_metadata == metadata)
        save()
        require(after == before and after_metadata == metadata, "Flash differs from the backup; not releasing")
        transport.release()
        log["released"] = True
        save()
    finally:
        transport.close()
    log["final_state"] = transport.wait_application()
    save()
    print(json.dumps({k: log[k] for k in ("whole_flash_unchanged", "hidden_metadata_unchanged", "final_state")}, indent=1))


if __name__ == "__main__":
    sys.exit(main())
