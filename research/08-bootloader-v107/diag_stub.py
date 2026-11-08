# Copyright 2026 patsys
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded flash-controller diagnostic START stub for the RY7203 (research only).

One START upload performs one erase, one program, or two back-to-back program
operations on a single scratch page and replies with what the controller did.
Nothing outside the scratch page is addressed: page and word numbers are
checked here and compiled in as constants, and the emulator self-test asserts
every controller and flash access.

Layout inside the 440-byte image (entries keep the blank() safe returns):
  0x028 op    write DATA, ADDRESS, COMMAND; optional ADDRESS rewrite / delay
  0x0B0 go    start, sample STATUS, count busy polls, store 3 words
  0x004 goi   IMMEDIATE variant of go (status_after_start reported as 0xffffffff)
  0x100 table constants (see TABLE)
  0x140 main  gate open, op(s), gate close, readback, reply

Reply (40 bytes, little-endian words):
  0..2  op0: STATUS right after start, busy poll count, STATUS at end
  3..5  op1: same (zero when a single operation ran)
  6     flash word 0 readback   7  flash word 1 readback
  8     ADDRESS register readback   9  gate register readback
"""
import struct
import sys
from pathlib import Path

_here = Path(__file__).resolve().parent
# ry72xx_flasher: a source checkout next to this folder, else the installed package.
for _src in (_here.parent / "flasher/src", _here.parent / "contributions/ry72xx-flasher/src"):
    if _src.is_dir():
        sys.path.insert(0, str(_src))
        break

from ry72xx_flasher.image import require  # noqa: E402
from ry72xx_flasher.stubs import GUARD, SEND, assemble, blank, place  # noqa: E402

CTRL = 0x40013000
GATE = CTRL + 0xD0
SCRATCH_FIRST, SCRATCH_LAST = 0x85, 0xCF   # FF in stock and VIA images, allowed by metadata 0x10000650
TABLE = 0x100
REPLY_WORDS = 10

REWRITE_ADDRESS = 1 << 0   # stock 0x3f94: re-write ADDRESS (uxth) right before the start bit
DELAY = 1 << 1             # ~130 cycles between COMMAND and start
ERASE = 1 << 2             # COMMAND 2 on the page instead of programming
TWO_OPS = 1 << 3           # program words w and w+1 back to back under one gate opening
IMMEDIATE = 1 << 4         # authored-loader flash_go: start, one instruction, then poll (no sample read)
POLL_BOTH = 1 << 5         # with IMMEDIATE: done only when STATUS bits 0 and 1 are both clear

OP = """
    ldr r2,[r5,#0]
    str r0,[r2,#8]
    str r1,[r2,#4]
    ldr r3,[r5,#28]
    movs r0,#1
    lsrs r1,r3,#3
    bcc cmd
    movs r0,#2
cmd:
    str r0,[r2,#0]
    lsrs r1,r3,#1
    bcc nore
    ldr r0,[r2,#4]
    uxth r0,r0
    str r0,[r2,#4]
nore:
    lsrs r1,r3,#2
    bcc nodelay
    movs r0,#32
spin:
    subs r0,#1
    bne spin
nodelay:
    lsrs r1,r3,#5
    bcs #0x20000004
    b #0x200000b0
"""

GO = """
    ldr r0,[r2,#16]
    movs r1,#1
    orrs r0,r1
    str r0,[r2,#16]
    ldr r0,[r2,#16]
    str r0,[r6,#0]
    movs r3,#0
    lsls r1,r1,#20
poll:
    ldr r0,[r2,#16]
    lsls r0,r0,#30
    bpl done
    adds r3,#1
    cmp r3,r1
    bls poll
done:
    str r3,[r6,#4]
    ldr r0,[r2,#16]
    str r0,[r6,#8]
    adds r6,#12
    bx lr
"""

GOI = """
    movs r0,#0
    mvns r0,r0
    str r0,[r6,#0]
    ldr r0,[r2,#16]
    movs r1,#1
    orrs r0,r1
    ldr r1,[r5,#32]
    str r0,[r2,#16]
    movs r3,#0
poll:
    ldr r0,[r2,#16]
    tst r0,r1
    beq done
    adds r3,#1
    lsrs r0,r3,#20
    beq poll
done:
    b #{go_done}
"""

MAIN = """
    movs r5,#0x20
    lsls r5,r5,#24
    adds r5,#255
    adds r5,#1
    mov r6,r4
    adds r6,#8
    ldr r0,[r5,#4]
    ldr r1,[r5,#8]
    str r1,[r0]
    ldr r0,[r5,#20]
    ldr r1,[r5,#12]
    bl #0x20000028
    ldr r3,[r5,#28]
    lsrs r3,r3,#4
    bcc single
    ldr r0,[r5,#24]
    ldr r1,[r5,#16]
    bl #0x20000028
    b closegate
single:
    movs r0,#0
    str r0,[r6,#0]
    str r0,[r6,#4]
    str r0,[r6,#8]
    adds r6,#12
closegate:
    ldr r0,[r5,#4]
    ldr r2,[r0]
    ldr r1,[r5,#8]
    bics r2,r1
    str r2,[r0]
    ldr r1,[r5,#12]
    lsls r1,r1,#2
    ldr r0,[r1]
    str r0,[r6,#0]
    ldr r1,[r5,#16]
    lsls r1,r1,#2
    ldr r0,[r1]
    str r0,[r6,#4]
    ldr r2,[r5,#0]
    ldr r0,[r2,#4]
    str r0,[r6,#8]
    ldr r0,[r5,#4]
    ldr r0,[r0]
    str r0,[r6,#12]
    movs r1,#40
"""


def diag_stub(page, word=0, values=(0, 0), flags=0, guard=GUARD, send=SEND):
    """guard/send select the bootloader version (v1.0.5 default; v107_stubs.GUARD/SEND)."""
    require(SCRATCH_FIRST <= page <= SCRATCH_LAST, "Diagnostic page outside the scratch window")
    require(flags & ~(REWRITE_ADDRESS | DELAY | ERASE | TWO_OPS | IMMEDIATE | POLL_BOTH) == 0, "Unknown diagnostic flag")
    require(not flags & POLL_BOTH or flags & IMMEDIATE, "POLL_BOTH applies to the IMMEDIATE variant")
    if flags & ERASE:
        require(not flags & TWO_OPS and word == 0, "Erase is a single page operation")
    require(0 <= word <= (126 if flags & TWO_OPS else 127), "Word outside the scratch page")
    address0 = page << 7 | word
    address1 = page << 7 | min(word + 1, 127)
    image = blank()
    place(image, 0x80, guard, 0xB0)
    place(image, 0x28, OP, 0x6C)
    place(image, 0xB0, GO, 0xDA)
    go_done = 0x200000B0 + len(assemble(GO, 0xB0)) - 10  # GO "done:" = its last five 16-bit instructions
    place(image, 0x04, GOI.format(go_done=hex(go_done)), 0x24)
    table = struct.pack("<9I", CTRL, GATE + (page >> 5) * 4, 1 << (page & 31), address0, address1,
                        values[0] & 0xFFFFFFFF, values[1] & 0xFFFFFFFF, flags, 3 if flags & POLL_BOTH else 2)
    image[TABLE:TABLE + len(table)] = table
    place(image, 0x140, MAIN + send, 440)
    require(len(image) == 440, "Stub must keep the native 440-byte size")
    return bytes(image)


def parse(reply):
    require(len(reply) == 4 * REPLY_WORDS, "Short diagnostic reply")
    w = struct.unpack(f"<{REPLY_WORDS}I", reply)
    return dict(op0=dict(status_after_start=hex(w[0]), busy_polls=w[1], status_end=hex(w[2])),
                op1=dict(status_after_start=hex(w[3]), busy_polls=w[4], status_end=hex(w[5])),
                word0=hex(w[6]), word1=hex(w[7]), address_reg=hex(w[8]), gate_reg=hex(w[9]))
