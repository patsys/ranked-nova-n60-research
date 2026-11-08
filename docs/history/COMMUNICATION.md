# Two-way communication investigation — 2026-11-02

> Historical checkpoint: the initial failures below were followed by verified
> custom USB readback, firmware extraction and working QMK/VIA. See
> [the end-to-end guide](REVERSE_ENGINEERING_GUIDE.md) for the full sequence.

**Later execution test:** An argument-independent, register-only delay stub
produced repeatable added latency of about 22 ms at START and 44 ms at DATA
in two comparisons against an immediate-return stub. This supplies strong
evidence of custom execution that the earlier tests below did not supply.
See `readonly_stub/EXECUTION_TEST.md` and `execution_probe_live.json`.
Custom data readback remains unresolved.

## Established

The native bootloader has bidirectional HID communication at VID 352D,
PID 1101. `boot_console.py --enter-bootloader --count 3` performed three
successful `getv` request/reply exchanges. Replies contained `version:` and
raw words `a1 05 00 00 / a1 04 00 00`. Interpretation of each word beyond
the recorded vendor observations remains provisional.

The operational channel also replies to START and DATA, echoing command and
sequence bytes. Our own 440-byte payloads were placed in START with the
recorded length and XOR checksum format. Replies used the normal `04` status.
This is transport-level communication, not proof of custom code execution.

## Custom handler tests

`readonly_stub/echo.bin` replaces inferred vendor entries with no-store
Thumb routines. Initialization/erase entries return zero without doing
anything. Programming entries check that the inferred source pointer has
upper 16 bits `0x2000`, read one byte, and return `2 + (byte & 1)`. A source
outside that window returns 2 without reading it. No flash or peripheral
access, stack access, or memory writes occur. The R0/R1 argument convention
is inferred from the original stub, not verified against ROM call sites.

After START, two synthetic 512-byte DATA inputs were sent, containing zeros
except for byte zero (challenge 0 or 1). No encrypted firmware body was sent.
Both replies had status 04. The raw exchanges are in `echo_probe_live.json`.
The builder's 36 offline emulation checks passed.

`readonly_stub/timing.bin` adds a finite 1,048,576-iteration register loop
when the source byte is odd. Its 36 emulation checks also passed. Live
synthetic challenge replies took 19.558 ms (even) and 19.909 ms (odd), both
with status 04. See `timing_probe_live.json`. This provides no convincing
evidence that the conditional loop ran on hardware. Possible explanations
include deferred execution, a different invocation ABI, transformed input,
or ROM handling that does not expose the handler's return value. None is
established by these results.

No COMPLETE/commit packet was sent in either test. Uploaded code contains
no erase/program instructions or memory stores. This does not independently
prove what the surrounding ROM did; no flash readback was available.

## Final state and remaining gap

A `getv` issued after the transfer phase produced a HID read error during
disconnect, as observed in earlier START-only sessions. The application then
reappeared as six HID collections at 3532:A0A3, with no bootloader interface.
See `communication_final_state.json`. This confirms application USB
enumeration, not byte-for-byte flash integrity or a complete keyboard test.

A verified custom memory-read or echo service has **not** been established.
Before describing such a service as working, establish where/when ROM invokes
the uploaded code and how it constructs responses. The observed ACK and its
sequence echo must not be mistaken for a custom stub reply.

The live test scripts are narrow research experiments, not general flashers.
`probe_echo.py` deliberately has no COMPLETE operation and stops on malformed
or non-success replies. Running it still enters the firmware transfer state;
it should not be represented as an ordinary read-only query client.
