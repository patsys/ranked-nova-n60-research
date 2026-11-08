# Verified firmware read — 2026-11-02

The CPU-visible 128 KiB range 0x00000000–0x0001ffff was read twice through
our guarded own RAM stub and native USB transmit callback. Both reads matched
byte-for-byte. This is a live memory dump, not an offline guess at the cipher.

The dumps themselves (flash images, bootloader and application regions, RAM
snapshots, the info-flash block and the linear disassembly listings) contain
vendor firmware and are not included in this repository. Produce them from your
own keyboard as described in `docs/REPRODUCING.md` and compare the SHA-256
values below and in `evidence/MANIFEST.json`.

- Full CPU flash snapshot: `flash_cpu_pass1.bin` (131,072 bytes).
- Independent verification pass: `flash_cpu_pass2.bin`.
- Bootloader region: `bootloader_0x0000.bin` (8,192 bytes, base 0).
- Application region: `application_plaintext_0x2000.bin` (117,760 bytes,
  base 0x2000, sliced to the captured image extent 0x1cc00).
- Initial stack pointer: 0x20001c50; reset vector: 0x00002211.
- The reset stub branches through a literal to 0x20d9 in Thumb mode.

Full SHA256: `5adca278d90a0672e05dfe5ad47d1635242f9ec0ff78827d83d9f28d6ccd8b49`.
Application SHA256: `24c9420a5cd1df4bc06472aad07965b360f7341815f234da109971246ed964c0`.
Bootloader SHA256: `e46c6d9300a13f4d2eea7c16584d24ea6e4e1b83815e5f84f389d4aeb0915f62`.

`application_thumb_linear.txt` and `bootloader_thumb_linear.txt` (not included) provide raw
linear ARM Thumb disassembly. They include vector tables, literal pools and
data interpreted by the disassembler; they are not recovered C source or a
complete function reconstruction. `startup_thumb.txt` (not included) is a focused listing
at the reset-selected startup entry. Import the binaries as little-endian
ARM/Thumb with the load bases above for further analysis.

The application extent is inferred from the captured image size. Its code and
vector base are verified; an exact byte-for-byte mapping of every vendor data
partition into flash has not been independently reconstructed. The full flash
snapshot remains the authoritative read of the selected CPU address range.
This does not establish whether physical flash cells or SWD reads expose the
same representation, identify the cipher/key, or identify the exact MCU part.

The reader returns up to 56 data bytes per START using the native transmit
callback at context+0x214. The own payload modifies a guarded RAM-stack return
word and writes the native RAM reply buffer; it has no flash controller,
erase/program or peripheral access. No firmware DATA or COMPLETE packet was
sent during these dumps. A callback-body mock is used only in offline bounded-
write emulation; physical USB replies and the two matching passes validate
the live output independently.

The normal START/getv cleanup returned the device to six application HID
collections and zero bootloader interfaces. Application USB enumeration is
verified; a complete keyboard functional or separate flash-integrity test was
not performed. Raw request/reply evidence is in `usb_transactions.json` and
the two-pass metadata is in `manifest.json`.
