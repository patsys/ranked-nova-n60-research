# Copyright 2026 patsys
# SPDX-License-Identifier: GPL-3.0-or-later
"""START stubs for bootloader v1.0.7 (GETV a1070000a1040000), from timing-measured identities.

Measured on a v1.0.7 unit with the one-byte START timing channel (v107_timing_live.json):
  incoming LR 0x1049 (bl 0x22c at 0x1044)        v1.0.5: 0x1021
  START handler frame add sp,#0x2c (0xf88)        v1.0.5: add sp,#0x24 (0xf60)
  saved return [sp,#60] = 0xce7 (after blx r0)    v1.0.5: [sp,#52] = 0xcc3
  reply builder 0xbe0: ctx+8 data, ctx+4 length, callback [ctx+0x214]  (unchanged)
  resume 0xe94: memset(ctx, 0, 0x208), main loop  v1.0.5: 0xe70
Everything else (entries, 440-byte layout, ACK) is the v1.0.5 framing.
"""
import diag_stub  # noqa: F401  (puts ry72xx_flasher on sys.path)
from ry72xx_flasher.image import require
from ry72xx_flasher.stubs import blank, mov32, place

LR = 0x1049
SAVED_OFFSET, SAVED = 60, 0xCE7
RESUME = 0xE94

GUARD = f"""
    mov r0,lr; movs r2,#0x10; lsls r2,#8; adds r2,#{LR & 0xFF};
    cmp r0,r2; bne done; ldr r0,[sp,#{SAVED_OFFSET}];
    movs r2,#0x0c; lsls r2,#8; adds r2,#{SAVED & 0xFF}; cmp r0,r2; bne done;
    movs r2,#0x20; lsls r2,#24; adds r2,#255; adds r2,#66; str r2,[sp,#{SAVED_OFFSET}];
done: movs r0,#0; bx lr
"""
SEND = f"""
    strh r1,[r4,#4]; mov r0,r4; adds r0,#255; adds r0,#255; adds r0,#2;
    ldr r0,[r0,#20]; blx r0;
    movs r3,#{RESUME >> 8}; lsls r3,#8; adds r3,#{(RESUME & 0xFF) | 1}; bx r3
"""


# Word-read windows without read side effects (SysTick CSR is excluded: reading clears COUNTFLAG).
WORD_WINDOWS = (
    (0x10000000, 0x10000800),  # info flash
    (0x20000000, 0x20001C50),  # RAM up to the application's initial SP
    (0xE000E014, 0xE000E020),  # SysTick RVR, CVR, CALIB
    (0xE000E100, 0xE000E104),  # NVIC ISER
    (0xE000E200, 0xE000E204),  # NVIC ISPR
    (0xE000E400, 0xE000E420),  # NVIC IPR0..7
    (0xE000ED00, 0xE000ED40),  # SCB
    (0xE00FF000, 0xE0100000),  # ROM table
    (0x40013000, 0x40013100),  # flash controller
    (0x40014000, 0x40014200),  # system control / retained
    (0x40019000, 0x40019040),  # oscillator control (written by the clock setup at 0xa60)
    # Identified by code analysis; status bits there are cleared only by explicit writes:
    (0x4000D000, 0x4000D020),  # AES/DMA engine (0x29c, 0x330)
    (0x40012000, 0x40012060),  # timer with compare (app 0x2f20 ISR, 0xdc54)
    (0x40015000, 0x40015040),  # timer/power block with ready flag +0x38 (0x5f0)
    (0x40016000, 0x40016020),  # USB core control / interrupt status (0x1250, 0x12c0)
    (0x40018000, 0x40018200),  # GPIO inputs +0x30 and pad configuration (0x484, 0x4ac)
    (0x40017C00, 0x40017E00),  # USB EP0 buffer (one byte per word, 0x98a)
    (0x40017E00, 0x40018000),  # USB endpoint table, EP control, setup registers (0x530, 0x638)
)


def read_stub(address, length):
    """Byte loads from CPU flash, or word loads from the side-effect-free WORD_WINDOWS."""
    info = any(lo <= address and address + length <= hi for lo, hi in WORD_WINDOWS)
    require(info or 0 <= address and address + length <= 0x20000, "Read outside CPU flash and the word windows")
    require(1 <= length <= 56 and (not info or address % 4 == length % 4 == 0), "Read reply must fit its native buffer")
    image = blank()
    place(image, 0x80, GUARD, 0xDA)
    step, load, store, count = (4, "ldr", "str", length // 4) if info else (1, "ldrb", "strb", length)
    tail = mov32("r0", address) + f""";
        mov r2,r4; adds r2,#8; movs r1,#{count};
    loop: {load} r3,[r0]; {store} r3,[r2]; adds r0,#{step}; adds r2,#{step};
        subs r1,#1; bne loop; movs r1,#{length};
    """ + SEND
    place(image, 0x140, tail, 440)
    return bytes(image)


def diag_stub(page, word=0, values=(0, 0), flags=0):
    import diag_stub as d
    return d.diag_stub(page, word, values, flags, guard=GUARD, send=SEND)


def core_stub(mask):
    """v1.0.5 core_stub with the v1.0.7 guard/send: PRIMASK before/after, CPUID, NVIC ISER, SysTick CSR."""
    image = blank()
    place(image, 0x80, GUARD, 0xDA)
    tail = "mov r2,r4; adds r2,#8; .byte 0xef,0xf3,0x10,0x80; str r0,[r2]; "
    if mask:
        tail += "cpsid i; "
    tail += ".byte 0xef,0xf3,0x10,0x80; str r0,[r2,#4]; "
    for offset, address in [(8, 0xE000ED00), (12, 0xE000E100), (16, 0xE000E010)]:
        tail += mov32("r0", address) + f"; ldr r0,[r0]; str r0,[r2,#{offset}]; "
    tail += "movs r1,#20; " + SEND
    place(image, 0x140, tail, 440)
    return bytes(image)
