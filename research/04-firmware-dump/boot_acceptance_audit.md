# Boot startup and application acceptance audit

Offline instruction execution against the recovered bootloader was combined with the separately live-read 512-byte information block. No hardware access, installation, or flash writes were performed by this audit. Reproduce with `audit_boot_acceptance.py`; detailed results are in `boot_acceptance_validation.json`.

## Result relevant before flashing

**The captured information block selects a patch-list boot path that skips the bootloader's application checksum checks. Both current QMK ELFs reach the original bootloader's application jump in emulation with the captured block unchanged.** This establishes conditional bootloader control flow, not successful hardware boot or a safe installation/restore procedure.

The same path also reaches the application jump with a corrupted application or information-block checksum. Consequently, checksum failure is **not an automatic recovery guarantee in this device's captured configuration**. A broken application can still be selected. Recovery entry and transport safety require the separate recovery audit and an actual restore plan.

## Reset to main

The boot vector at address4 contains `0x1cd`. At `0x1cc`, the reset trampoline branches through literal `0x1e8` to `0xd9`. Startup `0xd8` installs SP `0x20000bf0`, calls scatter initialization `0x150`, and branches through `0xe4` to main `0x701`.

Actual original instructions were executed from reset until main `0x700`: 1005 RAM writes, all inside `0x20000000..0x20000bf0`. This part contains initialization rather than application authentication. Earlier silicon ROM/reset behavior outside the extracted bootloader is not covered.

## Information block actually captured

The 512-byte block at CPU address `0x10000600..0x100007ff` is outside the original 128KiB flash capture. Its separate capture is `boot_safety_audit/metadata_10000600.bin`, SHA-256 `3bce58cb1e15aa6adfb8120c12b6911466a8d1f611a3efeefcb72c6bd7ca4d49`.

| Block offset | Address | Captured value / meaning in boot code |
|---|---|---|
| `0x1c` | `0x1000061c` | `1`: normal checksum-path application tag |
| `0x24` | `0x10000624` | `0xe908`: application checksum length, ends at `0x10908` from base `0x2000` |
| `0x28` | `0x10000628` | `0x25a4f084`: XOR of original application words over that length |
| `0x100` | `0x10000700` | `0xffffffff`: no configured recovery pin pair |
| `0x114` | `0x10000714` | `0xffffffff`: use default retained boot-request magic |
| `0x150/154` | `0x10000750/754` | Patch address `0x400130e8`, value `0xffff0000` |
| `0x158/15c` | `0x10000758/75c` | Patch address `0x400130ec`, value `0xffffffff` |
| `0x1fc` | `0x100007fc` | `0x488a27bc`: XOR of information-block words before this final word |

Both captured checksum values independently match the recovered bytes. Register addresses `0x400130e8/ec` are in the flash-controller neighborhood, but their exact protection-bit semantics have not been established by this control-flow test. They must not be treated as harmless general RAM or guessed erase commands.

## Two distinct acceptance paths

After retained-request handling, main reads `0x10000750` at `0x7a8..0x7b0`.

When that value is **not** `0xffffffff`, code `0x7b2..0x7de` validates up to eight patch addresses. Each non-sentinel address must be greater than `0x400130ce`, less than `0x400130f0`, and word aligned: the effective permitted addresses are `0x400130d0..0x400130ec` in steps of4. Invalid addresses select reason `0xffff0002`, whose low16 bits select the USB boot server. After valid entries, `0x7e0` branches directly to `0x83c`, bypassing all code `0x7fe..0x838`.

That is the path selected by the captured `e8/ec` patch entries. At `0x892..0x8b4`, the original code replays those address/value pairs. At `0x8b6..0x8c0`, it loads the application reset pointer from `0x2004`, stores a copy at `0x200001e8`, and calls it with `BLX r0`. This sequence does not load the initial application SP from `0x2000`; the replacement startup initializes its own MSP/PSP.

When the first patch address **is** `0xffffffff`, the alternative path can check the configured recovery GPIO pair, then requires nonzero tag/length fields (`0x7fe..0x808`). It executes `0x40c` over `0x10000600` for `0x1fc` bytes, comparing the result with `0x100007fc` at `0x818..0x81c`; requires tag exactly1 at `0x826..0x82a`; and executes `0x40c` over application base `0x2000` for the configured length, comparing with `0x10000628` at `0x834..0x838`. This helper XORs aligned 32-bit words; it is not a cryptographic signature verifier.

No reset-vector address range, Thumb-bit, or initial-SP validation is present in these inspected jump paths. A compensated-XOR invalid-vector fixture passes the normal checksum segment, and a corrupted application passes the captured patch-list path. This statement concerns these recovered paths, not hypothetical silicon features outside the dump.

## Reproduced tests

Nine synthetic normal-path fixtures execute original code `0x77c..0x83c` and helper `0x40c`: original data with matching checksums passes; basic/VIA QMK overlays with stale original checksums select the boot server; updated synthetic checksums pass; invalid metadata checksum, zero tag, or zero length select the boot server; a zero reset pointer with compensated XOR passes the segment.

Six captured-block fixtures continue to the real application-call instruction at `0x8c0`, or stop at USB-server selection `0x848`: original, basic QMK and VIA QMK all reach the application call without invoking checksum helper `0x40c`; a changed application byte and a changed metadata-checksum word also reach it; an out-of-range patch address selects the boot server. The two valid patch writes are recorded only in emulated MMIO backing memory.

These checks do not test physical flash protection, actual programming, reset persistence, exception entry timing, USB enumeration after installation, recovery from a nonworking application, or the silicon's real watchdog behavior.
