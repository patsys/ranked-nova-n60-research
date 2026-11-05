# What has been recovered

## Current update — 2026-11-03

The later work includes a functioning QMK/VIA diagnostic port, recovered key
acquisition/mapping, bounded application flashing, verified stock rollback,
and automatic diagnostic trace recovery. The user has confirmed operation.
See [the process guide](../REVERSE_ENGINEERING_GUIDE.md) and
[successful result](../qmk_flash/SUCCESS_20261103.md). Exact MCU part, complete
memory/OTP coverage, keys for other untested profiles, original source and complete
production validation remain unresolved. The older archive is not a current
complete-workspace backup.

The captured update's AES transform, embedded master key and per-file key are
now recovered and verified: [key extraction](../crypto_research/README.md).

## Historical dump-bundle coverage

Verified coverage is the complete **CPU-visible address range 0x00000000 to
0x0001ffff (128 KiB)**, read twice with identical results. This is not proof
that the chip has no additional memory outside that range.

Included:

- Full 128 KiB snapshot and independent verification copy.
- 8 KiB bootloader-region binary.
- Plaintext application-region binary at 0x2000, with extent inferred from
  the captured update image.
- Vector table, reset/startup listings, and raw linear Thumb disassembly.
- USB request/reply evidence, hashes, tools, and the current SQLite record.
- Demonstrated RAM-code execution and direct USB readback.
- Located bootloader crypto-control code and a hardware-assisted block path.

Not established or recovered:

- Exact MCU part number and complete peripheral documentation.
- A complete GPIO/key-matrix/LED pin map or a working QMK port.
- Original C source, full function reconstruction, or vendor build files.
- Complete RAM, OTP/fuse contents, or an identified encryption key/algorithm.
- A tested flash restore/programming procedure. The existing work is read-only
  with respect to flash; no erase/program test was performed.

The archive is an evidence/analysis bundle, **not an installable firmware
package**. Byte addresses and load bases are documented in README.md.
