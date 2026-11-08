# Research phases

Each folder is one phase of the investigation, in the order it happened. Every phase has a README
with the goal, the outcome, what the folder contains and what is not published. Scripts,
results and reports of a phase live together.

| Phase | Topic | Outcome |
|---|---|---|
| [01-update-capture](01-update-capture/) | Official updater capture, USB protocol | Protocol mapped; START carries a RAM stub |
| [02-update-crypto](02-update-crypto/) | Update encryption | AES-128 transform and key derivation verified |
| [03-bootloader-stubs](03-bootloader-stubs/) | Own START stubs, timing and USB read channel | 56-byte reads per START through the native reply path |
| [04-firmware-dump](04-firmware-dump/) | Full flash read and offline analysis | Matching double read; boot, USB, scan and flash logic recovered |
| [05-ram-bypass](05-ram-bypass/) | Plaintext DATA without decryption | Bypass proven in RAM, flash unchanged |
| [06-stock-restore](06-stock-restore/) | Bounded flashing and stock rollback | Stock rewrite and QMK rollbacks verified |
| [07-qmk-port](07-qmk-port/) | QMK on the RY72xx platform | Typing, RGB, VIA, NKRO, remote wake work; persistent VIA open on board 1 |
| [08-bootloader-v107](08-bootloader-v107/) | Second board, bootloader v1.0.7 | Flash-controller timing root cause fixed; QMK + VIA flashed |

The chronological story with failed attempts is in [docs/EXPERIMENT_LOG.md](../docs/EXPERIMENT_LOG.md).

## About paths inside the scripts

The scripts were written in the original working directory and still use its folder names
(`firmware_dump/`, `crypto_research/`, `readonly_stub/`, …). They read their inputs from
there, so set up those names in your working directory or adjust `ROOT` in the script. Inputs
that contain vendor firmware are not published; [docs/REPRODUCING.md](../docs/REPRODUCING.md)
explains how to create them from your own keyboard.
