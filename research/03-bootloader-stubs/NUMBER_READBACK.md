# Number readback through timing

Result: **7**, decoded from the live START acknowledgement delay.

The register-only test stub calculates `0x12 XOR 0x15` and executes that many
units of a 262,144-iteration countdown, then returns zero. It has no loads,
stores, stack accesses, or peripheral accesses. Two separate calibration
stubs encode zero and one. All six inferred entries branch to the same
routine. Eighteen offline entry-call emulations passed across the three builds.

Measured time from completion of the last HID write to the acknowledgement:

| Stub | Time (ms) |
| --- | ---: |
| Calibration zero | 2.0036 |
| Calibration one | 24.0226 |
| Computed number | 155.0121 |

One unit was 22.0190 ms. The decoder calculated
`(155.0121 - 2.0036) / 22.0190 = 6.94893`, rounded to **7**. The residual
was 0.0511 units, below the preset 0.25-unit ambiguity threshold. It decoded
from timing before comparing the result with the known test value.

This demonstrates a low-bandwidth output channel from the custom stub.
The number is a known arithmetic test value computed by uploaded code; it
is not a newly discovered device property or a memory dump. The USB reply
payload still has status 04; the value is conveyed by latency, not a USB data
byte. Calibration and timing can be affected by USB/host scheduling, and this
single successful calibrated trial does not establish a production protocol.

Each session sent only START, followed by the previously observed getv/return
to application transition. No DATA or COMPLETE packet was sent. After each
session, six application HID collections reappeared and no bootloader
interface remained. No flash readback was performed.

Evidence: `../number_readback_live.json`. Builder:
`build_number_probe.py`. Live test: `../read_number_live.py`.
