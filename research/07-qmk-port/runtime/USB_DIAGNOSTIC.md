# Isolated USB diagnostic firmware

Latest status: diagnostic V1's automatic timeout/boot return and trace retrieval
were observed physically. V2 now enumerates as QMK/VIA, passes live protocol
and reversible-remap tests, and the user confirms operation. See
[the full process](../../../docs/history/REVERSE_ENGINEERING_GUIDE.md). V2 reserves trace words45–47
for shared-startup status, auxiliary read count and last auxiliary flags;
event counters cover0–28. Current hash-bound validation has22 cases.

Enabled only by `NOVA_USB_DIAGNOSTIC` and built into separate diagnostic output directories. The normal build keeps its existing behavior through empty inline instrumentation and the original boot-request function. This is not a claim that an arbitrary early hardware failure is recoverable.

The diagnostic records a256-byte trace at `0x20003000..0x200030ff`. The exact64-word layout and stage/reason constants are in `usb_diagnostic.h`. Startup initializes the trace before clock operations, records clock/keyboard/matrix/emergency/USB stages, and records already-read USB status/event values and IRQ entry/exit counts. Instrumentation adds no USB status-register reads. USB configuration callbacks record transitions without renewing the deadline.

Immediately before globally enabling interrupts, main arms an absolute5000-SysTick deadline. If USB is unconfigured when that deadline is reached, or configuration is lost after the deadline, the diagnostic records the previous stage and requests the original bootloader through `0x4001400c=0x5ac396c5` followed by ARM SYSRESETREQ. Repeated bus reset/configuration0 callbacks do not restart the countdown. The configured SysTick interval assumes the recovered nominal48MHz clock;5000 ticks are not an independently measured physical five seconds.

Diagnostic `timer_init` assigns SysTick priority0, preserving the other SHPR3 bytes. USB IRQ4 retains priority1. Thus the architectural priority relationship permits SysTick to preempt a USB IRQ storm, subject to the global interrupt mask and functioning clock/core. USB IRQ instrumentation owns its counters; SysTick owns its tick count and boot-request fields, avoiding cross-context read-modify-write of those counters.

Strong diagnostic NMI and HardFault handlers recover the original exception-frame pointer from EXC_RETURN's PSP/MSP selector, then switch MSP to a separate176-byte emergency window `0x20003100..0x200031af`. The top is `0x200031b0`, within the physical RAM addresses exercised by the earlier RAM acquisition payload. The C handler captures a bounded frame, records exception/PC context and requests boot. Invalid frame pointers and nested frames overlapping that emergency stack are recorded as unavailable (`0xffffffff`) rather than dereferenced or represented as reliable frames. The handlers never attempt to return to the faulting application.

## Actual compiled checks

`validate_usb_diagnostic.py` runs both complete linked diagnostic ELFs and writes the hash-bound gate `usb_diagnostic_validation.json`.

The initial20 cases (extended to22 for V2) cover:

- Full5000-tick expiry for each image despite thousands of configuration0/IRQ events.
- Configured-at-deadline operation and later loss of configuration.
- SysTick priority0, USB priority1, neighboring priority-byte preservation.
- Timeout with256 bytes of pre-existing USB/exception-stack budget: modeled main-stack use296 bytes of the512-byte allocation.
- Actual compiled HardFault/NMI wrapper paths with PSP, MSP, invalid and nested frame fixtures. Maximum emergency-stack use88 bytes, minimum SP `0x20003158`, above the `0x20003100` bound.
- Actual original boot reset/scatter/main/USB initialization leaves all256 trace bytes unchanged and returns to native protocol code `0xbdc`. Hardware reset registers are modeled and host configuration completion is explicitly injected; this is not physical USB enumeration proof.

The bootloader's observed RAM initialization and subsequent writes in that test
do not overwrite the trace. Physical V1 trace retrieval subsequently demonstrated
retention through its automatic reset; one `armed` field differed from the expected
stored value and remains an observation to investigate, not a strict retention
invariant. DSB before the actual reset request orders the application's trace
stores before reset.

All tests use modeled exception entries/ticks and MMIO. They do not simulate physical NVIC arbitration, prove real oscillator timing, or guarantee recovery from failed hardware exception stacking, unreadable vectors/code, a stopped core clock, or failure before the guard can execute. No flash or device operations were performed by this validation task.
