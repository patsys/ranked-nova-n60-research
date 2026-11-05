# Ranked Nova N60 reverse engineering

A reproducible, evidence-led record of reverse engineering the Ranked Nova N60 keyboard, its vendor updater and bootloader, and a research QMK port. This repository contains the experiment history (including failed approaches), source tools, firmware/USB evidence, and test results.

> **Current status (5 November 2026):** the experimental QMK image runs on the keyboard, and physical checks for typing, Neo2, lighting, NKRO, key wake, and the QMK CLI flash path succeeded. Persistent VIA settings are **not working reliably**. A final read-only flash probe found the expected storage word erased and the test slot back at its default value. The QMK contribution is not ready and no PR has been opened.

## Start here

1. [Experiment log](docs/EXPERIMENT_LOG.md) — chronological attempts, failures, corrections, and lessons.
2. [Technical findings](docs/TECHNICAL_FINDINGS.md) — what the evidence supports and its confidence.
3. [Current status and next steps](docs/STATUS.md) — known-good behavior and open blockers.
4. [DrunkDeer comparison](docs/DRUNKDEER_COMPARISON.md) — tested the Nova master-key profile against public DrunkDeer updater images.
5. [Reproducing the tools](docs/REPRODUCING.md) — source layout, dependencies, and offline checks.
6. [Safety and evidence notes](docs/SAFETY_AND_PROVENANCE.md) — what each artifact represents and how hardware operations are bounded.

## Repository map

- `docs/` — narrative, timeline, technical results, status, and provenance.
- `programs/analysis/` — capture parsing, firmware analysis, and research utilities.
- `programs/read-only-stubs/` — source and evidence for the diagnostic bootloader stubs and RAM readers.
- `programs/crypto/` — offline cipher/key analysis scripts and their captured-profile fixtures.
- `programs/ram-bypass/` — RAM-only plaintext experiments.
- `programs/qmk-platform/`, `programs/qmk-keyboard/`, `programs/qmk-userspace/` — the locally authored QMK platform, keyboard, and userspace sources; the upstream QMK checkout is not vendored.
- `programs/flasher/` — bounded RY72xx flasher source and tests.
- `programs/stock-restore/` — stock rollback/hand-off builders, validation, and documentation.
- `evidence/` — captures, firmware analysis, validation reports, and the final read-only persistence probe.

The SQLite research database is intentionally excluded. The file list and SHA-256 hashes for included evidence are in [`evidence/MANIFEST.json`](evidence/MANIFEST.json).

## Important limits

- The exact MCU ordering code is not established. The RY72xx platform family identification is stronger than any exact chip claim.
- A full CPU-visible firmware image was read and analyzed; that does not imply a raw SWD dump or complete physical-flash image.
- VIA key remapping and VIA protocol communication work in RAM. **Cold-power persistence remains an unresolved blocker.**
- The persistence driver is experimental. Do not treat it as safe general-purpose NVM or as upstream-ready.
- The included flasher can write firmware. Read its safety documentation and use only a verified image for the matching board.

## Scope and licensing

The evidence was collected from a user-owned Ranked Nova N60 and its vendor updater. See `docs/SAFETY_AND_PROVENANCE.md` for artifact provenance and component licensing. Firmware and captures are research evidence; their inclusion does not assert ownership of vendor copyrights.
