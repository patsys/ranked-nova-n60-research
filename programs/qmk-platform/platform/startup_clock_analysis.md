# Startup, clock and fixed-vector evidence

Original code was examined offline. No keyboard access or flash operations.

The boot vector entries for exceptions 2,3,11,14,15 and IRQ0..21 point to
0x1df. Code at0x1de loads0x3ad;0x3ac reads IPSR, multiplies it by4,
adds0x2000, loads that application's vector and branches to it. Thus the
preserved original bootloader provides **fixed application vector forwarding**
at0x2000; this mechanism does not require assuming a VTOR register exists.
`validate_vector_forwarding.py` executes the original path for all27 relevant
entries with synthetic IPSR values, stopping at each recovered app handler.
This checks instruction behavior, not physical exception entry/return timing.

Application reset0x2210 branches to0x20d8, sets SP20001c50, then executes the
scatter initializer0x2284. The three16-byte descriptors at0x10614..0x10644
decode1364 bytes into20000000..20000554 and zero20000554..20001c50 plus
20003000..20003718. Original main starts0xcd80. Initialized RAM regions do
not establish the physical memory limit or a safe replacement stack budget.

The decoded software clock values at20000428 and2000042c are both48000000.
Function4194 returns the latter. Delay0xdde8 chooses a helper indexed by
floor(clock/4000000), capped at12, from decoded RAM table20000470; the
48MHz entry is0x21c9. The long delay0xdd80 first calls the selected helper
with `count<<7`, then calls it `count` times with argument999. This corrects
the earlier claim of128 repetitions; native tracing for counts0/1/2/10
establishes the actual sequence. Units/frequency remain unmeasured.

`recovered_clock.c` transcribes0xd5f0 startup register ordering and0xd57c
domain selection, retaining repeated volatile writes and unproven field names.
Bit0x01000000 is the exact ARM32 result of the source address shifted left18.
Twenty original-code cases and twenty compiled-C comparisons use synthetic
MMIO values to check ordered writes. This does not simulate oscillator/PLL
stability or prove that the software clock estimate is accurate.

The0xd524 gate writer writes a mask to4001402c(enable) or40014030(disable)
then calls calibrated delay0xdde8(10). The C adaptation requires a real delay
callback and reports failure for a missing callback; no no-op timing supplied.
USB startup0xf0dc selects domain2, enables mask80000000, polls40014120 bit0,
then calls long delay0xdd80(10). A complete platform still needs verified
frequency/source definitions, bounded status waits and interrupt/tick integration.

No linker script guessing full SRAM, ChibiOS board name, or flashable startup
image is supplied. The compiled validation ELF has no vectors/startup and is
solely an offline test artifact. Remaining integration requires a real platform.
