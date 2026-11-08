# 07 · QMK port

**When:** 3–5 November 2026 · **Status:** works; persistent VIA was not verified on this board

QMK was brought up on the recovered RY72xx platform: startup and clock, the analog key scan,
USB device and Raw HID, RGB, VIA, NKRO and remote wake. Each step was built offline, flashed with
the bounded path from [06](../06-stock-restore/) and checked on the keyboard. Failures and their
fixes are kept next to the results. Persistent VIA storage did not work on the first board; the
root cause was found later on the second board ([08](../08-bootloader-v107/)).

This folder is the research history. The maintained code is in the
[QMK branch](https://github.com/patsys/qmk_firmware/tree/ranked-nova-platform) (platform and
keyboard) and the [QMK userspace](https://github.com/patsys/qmk_userspace) (Neo2 and VIA keymaps).

Build notes of the research tree: [RESEARCH_BUILD.md](RESEARCH_BUILD.md).

## Contents

| Path | What it is |
|---|---|
| `build_firmware.py`, `build_components.py`, `generate_keymap.py` | Research build scripts |
| `platform/` | Startup, clock calibration, platform integration, VIA build ([PLATFORM_INTEGRATION.md](platform/PLATFORM_INTEGRATION.md)) |
| `scan/` | Key-scan integration and validation |
| `usb/` | USB controller fixes, Raw HID transport, IRQ audit ([RAW_HID_TRANSPORT.md](usb/RAW_HID_TRANSPORT.md)) |
| `runtime/` | Emergency boot, sensor and USB diagnostics ([EMERGENCY_BOOT.md](runtime/EMERGENCY_BOOT.md)) |
| `rgb/` | RGB lighting ([README](rgb/README.md)) |
| `via/` | VIA definition and tests ([README](via/README.md)) |
| `neo2/` | Neo2 layout data and the key-timing fix ([TIMING_FIX_20261103.md](neo2/TIMING_FIX_20261103.md)) |
| `flash/` | Flashing the research images, recovery and soak tests ([SUCCESS_20261103.md](flash/SUCCESS_20261103.md)) |
| `validation/` | Build, lint, flasher and feature validation logs and results |
| `results/` | Persistence probes: `gate-clear-flash/` and `final-read-only-probe/` |
| `scripts/` | Porting-evidence and recovery-record scripts |

## Not included

Flash snapshots from the persistence probes contain the vendor bootloader and are not published;
`results/*/result.json` and `evidence/MANIFEST.json` keep their hashes.
