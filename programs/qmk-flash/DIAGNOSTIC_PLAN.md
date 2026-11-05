# Bounded USB diagnostic experiment

The user authorized autonomous testing and another flash when justified by
tests, with physical recovery available later if needed. Two new definite
USB port differences have been corrected: missing raw-event4 endpoint setup
and missing fresh status reads immediately before interrupt acknowledgements.
These corrections match original instruction traces. Their contribution to
the physical enumeration failure remains unproved.

The next target is a separate diagnostic VIA build. It records startup stages,
existing USB status/event reads, IRQ entry/exit counts, configuration changes
and fault context at `0x20003000..0x200030ff`. The separate fault stack is only
`0x20003100..0x200031af`, within the area exercised by the prior RAM probe.
It contains no flash-programming or erase driver.

A diagnostic SysTick deadline requests the original bootloader if USB is
unconfigured after5000 ticks. Its priority0 can preempt the USB IRQ at priority1.
Detected initializer failures and captured NMI/HardFault also request boot.
This depends on working core execution, exception delivery and reset retention;
it is not independent hardware recovery or a guarantee against every failure.
Repeated USB reset/configuration-zero callbacks do not extend the deadline.

Before execution, the exact diagnostic ELF must pass startup/vector, key/VIA,
emergency-entry, timeout/priority/fault-stack and native-boot trace-retention
tests. Preparation and the writer bind exact ELF/body hashes. The native
117-page transfer/readback/release model and host error tests must pass again
for that body. Bootloader, settings and hidden metadata remain excluded from
the application-only writer and are compared after programming.

If QMK enumerates, perform read-only VIA queries. If the original bootloader
returns, collect the trace through five guarded RAM-reader STARTs during the
verified stock rollback session. If neither interface returns, stop further
device operations and await the user's physical Esc-held reconnect. Preserve
every outcome in SQLite. Do not describe a successful readback as a working
QMK runtime.

A full RAM-only USB takeover was considered but not executed: the current
verified loader is too small, and direct native USB reinitialization contains
unbounded waits. Evidence is in `ram_usb/feasibility.json`.
