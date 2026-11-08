# Caller trace and feasibility check

Live nibble timing probes recovered these CPU-readable bytes:

```text
0000101c: ff f7 06 f9   bl  0x0000022c
00001020: 33 e0         b   0x0000108a
```

The call ends at exactly the return address measured independently as
LR = 0x00001021 (Thumb bit included). This corroborates the LR readback and
shows that the timing channel can recover code bytes, not only register
constants. Two reads of the first byte of each source block matched, every
nibble passed the timing ambiguity bound, and before/after calibration passed.
Only START was sent; no DATA or COMPLETE operation was used. Uploaded stubs
perform one bounded byte read from the selected code address and have no
data-memory stores, stack operations, or peripheral accesses.

Evidence: `../caller_readback_live.json` (101e–1021),
`../caller_0000101c_2_live.json` (101c–101d), and `../caller_101c_6.bin`.
The next code target being examined is 0x0000022c, obtained from the decoded
BL instruction. The USB transmit function remains unidentified.

## Trampoline and common exit

Further calibrated reads recovered:

```text
0000022c: 03 b4        push {r0,r1}
0000022e: 01 48        ldr  r0,[pc,#4]  ; literal at 0x234
00000230: 01 90        str  r0,[sp,#4]
00000232: 01 bd        pop  {r0,pc}
00000234: 3b 01 00 20  .word 0x2000013b

0000108a: 00 20        movs r0,#0
0000108c: 68 e7        b    0x00000f60
```

This preserves the incoming R0 and transfers control to our uploaded code at
0x2000013a in Thumb mode. It identifies the START entry as the original timing
configuration function offset 0x13a, rather than offset zero. No USB response
buffer or transmit API is established by these instructions. A provisional
interpretation of incomplete exit bytes as an R5 packet read was wrong; the
completed bytes decode to the branch shown above. Do not infer a buffer from
that earlier commentary.

The next exit-path target is 0x00000f60. Raw evidence for the trampoline and
literal: `../caller_0000022c_8_live.json` and `../trace_followup_live.json`.
Before/after calibration passed in both traces; the first trampoline byte was
read twice and matched. The literal/common-exit batch has no full duplicate
read, so later structural checks provide useful additional corroboration.

Repeated START messages in a single HID session are not established as a
usable read mechanism: a trial disconnected on the second START. Current
reads use a fresh bootloader session for each nibble. This is slow but bounded
and resumable; it does not assume a new protocol command exists.
