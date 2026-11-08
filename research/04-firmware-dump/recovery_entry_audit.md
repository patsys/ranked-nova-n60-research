# Bootloader recovery-entry audit

**This unit has no verified application-independent recovery entry yet.** The
captured configuration disables the bootloader's GPIO-low override. Its enabled
register-patch path also bypasses the application's checksum-validation branch.
Consequently, a broken application is not guaranteed to bring up USB recovery.

This conclusion comes from the original bootloader machine code, the captured
512-byte metadata at `0x10000600`, and offline execution of both together. No
device was accessed or modified by this audit. USB bootstrap is a control-flow
destination here, not a physically tested enumeration/recovery outcome.

## Actual captured configuration

Source: `firmware_dump/boot_safety_audit/metadata_10000600.bin`.

| Address | Value | Relevant effect |
|---|---|---|
| `0x10000700` | `0xffffffff` | Skip configuring and reading the two boot-selection GPIOs. |
| `0x10000714` | `0xffffffff` | Use default retained-request magic `0x5ac396c5`. |
| `0x10000750/+54` | `0x400130e8`, `0xffff0000` | First enabled register patch. |
| `0x10000758/+5c` | `0x400130ec`, `0xffffffff` | Second enabled register patch. |

These addresses are in the same 512-byte metadata block as the application
length/checksum fields. This audit does not infer the undocumented electrical
meaning of the two flash-controller-area configuration registers.

## Original entry flow

Reset vector `0x1cd` enters startup `0xd8`, which executes scatter initialization
at `0x150` and transfers to boot main at `0x700`.

1. Boot main configures and verifies clock registers. The modeled register
   storage reflects its writes; delay helper `0x9bc` is intercepted offline.
2. At `0x77c..0x7a6`, read retained register `0x4001400c`. If it matches the
   configured request value (or default `0x5ac396c5` when configuration is FF),
   set mode 2, clear that register, and branch to USB bootstrap. This happens
   before application validation or vector reads.
3. At `0x7a8..0x7e0`, if the first register-patch address at `0x10000750` is not
   FF, validate up to eight patch targets. Valid targets must be aligned and
   strictly inside `(0x400130ce,0x400130f0)`. Invalid targets select USB mode.
   **A valid list branches directly to `0x83c`, bypassing `0x7fe..0x83a`.**
4. Only when the patch list is absent, an optional GPIO override and the
   metadata/application checksum branch are reached. With a configured pin
   pair, both pin reads low select USB mode before reading application bytes.
5. At `0x83c`, low 16 bits of mode equal to 2 select USB bootstrap at `0x848`.
   Otherwise, `0x892..0x8b4` applies the register patches. `0x8b6..0x8c0` reads
   the word at application address `0x2004` and executes `BLX` to it.

With this unit's enabled, valid patch list, mode remains zero unless a retained
request has already selected USB. The absent GPIO configuration cannot provide
a physical override, and the checksum branch is not executed.

## GPIO override: present in code, disabled in this unit's metadata

When the config word at `0x10000700` is not FF, it supplies:

```
pinA = word & 0x3f
pinB = (word >> 8) & 0x3f
```

The original helper `0x464` configures these encoded pins with the value
`0x0802 | (5<<4)` at the decoded pin configuration address. Helper `0x48c`
reads `0x40018030 + 4*((pin>>5)&3)` and extracts bit `pin&31`.
At `0x7e2..0x7fc`, both extracted bits must be zero to select USB mode.

The captured FF configuration disables this code, independently of whether
keys are held. No physical keyboard key combination can be named from that
disabled configuration. These encoded GPIO IDs would not, by themselves,
prove a correspondence to the keyboard's analog sensor keys or package pins.

There could still be undocumented hardware straps, system-ROM ISP modes,
debug interfaces, or factory pads outside this flash program. None is proved
by the recovered bootloader or these tests. Do not present one as a known
recovery procedure.

## Application-requested bootloader mode

The original application's reset primitive at `0x3ed8` writes:

```
*(uint32_t *)0x4001400c = 0x5ac396c5
*(uint32_t *)0xe000ed0c = 0x05fa0004  // ARM system reset request
```

It then loops at `0x3eec`. This matches the boot main's default request path.
The known original application USB command `04 A5 01` relies on application
code eventually reaching this primitive; receiving it is not a demonstrated
option after installing an application that cannot initialize USB or execute.
Setting the retained magic through another means would still need a working
execution/debug path. Retention across a particular physical reset/power cycle
must not be assumed solely from an ordinary memory-storage emulator.

## Offline test evidence

Run `firmware_dump/test_recovery_entry.py`. Results are saved in
`firmware_dump/recovery_entry_validation.json` with binary/metadata hashes.

- Original startup scatter initialization reaches boot main.
- 18 synthetic entry cases cover original/blank applications, default and
  configured request values, request mismatch, both-low versus either-high
  configured GPIOs, GPIO override disabled, erased metadata, and invalid
  register-patch targets.
- Eight cases use **the actual captured metadata**, with original application,
  erased application, invalid reset vector `0xdeadbeef`, or a changed body byte,
  each with retained request zero or the default magic.
- With request zero, all four actual-metadata application variants reach the
  application `BLX` at `0x8c0`; only `0x2004` is read from the app. The erased
  application supplies target `0xffffffff`, and the invalid vector supplies
  `0xdeadbeef`. The checksum block and GPIO read helper are never reached.
- With default request magic, all four reach USB bootstrap before any app read.
- Original application primitive execution performs exactly the two request
  and reset-register writes shown above.

Tests stop before USB initialization or the application `BLX`. They do not
prove USB enumeration, actual reset retention, flash-controller side effects,
successful reflashing, or recovery after a failed installation. The source and
observed configuration warrant retaining the current no-install boundary until
an application-independent recovery route is demonstrated.
