# Bootloader crypto path and QMK feasibility update

> Historical analysis followed by successful plaintext application flashing,
> verified stock rollbacks and working QMK/VIA. The AES transform and keys were
> subsequently recovered and verified offline for the captured update; see
> [key extraction](../02-update-crypto/KEY_RECOVERY.md) and
> [the full process](../../docs/history/REVERSE_ENGINEERING_GUIDE.md).

The verified bootloader contains the control code for firmware transformation.
Static disassembly shows the encrypted DATA path runs two loops in 16-byte
steps, calling 0x029c at 0x0d60 and 0x0d9a before dispatching erase/program
through 0x0214 and 0x0220. The programming buffer was independently observed
as plaintext-like vector data, and the full application CPU view is now read.

Relevant functions and literals:

- 0x029c: 16-byte input/output operation, using descriptor 0x20000314 and
  peripheral base 0x4000d000, triggering and checking peripheral status.
- 0x0330: initializes that descriptor's buffer pointers and the peripheral.
- 0x0398: copies 16 bytes into the descriptor's configuration/key buffer.
- 0x0d4c–0x0db4: selects the two configurations and processes DATA blocks.
- 0x0e14 / 0x0e26: dispatches the uploaded erase/program functions afterward.

This supports hardware-assisted block processing driven by bootloader code.
It does not yet identify the hardware cipher, exact key derivation, key source,
or all boot-time validity checks. Absence of common S-box/TEA constants does
not rule out those algorithms when hardware performs the primitive.

The original programming routine consumes a CPU-visible RAM buffer, so an
alternative programmer could in principle consume plaintext directly. Sending
plaintext through the unmodified encrypted vendor DATA path is not equivalent:
that path would still apply its transformations. Any installation method
must deliberately bypass or account for that processing and satisfy boot
validity requirements. No installation/erase/program experiment was done.

Later RAM-only testing verified that clearing 0x20000214 after START makes
DATA deliver all 512 plaintext bytes unchanged to a diagnostic programming
entry. The crypto-enabled control transformed the same input. No firmware
installation was performed. Bootloader/application code matched the backup;
small data-journal appends were observed and reproduced by an ordinary read
session. See `../ram_bypass_test/README.md`.

## QMK

The old blanket infeasibility conclusion is superseded: custom code execution
and plaintext firmware access are demonstrated. This does not establish an
existing compatible QMK build. The exact MCU and peripherals still need to
be identified, followed by clock/USB/GPIO/timer support and matrix mapping.
The initial stack pointer alone is not a reliable measurement of total SRAM.

Official QMK Arm guidance uses ChibiOS/ChibiOS-Contrib support; a new MCU
family entails a platform port, beyond adding a keyboard definition:
https://docs.qmk.fm/platformdev_selecting_arm_mcu
https://docs.qmk.fm/porting_your_keyboard_to_qmk

SonixQMK documents support for certain Sonix/eVision rebrands. That becomes
relevant only if this board's exact silicon is confirmed to match; the earlier
Yichip guess and a shared Royuan updater do not establish that:
https://sonixqmk.github.io/SonixDocs/

The useful sequence is MCU identification, recovery/boot-check analysis,
minimal RAM-only clock/USB/GPIO experiments, matrix reconstruction, then a
matching QMK platform/board build. A stock plaintext backup is available;
a verified restore writer is still a separate, unperformed requirement.
