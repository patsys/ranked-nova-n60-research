# 04 · Firmware read and offline analysis

**When:** 2–3 November 2026 · **Status:** done

The 128 KiB CPU-visible flash was read twice through the read channel from
[03](../03-bootloader-stubs/); both passes matched byte for byte. Offline analysis of that image
recovered the vector table, startup and RAM initialization, the USB driver and control paths,
the key-scan tables, the boot acceptance and recovery-entry logic, and the flash bounds. These
results are the basis of the QMK port in [07](../07-qmk-port/).

Dump details and hashes: [FIRMWARE_READ.md](FIRMWARE_READ.md).

## Contents

| Path | What it is |
|---|---|
| `scripts/` | Live dump, metadata read, offline emulation and analysis scripts |
| `audit_*.py`, `test_recovery_entry.py`, `trace_usb_driver_offline.py`, `recover_usb_control_offline.py` | Offline audits run against the dump |
| `*.md` | Analysis reports (see below) |
| `*.json` | Analysis results, offline traces and validation output |
| `usb_transactions.json`, `manifest.json` | Raw request/reply log and metadata of the two dump passes |
| `boot_safety_audit/` | Info-flash metadata block and factory clock read |
| `processor_identification/` | Notes on identifying the MCU |

## Reports in this folder

| Report | Topic |
|---|---|
| [COVERAGE.md](COVERAGE.md) | What the dump covers and what it does not |
| [BOOT_CRYPTO_AND_QMK.md](BOOT_CRYPTO_AND_QMK.md) | Boot path, crypto path and consequences for QMK |
| [boot_acceptance_audit.md](boot_acceptance_audit.md), [boot_reset_recovery_audit.md](boot_reset_recovery_audit.md), [boot_irq_dependency_audit.md](boot_irq_dependency_audit.md), [recovery_entry_audit.md](recovery_entry_audit.md) | Boot decision and recovery entry |
| [usb_driver_analysis.md](usb_driver_analysis.md), [usb_control_analysis.md](usb_control_analysis.md) | USB driver and control requests |
| [key_scan_analysis.md](key_scan_analysis.md) | Analog key-scan tables |
| [flash_bounds_audit.md](flash_bounds_audit.md), [PRE_FLASH_AUDIT.md](PRE_FLASH_AUDIT.md) | Safety checks before the first write |
| [qmk_platform_analysis.md](qmk_platform_analysis.md), [QMK_EVIDENCE_AUDIT.md](QMK_EVIDENCE_AUDIT.md), [recovery_recheck_after_qmk.md](recovery_recheck_after_qmk.md) | Evidence used for the QMK port |

## Not included

The flash images, bootloader and application regions, RAM snapshots and full disassembly
listings are vendor firmware and are not published. Create them from your own keyboard
([REPRODUCING.md §2](../../docs/REPRODUCING.md)) and compare against the SHA-256 values in
[FIRMWARE_READ.md](FIRMWARE_READ.md) and `evidence/MANIFEST.json`.
