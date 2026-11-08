# Source-buffer and outer-caller investigation

The handler exit at 0xf60 decoded as `add sp,#0x24; pop {r4,r5,r6,r7,pc}`.
Reading its saved return word at SP+52 during our START entry produced
`0x00000cc3`, giving a return point of `0x00000cc2`. Repeated nibbles, an
independent nibble XOR, and calibration checks passed. This is another caller
location; it is not yet a verified USB transmit function.

Evidence: `../caller_00000f60_8_live.json` and
`../saved_lr_readback_live.json`.

## DATA entry and synthetic source markers

An isolated delay at uploaded offset 0x6c changed each DATA acknowledgement
by about 175 ms for an eight-unit delay. Other inferred entries returned
immediately. This verifies that the programming entry at 0x6c executes during
DATA, independently of the START initialization entry at 0x13a.

The original 0x6c routine treats R1 as its source pointer. A no-store replacement
read the low nibble of the first byte at R1. Two synthetic chunks started with
A5 and 5A (expected low nibbles 5 and 10). Measured source nibbles were 13 and
3, respectively. Timing estimates were 12.9663 and 3.0194 units, within the
0.25-unit decoding bound. ACK payloads remained status 04.

This establishes a changing value at the inferred source pointer, but it does
not yet establish the source's layout or transformation. Possible explanations
include ROM-side decryption/processing or a buffer interpretation difference.
Do not claim plaintext recovery from this test alone. Earlier conclusions
that a simple programmer necessarily means ciphertext is written to flash
were too strong: the ROM could transform data before calling the programmer.

The uploaded replacement has no stores, stack accesses, or peripheral accesses.
Only synthetic DATA chunks were used in this marker experiment, and no
COMPLETE was sent. The application re-enumerated after every session. Raw
evidence: `../chunk_buffer_live.json`. Next test compares the source buffer
against the captured vendor ciphertext page and repeats the first observed
byte, using the same no-store programming replacement.

## Captured-page source word — later result

The first DATA page reconstructed from the original USBPcap starts with
ciphertext `f0 6d 17 be`. Sending that page to our no-store stub, twice per
session, yielded source bytes `50 1c 00 20` at R1 in both sequences. All four
bytes were read by nibble timing probes across sessions. The first byte was
independently repeated and matched. Calibration and ambiguity checks passed.
Evidence: `../source_word_live.json` and `../captured_first_page.bin`.

The source word is `0x20001c50`, consistent with an ARM initial stack pointer.
This directly establishes that the programmer's CPU-visible source is not
the raw ciphertext page. It strongly supports bootloader-side decryption
before programming. It does not identify the cipher, recover a key, or
establish a full plaintext dump. More vector-table bytes would provide
further corroboration.

The earlier claim that unchanged USB ciphertext plus a verbatim programmer
proves transparent XIP encryption is invalid: the ROM can transform the
source first. What SWD returns cannot be inferred from that earlier claim.
The uploaded replacement has no stores, no COMPLETE was sent, and application
USB enumeration returned after each session. No flash readback was performed.
