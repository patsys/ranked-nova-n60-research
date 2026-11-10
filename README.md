# Ranked Nova N60 reverse engineering

A reproducible, evidence-led record of reverse engineering the Ranked Nova N60 keyboard, its vendor updater and bootloader, and a research QMK port. This repository contains the experiment history (including failed approaches), source tools, firmware/USB evidence, and test results.

> **Current status (10 November 2026):** a Ranked G65 on the same RY7203 bootloader v1.0.7 runs QMK with Neo2, VIA and RGB (keys and border, I2C LED controller); see [research/09-g65](research/09-g65/).
>
> **7 November 2026:** a second Nova N60 with the newer bootloader v1.0.7 runs QMK (Neo2 + VIA). The authored loader's lost-word failure was traced to the flash controller's STATUS timing, measured on a scratch page and fixed; the flasher supports v1.0.5 and v1.0.7. The QMK upstream candidate is prepared on a fork branch; no PR has been opened yet (photos and maintainer feedback pending). The first board has been soft-bricked since 4 November.
>
> Published components: [ry72xx-flasher](https://github.com/patsys/ry72xx-flasher) · [QMK branch](https://github.com/patsys/qmk_firmware/tree/ranked-nova-platform) · [QMK userspace](https://github.com/patsys/qmk_userspace)

## Start here

1. [Experiment log](docs/EXPERIMENT_LOG.md) — chronological attempts, failures, corrections, and lessons.
2. [Technical findings](docs/TECHNICAL_FINDINGS.md) — what the evidence supports and its confidence.
3. [Current status and next steps](docs/STATUS.md) — known-good behavior and open blockers.
4. [Bootloader v1.0.7 and flash controller](docs/BOOTLOADER_V107.md) — second board, new bootloader revision, STATUS timing root cause, register meanings.
5. [DrunkDeer comparison](docs/DRUNKDEER_COMPARISON.md) — tested the Nova master-key profile against public DrunkDeer updater images.
6. [Reproducing the tools](docs/REPRODUCING.md) — source layout, dependencies, and offline checks.
7. [Safety and evidence notes](docs/SAFETY_AND_PROVENANCE.md) — what each artifact represents and how hardware operations are bounded.

## Repository map

```
docs/                    narrative: log, findings, status, bootloader v1.0.7, reproducing, provenance
  history/               original working notes from the investigation
research/                one folder per phase, each with a README
  01-update-capture/     official updater capture, USB protocol
  02-update-crypto/      update encryption and key derivation
  03-bootloader-stubs/   own START stubs, timing and USB read channel
  04-firmware-dump/      full flash read and offline firmware analysis
  05-ram-bypass/         plaintext DATA bypass in RAM
  06-stock-restore/      bounded flashing and stock rollback
  07-qmk-port/           QMK platform bring-up, validation and persistence probes
  08-bootloader-v107/    second board, bootloader v1.0.7, flash-controller root cause
  09-g65/                Ranked G65: identification, read-only backup, boot decision
evidence/MANIFEST.json   size and SHA-256 of every file, including unpublished vendor material
```

See [research/README.md](research/README.md) for an overview of the phases and their outcomes.

Vendor firmware, update captures and key material are not published. Their sizes and SHA-256
values are in [`evidence/MANIFEST.json`](evidence/MANIFEST.json) (`"included": false`), and
[docs/REPRODUCING.md](docs/REPRODUCING.md) explains how to produce them from your own keyboard.
The SQLite research database is not included.

## Important limits

- The exact MCU ordering code is not established. The RY72xx platform family identification is stronger than any exact chip claim.
- A full CPU-visible firmware image was read and analyzed; that does not imply a raw SWD dump or complete physical-flash image.
- VIA settings persistence was reported working on the v1.0.7 board after the flash-driver timing fix; it has not been re-measured with raw-flash evidence as in section 6 of the log.
- The v1.0.7 bootloader, stock firmware, info-flash and RAM dumps of the second board are not published (hashes only).
- The flasher ([ry72xx-flasher](https://github.com/patsys/ry72xx-flasher)) can write firmware. Read its safety documentation and use only a verified image for the matching board.

## Scope and licensing

The evidence was collected from a user-owned Ranked Nova N60 and its vendor updater. See `docs/SAFETY_AND_PROVENANCE.md` for artifact provenance and component licensing. Vendor firmware and captures are not part of this repository; see [LICENSES.md](LICENSES.md).
