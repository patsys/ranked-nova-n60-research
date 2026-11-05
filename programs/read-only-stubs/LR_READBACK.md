# Incoming LR readback — 2026-11-02

**Decoded incoming LR: `0x00001021`. Return address with Thumb bit cleared:
`0x00001020`.** This is the return point presented to our stub during START.
It is not yet an identified USB transmit function or a disassembled call site.

Each own 440-byte payload branches from all six inferred vendor entry offsets
to a common routine. The routine reads LR into R0, selects one nibble, and
encodes it in a finite CPU countdown before returning zero. The entry branches
do not change LR. No stack, data-memory load/store, peripheral access, DATA,
or COMPLETE operation is used. The offline builder verifies nibble selection,
LR preservation, return behavior, and absence of memory writes across 66
emulated calls. Code is limited to register arithmetic, branches, and return.

Eight live START sessions read the nibbles from least to most significant:
`1, 2, 0, 1, 0, 0, 0, 0`. The low nibble and nibble four were independently
repeated and matched. Another payload folded all eight LR nibbles with XOR
and returned 2 through timing, matching the reconstructed value's checksum.
This checksum checks consistency; it is not a complete independent repetition
of all 32 bits and cannot exclude all possible timing errors or changes.

Calibration used separate zero/eight-unit payloads before and after the reads:

| Calibration | Zero post-write ACK (ms) | Eight-unit ACK (ms) | Unit (ms) |
| --- | ---: | ---: | ---: |
| Initial | 2.0281 | 177.1607 | 21.891575 |
| Final | 2.0974 | 177.1701 | 21.8840875 |

The decoder required each measured digit to lie within 0.25 unit of an integer,
a calibration slope change below 5%, and baseline change below 3 ms. All
checks passed. Use the raw JSON for full precision and individual exchanges.

After every session, the observed getv/disconnect transition returned the
device to six application HID collections at 3532:A0A3, with no bootloader
interface. No flash readback or complete keyboard functional test was done.

Sources: `build_lr_probe.py`, `lr_probes.json`, each `probe_*.disasm.txt`, and
`../read_lr_live.py`. Raw evidence: `../lr_readback_live.json`.

The next useful code location is around `0x00001020`. Reading and disassembling
that code could identify the caller and dispatch mechanism. This result alone
does not establish the underlying memory type, chip model, other argument
registers, or USB response API.
