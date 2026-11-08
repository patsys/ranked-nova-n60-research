# QMK evidence audit

The existing dump/database is sufficient to continue software reverse
engineering without requiring more material from the user. It is not yet a
finished QMK hardware-support implementation.

Already available: verified bootloader/application CPU binaries; vectors and
startup; a RAM-code execution and USB-read mechanism; native USB transmit
path; DATA transform control and a tested RAM-only plaintext bypass; flash
layout; logical key indices, HID mapping and four-layer remap protocol.

Work to derive from those artifacts: coherent clock/GPIO/timer/USB register
definitions and drivers; physical matrix row/column pins and scan polarity;
RAM budget, startup/linker rules, boot validity checks, and a matching QMK
platform/board implementation. A tested restore writer is still separate.
MCU branding can help match an existing platform, but lack of a chip label
does not prevent continuing register-level analysis of the recovered drivers.

`porting_evidence.json` indexes candidate PC-relative peripheral literal
references and their instruction locations in the dump. This is a starting
index, not a proven physical pin map or a complete function analysis. Every
candidate must be checked against actual control flow; arbitrary 32-bit
words in a firmware binary are not reliable register evidence by themselves.

Prior YC500/Yichip attribution remains unconfirmed. Do not use it as an
established MCU identity, and do not infer total SRAM from the initial SP.
No device access, installation, erase, or programming was performed in this
audit. QMK is not yet built or demonstrated on this keyboard.
