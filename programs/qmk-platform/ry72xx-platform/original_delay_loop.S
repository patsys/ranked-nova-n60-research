// Copyright 2026 patsys
// SPDX-License-Identifier: GPL-3.0-or-later

.syntax unified
.cpu cortex-m0
.thumb
.section .text.nova_delay48_loop,"ax",%progbits
.global nova_delay48_loop
.type nova_delay48_loop, %function
.thumb_func
/* Exact instruction sequence of original 0x21c8..0x21fe, selected by the
 * firmware's nominal48MHz software value. No physical timing claim. */
nova_delay48_loop:
1: .inst.n 0x1e40 /* subs r0,r0,#1: preserve original encoding */
.rept 25
    .inst.n 0xbf00 /* Original architectural NOP, not assembler's MOV r8,r8. */
.endr
    bne 1b
    bx lr
.size nova_delay48_loop, .-nova_delay48_loop
