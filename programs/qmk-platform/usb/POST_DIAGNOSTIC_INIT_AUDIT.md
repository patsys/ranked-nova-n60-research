# Audit after the physical 5-second USB diagnostic

Root supplied `qmk_flash/live_rollback_20261103T073830_059181Z/diagnostic_trace.json`: main loop reached, 5000 SysTicks, one USB IRQ entry and exit, outer status 2, no primary event read or configuration transition, no recorded fault. This rules out an interrupt storm in that observation; it does not identify which auxiliary flags were present because 0x40017f58 was not recorded.

A definite omitted auxiliary controller action exists. Native 0xf310 reads the low byte of 0x40017f58. If bit7 is set it writes 0x80 to that same register at 0xf320. Current C only implements the branch where bit7 is clear and bit3 is set; bit7 therefore produces no controller write at all. `audit_aux_irq_flags.py` executes actual native instructions without bypasses, with bus-flags word 0x20000528 zero, and proves this for flags 0x80, 0x81, 0x88; flags zero is a negative control. Evidence is `aux_irq_missing_bit7.json`. Register acknowledgement semantics and the physical meaning of bit7 are undocumented; do not call it an attach fix or infer causality.

When native bus-flags bit2 is set, the bit7 path additionally runs a timed sequence through 0xf328..0xf35a. Other auxiliary branches update application policy and optionally invoke callbacks. A faithful auxiliary implementation should recover those cases before transplanting guessed partial behavior. No source was changed during this audit.

The broader native startup at 0xcd80 performs d5f0/ea20 clock setup, peripheral/application setup, 0xf02c IRQ4 pending clear, 0xf004 dispatch to 0x46fc, then 0xf038 IRQ4 enable. The latter two wrappers write 0xe000e280=16 and 0xe000e100=16, already represented in runtime. All controller stores in 0x46fc, including 0xeea8, 0xeed4 and 0xee94 reset/pulse/clear helpers, are covered by existing exact instruction trace tests. No separate post-0x46fc attach-enable write was found in those wrappers.

Earlier native 0x4a9c(-1) enables gate mask 0x80000, calls long delay10, writes 0x40015000=1 and polls 0x40015038. Runtime omits this peripheral initialization, but no evidence currently establishes that peripheral as USB-related. GPIO41/45 initialization in 0x4470 is represented by the acquisition implementation. These differences are leads for bounded register comparisons, not grounds for copying unrelated hardware writes.

Safe next diagnostic improvement: record the already-read auxiliary flag value through the bus read hook, without an additional MMIO read. A repeat physical test should wait for complete auxiliary instruction-equivalence coverage and retain root's stock rollback procedure. This audit performed no hardware access, source correction, firmware rebuild or flash.

## Subsequent bounded correction

Parent authorized the unconditional bit7 acknowledgement after the native proof. The engine now writes f58=0x80 for bit7, otherwise preserving the bit3 reset branch. Actual native/C cases with auxiliary flags0/80/81/88 and native busflags0 are included in `device_validation.json`. No timed-resume policy was invented: native busflags bit2 remains unsupported and explicitly documented. Runtime diagnostics now log the already-read f58 value using `nova_usb_diagnostic_aux`, with no extra controller access.
