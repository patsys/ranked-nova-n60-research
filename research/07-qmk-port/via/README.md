# VIA research definition

`nova_research.json` uses the existing research USB VID/PID `3532:A0A3` and
contains all 62 recovered keys. Rows are acquisition banks 0–5 and columns are
channels 0–10. This is a **diagnostic layout**, not a claim about the physical
German/ISO arrangement. Human-readable legends describe the original fallback
HID usages; the operating system determines the language-specific characters.

The raw HID interface must advertise usage page `0xFF60`, usage `0x61`, with
32-byte packets. These standard interface selectors are described by the
firmware HID descriptors; they are not invented keyboard-definition properties.
The definition follows the [official VIA specification](https://www.caniusevia.com/docs/specification/).

Generate and validate with `generate_definition.py`. The research firmware uses
RAM-backed transient EEPROM: VIA remaps are lost on reset. Loading the JSON into
VIA alone does not install firmware or make the original vendor firmware speak
VIA. No definition has been submitted or published to VIA's keyboard repository.

`test_via_protocol.py` executes the **actual linked upstream VIA handler** in
the VIA research ELF, including its dynamic keymap and transient EEPROM code.
It checks protocol version 13, three layers, individual and buffered remaps,
reset, invalid coordinates, end-of-keymap accesses, packet guards, and responses
through the real runtime host raw callback. Remapping a physical acquisition
position to A or B changes the actual QMK keyboard report; reset restores 1.
The final run passed 147 cases with 138 queued responses and no CPU flash writes.
Observed process-stack use was 280 bytes within the 1,024-byte allocation.

The emulator provides sensor samples, a synthetic millisecond clock, USB
clock-ready status, and intercepted original delays. It does not establish
physical USB enumeration, endpoint transfers, sampling timing, or boot acceptance.
See `via_protocol_result.json` for the exact ELF hash, cases, and limitations.
