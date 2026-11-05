# Keyboard analysis update — 2026-11-02

> Historical checkpoint. Later custom readback, firmware extraction and working
> QMK/VIA supersede its unresolved/current-state sections. Follow
> [the complete process guide](REVERSE_ENGINEERING_GUIDE.md).

Primary source: `ranked_re.db`, opened in SQLite read-only mode. Additional
checks: current Windows PnP enumeration and offline `fw_update.pcap` parsing.

## Current device

The connected device is `USB\VID_3532&PID_A0A3\RANKEDNOVA`, revision
`0004`, in application mode. Windows reports OK status for the composite
device and its HID children. MI_00 exposes a keyboard; MI_01 exposes two
keyboard collections, a vendor-defined collection (Col03), consumer control,
and a mouse collection. These are HID capabilities, not evidence of actual
mouse activity. No bootloader device appeared in the present-device query.

## Existing database evidence

- `usb_protocol_notes`: the application control channel is MI_01 Col03,
  usage page FF00, report ID 04. Command responses are checked by the host.
- `dynamic_capture`: an earlier update transferred the encrypted image
  unchanged; bootloader entry is `04 A5 01`, followed by re-enumeration as
  `352D:1101` and a `getv` exchange.
- `decompiled`, function `10004e40`: START contains image size, hardware
  metadata, a 32-byte file header, and a stub when the relevant branch is
  selected. DATA carries 512-byte file chunks; COMPLETE carries checksum
  and timestamp fields. This describes host behavior, not ROM internals.
- `flash_controller`: the recorded vendor stub accesses controller
  `40013000`, with program/erase operations and 512-byte programming pages.
- Findings 31–32 record prior live probing and the custom-stub proposal.
  Their observations are historical, not new experiments in this session.

## Independently recovered artifact

`extract_vendor_stub.py` reconstructs the observed START frame from outgoing
USBPcap reports and extracts its plaintext stub into `vendor_stub.bin`.

- START frame: 496 bytes, including its 8-byte framing header.
- Stub length field: frame offset 48, value 440.
- Stub bytes: frame offsets 52–491 inclusive.
- SHA256: `fbf8d711262615c1fcfa7abad885e124032be8990da9af01f6e31a20da762ae8`.
- Controller literal `0x40013000`: stub offset 416 (`0x1a0`).
- Historical `getv` reply contains `version:` and
  `a1 05 00 00 a1 03 00 00`. Field meanings require confirmation; this is
  not a query of the currently installed application version.

The extractor is specific to this capture's observed endpoint and framing.
It is an offline analysis helper, not a general USB protocol implementation.

## What remains unresolved

The database's 57 decompiled functions are host-side addresses; it contains
no decompiled `20000000` stub functions. Stub behavior is summarized in
findings and `flash_controller`, but bootloader ROM call sites, argument
registers, scratch RAM ownership, function dispatch offsets, and a mechanism
to return arbitrary bytes through ACKs are not supplied. Host ACK validation
does not establish that the stub controls ACK contents.

Consequently `readonly_stub/stub.c` remains a proposed mailbox interface,
not a compatible vendor-stub replacement. The next useful analysis is to
disassemble the recovered vendor stub and recover each entry's inputs,
outputs, clobbers, and internal calls; then establish which entries the ROM
actually invokes and how results reach USB. Repeating generic application
queries does not resolve this gap.

Some database conclusions exceed their direct evidence. An unchanged
ciphertext transfer plus a flash programmer supports device-side crypto,
but does not alone prove transparent XIP decryption, CPU-readable plaintext,
a particular cipher/KDF, or what a SWD dump returns. Repeated blocks support
an ECB-like structure; diffusion statistics do not prove cryptographic
strength. Entering bootloader without erase does not prove START or a custom
stub transaction is harmless. These remain hypotheses until tested against
the device implementation.

No bootloader-entry, update, flash erase/program, or custom-stub upload was
performed during this analysis. The original database was not modified.
