/* Thumb Cortex-M0; built by build_diagnostic.py.
 * PROBE returns ROST in r0. INFO requires r0 = trusted 48-byte RAM buffer.
 * Neither entry establishes compatibility with the bootloader ROM.
 */
/* @PROBE */
movs r0, #0x52
lsls r0, r0, #8
adds r0, #0x4f
lsls r0, r0, #8
adds r0, #0x53
lsls r0, r0, #8
adds r0, #0x54
bx lr

/* @DENY */
movs r0, #2
bx lr

/* @INFO */
/* Save no stack or global state. r1-r3 are AAPCS caller-saved. */
mov r1, lr
str r1, [r0, #40]
movs r1, #1
str r1, [r0, #4]
movs r1, #48
str r1, [r0, #8]
mrs r1, ipsr
str r1, [r0, #16]
mrs r1, control
str r1, [r0, #20]
mrs r1, primask
str r1, [r0, #24]
mrs r1, msp
str r1, [r0, #28]
mrs r1, psp
str r1, [r0, #32]
mov r1, pc
str r1, [r0, #36]
movs r1, #0
str r1, [r0, #44]
/* Construct architectural CPUID register address without a literal pool. */
movs r2, #0xe0
lsls r2, r2, #24
movs r3, #0xed
lsls r3, r3, #8
adds r2, r2, r3
ldr r1, [r2]
str r1, [r0, #12]
/* Publish marker last. */
movs r1, #0x52
lsls r1, r1, #8
adds r1, #0x4f
lsls r1, r1, #8
adds r1, #0x53
lsls r1, r1, #8
adds r1, #0x54
str r1, [r0]
movs r0, #0
bx lr
