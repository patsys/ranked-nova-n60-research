# 08 · Bootloader v1.0.7 and the flash-controller root cause

**When:** 7 November 2026 · **Status:** done

A second Nova N60 reported bootloader v1.0.7, which all existing tools refused. Register-only
START timing probes recovered its native call frame, and a new read stub read flash, info flash
and peripheral registers. Diagnostics on a scratch page then showed why the authored loader lost
every second word: the flash controller reports busy one STATUS read late, and writes during
that window redirect the running operation. Polling the right bits fixed it, and QMK with VIA was
flashed and verified on this board.

Full write-up: [docs/BOOTLOADER_V107.md](../../docs/BOOTLOADER_V107.md).

## Contents

| Path | What it is |
|---|---|
| `identify.py` | Read-only identification: ROM table IDs, controller registers, info flash |
| `v107_timing.py`, `v107_lr_probe.py` | START timing reads for the v1.0.7 frame |
| `v107_stubs.py`, `v107_read.py`, `test_v107_stubs.py` | v1.0.7 read stub, flash reader and its emulator tests |
| `diag_stub.py`, `test_diag_stub.py`, `run_diag.py`, `run_diag_v107.py` | Flash-controller diagnostics on one scratch page |
| `xref_registers.py` | Cross-reference of peripheral register accesses |
| `via_load_layers.py`, `neo2_via_layers.json` | Load keymap layers into a running VIA image |
| `results/` | Timing and LR readbacks, register snapshot and run logs (`runs/`) |

## Not included

The v1.0.7 bootloader, stock firmware, info-flash and RAM dumps of this board are not published;
`results/register_snapshot_v107.json` records their sizes and SHA-256 values.
