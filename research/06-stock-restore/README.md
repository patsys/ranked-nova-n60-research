# 06 · Stock restore and bounded flashing

**When:** 3 November 2026 · **Status:** done

Before any QMK image was written, the stock application had to be restorable. Bounded stubs
derived from the vendor stub accept only application pages 16..132 and refuse the bootloader and
metadata regions. A first in-place rewrite of the stock application was verified against a
fresh double-read backup, and the same path later rolled back failed QMK images.

First rewrite: [STOCK_RESTORE_TEST.md](STOCK_RESTORE_TEST.md) · restore after QMK:
[STOCK_RESTORED_20261103.md](STOCK_RESTORED_20261103.md).

## Contents

| Path | What it is |
|---|---|
| `build_bounded_stub*.py`, `build_hold_stub.py`, `build_release_stub.py` | Builders for the bounded, hold and release stubs |
| `validate_*.py`, `*_validation.json` | Offline emulation of the stubs and the protocol transitions |
| `restore_stock.py` | Host-side restore tool |
| `scripts/snapshot_stock_preflight.py` | Double-read backup before the write |
| `results/20261103T052626Z/` | Preflight snapshot record |

## Reports in this folder

| Report | Topic |
|---|---|
| [BOUNDED_STUBS.md](BOUNDED_STUBS.md) | Design and limits of the bounded stubs |
| [HOST_REVIEW.md](HOST_REVIEW.md) | Review of the host-side restore path |
| [ROLLBACK_FROM_BOOT_REVIEW.md](ROLLBACK_FROM_BOOT_REVIEW.md) | Rolling back from the bootloader after a failed image |

## Not included

The stub binaries (patched vendor code) and the stock application pages are not published; the
builders recreate the stubs from your own `vendor_stub.bin`.

## Successor

The maintained flasher is [ry72xx-flasher](https://github.com/patsys/ry72xx-flasher).
