# Copyright 2026 patsys
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only G65 backup through ry72xx-flasher's own read stubs (v1.0.7 profile).

Only core and read START stubs are sent: no loader, no DATA, no release.
The stubs' guard returns without replying unless the bootloader's native LR and
saved return match v1.0.7, so a differently laid-out bootloader just times out.
"""
import hashlib, json, os, sys, time
from pathlib import Path

from ry72xx_flasher.loader import authored
from ry72xx_flasher.profiles import V107
from ry72xx_flasher.transport import BOOT, HIDTransport

digest = lambda b: hashlib.sha256(b).hexdigest()
out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=False, mode=0o700)
log = dict(board="Ranked G65 / Guardian 65%", app_usb="3532:a0c2", getv="a1070000a1020000", profile_used=V107.name)
save = lambda: (out / "result.json").write_text(json.dumps(log, indent=1))


def write(name, data):
    path = out / name
    with open(path, "wb") as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    assert path.read_bytes() == data


t = HIDTransport(authored()[0])
boots = t.hid.enumerate(*BOOT)
assert len(boots) == 1 and not t.hid.enumerate(0x3532, 0xA0C2), "Need exactly the G65 bootloader"
t.path = boots[0]["path"]
t.handle = t.hid.device()
t.handle.open_path(t.path)
t.profile = V107
try:
    log["core_before"] = t.core(True); save()
    boot = t.read(0, 0x2000)
    write("boot.bin", boot)
    log.update(boot_sha256=digest(boot), boot_matches_n60_v107=digest(boot) == V107.boot_sha,
               boot_version_string=boot[0xC0:0xD8].split(b"\0")[0].decode("latin1"))
    save(); print(json.dumps({k: log[k] for k in ("boot_sha256", "boot_matches_n60_v107", "boot_version_string")}), flush=True)
    for n in (1, 2):
        t0 = time.monotonic()
        flash = t.read(0, 0x20000)
        meta = t.read(0x10000600, 512, metadata=True)
        write(f"flash_{n}.bin", flash); write(f"metadata_{n}.bin", meta)
        log[f"pass_{n}"] = dict(flash_sha256=digest(flash), metadata_sha256=digest(meta), seconds=round(time.monotonic() - t0, 1))
        save(); print(f"pass {n}:", json.dumps(log[f"pass_{n}"]), flush=True)
    log["passes_match"] = log["pass_1"] == {**log["pass_2"], "seconds": log["pass_1"]["seconds"]}
    log["boot_region_stable"] = flash[:0x2000] == boot
    log["core_after"] = t.core(False)
    save()
finally:
    t.close()
print(json.dumps({k: log[k] for k in ("passes_match", "boot_region_stable")}))
