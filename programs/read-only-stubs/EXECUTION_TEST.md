# Argument-independent execution test — positive result

Two own 440-byte Thumb stubs were compared twice on the keyboard. Both have
branches at offsets 0, 0x24, 0x6c, 0xda, 0xfc, and 0x13a to one common routine.
The control routine returns zero immediately. The delayed routine counts down
from 262,144 in R0, then returns zero. Neither reads memory, writes memory,
uses the stack, or touches a peripheral. All code decodes to B/BX, MOVS, LSLS,
SUBS, and BNE. Twelve offline entry calls across both builds passed emulation.

The live sender used the captured START framing, replaced the stub and its
XOR checksum, and sent one synthetic 512-byte zero DATA packet. It did not
send real firmware or COMPLETE. Each session was followed by the previously
observed getv/disconnect transition and application re-enumeration.

| Run | Stub | START round trip (ms) | DATA round trip (ms) |
| --- | --- | ---: | ---: |
| 1 | Immediate return | 16.931 | 19.975 |
| 1 | Register delay | 38.951 | 63.933 |
| 2 | Immediate return | 16.948 | 19.968 |
| 2 | Register delay | 39.080 | 64.157 |

Changing only the uploaded code produced repeatable additional latency of
about 22 ms at START and 44 ms at DATA. This is strong evidence that the
uploaded custom stub executes during these transactions, before COMPLETE.
The result is consistent with one delay invocation at START and two at DATA;
it does not identify the exact entry offsets called or establish arguments.
All ACKs still had status 04, so that byte does not expose these return values.

The previous challenge-dependent timing test was inconclusive because it
depended on an unverified source pointer and invocation convention. This
test removes both input dependencies. It proves execution much more directly
than acknowledging an uploaded buffer alone. It does not yet prove arbitrary
readback, an echo service, or ROM-to-stub calling conventions.

Raw evidence: `../execution_probe_live.json`. Sources and reproducibility:
`build_execution_probe.py`, `execution_0.disasm.txt`,
`execution_18.disasm.txt`, and `../test_execution_live.py`.
The latter is a live research experiment, not an ordinary query tool.

At the end of all four successful sessions, six application HID collections
at 3532:A0A3 were present and no bootloader interface remained. One initial
attempt to re-enter bootloader too soon after application enumeration failed;
the delayed test was retried after the app was ready. The repeated comparison
waited five seconds before each boot entry. No flash readback was performed.
