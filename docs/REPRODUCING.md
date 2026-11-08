# Reproducing the research

This repository does not distribute vendor firmware, captures or keys. Every analysis
here starts from files you produce yourself from **your own** Ranked Nova N60 and the
official updater. The scripts that acquire them are included. Compare the SHA-256 of your
files with `evidence/MANIFEST.json` and the run logs to see whether your board has the
same revision as the one analysed.

## 0. Setup

- Python 3.10+ with `hidapi`, `keystone-engine`, `capstone` and `unicorn` in a virtual
  environment. Install the flasher with
  `python -m pip install git+https://github.com/patsys/ry72xx-flasher`.
- macOS: if Karabiner-Elements runs, disable "Modify events" for the Nova; the flasher
  already opens HID devices non-exclusively.
- Work in an empty directory outside this repository. Never commit the files you create.
- Read a script before running it. Read-only scripts say so in their docstring; the
  flasher and `research/06-stock-restore/` can write the application pages.

## 1. Your own update capture (offline analyses, v1.0.5 loader profile)

1. Install USBPcap on Windows and start a capture on the root hub of the keyboard.
2. Run the official Ranked updater for your keyboard once.
3. Stop the capture and save it as little-endian PCAP (`.pcap`, not `.pcapng`) under the
   name `fw_update.pcap` in your working directory.

Scripts that use it (they read `fw_update.pcap` from the current directory):

| Script | Output |
|---|---|
| `research/01-update-capture/scripts/analyze_upload_capture.py` | packet chronology of the update |
| `research/01-update-capture/scripts/extract_vendor_stub.py` | the vendor RAM loader from your capture (`vendor_stub.bin`) |
| `ry72xx-flasher --setup-capture fw_update.pcap` | private loader profile for the capture-based loader option |
| `research/02-update-crypto/` | analysis of the update container; inputs are derived from your capture |

## 2. Your own flash backup (read-only)

Any bootloader revision (v1.0.5 or v1.0.7):

    ry72xx-flasher --probe --enter-stock     # stock firmware running
    ry72xx-flasher --probe                   # QMK running: hold Esc while plugging in

This reads the whole 128 KiB flash and the 512-byte info-flash metadata twice, compares
them, writes nothing and returns the keyboard to its firmware. The result directory
(printed by the tool) contains `before_flash.bin`, `after_flash.bin` and
`before_metadata.bin`.

Bootloader v1.0.5 only, the original acquisition path:

    python research/04-firmware-dump/scripts/dump_firmware_live.py

It writes `firmware_dump/flash_cpu_pass1.bin`, `flash_cpu_pass2.bin`,
`bootloader_0x0000.bin` and `application_plaintext_0x2000.bin`. With a `--probe` backup
instead, create those names yourself: `flash_cpu_pass1.bin` and `flash_cpu_pass2.bin`
from `before_flash.bin`/`after_flash.bin`, `bootloader_0x0000.bin` = bytes
`0x0000..0x1FFF`, `application_plaintext_0x2000.bin` = bytes `0x2000..0x1EBFF`.

Bootloader v1.0.7, including the info flash and side-effect-free peripheral registers:

    cd research/08-bootloader-v107
    python v107_read.py dump 0 0x20000 flash.bin
    python v107_read.py dump 0x10000000 0x800 info.bin

## 3. Offline analysis of your backup

- `research/04-firmware-dump/scripts/analyze_firmware_dump.py` (reads `firmware_dump/`): disassembly and
  region checks.
- `research/04-firmware-dump/scripts/recover_scan_tables.py`, `recover_startup_ram.py`: key-scan tables and
  startup RAM from your dump.
- `research/08-bootloader-v107/xref_registers.py`: register cross-reference of your dump
  (edit `DUMP` at the top to point at your `flash.bin`).

## 4. Hardware experiments

- Flash-controller diagnostics write only scratch page `0xA0` and compare the whole flash
  and the info flash afterwards: `research/08-bootloader-v107/run_diag_v107.py`
  (`--matrix plan` or `--matrix race`). Bootloader v1.0.7 only.
- The timing-channel tools (`v107_lr_probe.py`, `v107_timing.py`) and the read stubs never
  write flash.
- After a failed write, never stop the flasher's recovery holder; restore first
  (`ry72xx-flasher --recover <result dir>`).

## 5. QMK

Build from the published branch https://github.com/patsys/qmk_firmware/tree/ranked-nova-platform
with the QMK CLI and the Arm GNU toolchain; the Neo2 and VIA keymaps are in
https://github.com/patsys/qmk_userspace (its GitHub Actions build produces ready images).
