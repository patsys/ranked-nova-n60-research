# Copyright 2026 patsys
# SPDX-License-Identifier: GPL-3.0-or-later
"""Authored bounded RAM probes, generated from readable Thumb source."""
from functools import lru_cache
from keystone import Ks, KS_ARCH_ARM, KS_MODE_THUMB

from .image import digest, require

BASE = 0x20000000
ENTRIES = (0, 0x24, 0x6C, 0xDA, 0xFC, 0x13A)
GUARD = """
    mov r0,lr; movs r2,#0x10; lsls r2,#8; adds r2,#0x21;
    cmp r0,r2; bne done; ldr r0,[sp,#52];
    movs r2,#0x0c; lsls r2,#8; adds r2,#0xc3; cmp r0,r2; bne done;
    movs r2,#0x20; lsls r2,#24; adds r2,#255; adds r2,#66; str r2,[sp,#52];
done: movs r0,#0; bx lr
"""
SEND = """
    strh r1,[r4,#4]; mov r0,r4; adds r0,#255; adds r0,#255; adds r0,#2;
    ldr r0,[r0,#20]; blx r0;
    movs r3,#14; lsls r3,#8; adds r3,#0x71; bx r3
"""


def assemble(source, offset):
    return bytes(Ks(KS_ARCH_ARM, KS_MODE_THUMB).asm(source, BASE + offset)[0])


def blank():
    image = bytearray(b"\x70\x47" * 220)
    for offset in ENTRIES:
        image[offset:offset + 4] = b"\0\x20\x70\x47"
    image[0x13A:0x13C] = assemble("b #0x20000080", 0x13A)
    return image


def place(image, offset, source, end):
    code = assemble(source, offset)
    require(offset + len(code) <= end, "RAM stub source exceeds its bounded section")
    image[offset:offset + len(code)] = code


def mov32(register, value):
    octets = value.to_bytes(4, "big")
    parts = [f"movs {register},#{octets[0]}"]
    for byte in octets[1:]:
        parts.extend([f"lsls {register},#8", f"adds {register},#{byte}"])
    return "; ".join(parts)


@lru_cache(maxsize=32)
def read_stub(address, length, metadata=False):
    if metadata:
        require(0x10000600 <= address and address + length <= 0x10000800 and address % 4 == length % 4 == 0, "Metadata read outside observed window")
    else:
        require(0 <= address and address + length <= 0x20000, "Read outside CPU flash")
    require(1 <= length <= 56, "Read reply must fit its native buffer")
    image = blank()
    place(image, 0x80, GUARD, 0xDA)
    if metadata:
        tail = mov32("r0", address) + f""";
            mov r2,r4; adds r2,#8; movs r1,#{length // 4};
        loop: ldr r3,[r0]; str r3,[r2]; adds r0,#4; adds r2,#4;
            subs r1,#1; bne loop; movs r1,#{length};
        """ + SEND
    else:
        tail = mov32("r0", address) + f""";
            mov r2,r4; adds r2,#8; movs r1,#{length};
        loop: ldrb r3,[r0]; strb r3,[r2]; adds r0,#1; adds r2,#1;
            subs r1,#1; bne loop; movs r1,#{length};
        """ + SEND
    place(image, 0x140, tail, 440)
    return bytes(image)


@lru_cache(maxsize=2)
def core_stub(mask):
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


@lru_cache(maxsize=1)
def hold_stub():
    image = bytearray(read_stub(0x101C, 6))
    source = """
        mov r0,lr; movs r2,#0x10; lsls r2,#8; adds r2,#0x21;
        cmp r0,r2; bne done; ldr r0,[sp,#52];
        movs r2,#0xc; lsls r2,#8; adds r2,#0xc3; cmp r0,r2; bne done;
        ldr r0,[sp,#116]; movs r2,#8; lsls r2,#8; adds r2,#0x49;
        cmp r0,r2; beq hold; adds r2,#0x36; cmp r0,r2; bne done; subs r2,#0x36;
    hold: str r2,[sp,#116]; movs r2,#0x20; lsls r2,#24;
        adds r2,#255; adds r2,#66; str r2,[sp,#52];
    done: movs r0,#0; bx lr
    """
    place(image, 0x80, source, 0xDA)
    require(digest(image) == "1c04bf5c4c9ae72885acfd8a62dc948219bb36c4cbc7a12ea3106367a0ebf871", "Holder differs from validated instructions")
    return bytes(image)


@lru_cache(maxsize=1)
def release_stub():
    image = blank()
    source = """
        mov r0,lr; movs r2,#0x10; lsls r2,#8; adds r2,#0x21;
        cmp r0,r2; bne fail; ldr r0,[sp,#52];
        movs r2,#0xc; lsls r2,#8; adds r2,#0xc3; cmp r0,r2; bne fail;
        ldr r0,[sp,#116]; movs r2,#8; lsls r2,#8; adds r2,#0x49;
        cmp r0,r2; beq release; adds r2,#0x36; cmp r0,r2; bne fail; b done;
    release: adds r2,#0x36; str r2,[sp,#116];
    done: movs r0,#0; bx lr;
    fail: movs r0,#2; bx lr
    """
    place(image, 0x80, source, 0xDA)
    require(digest(image) == "57332cb094949feeba32c44fa829bb57069eaef61d92bceab161601737af4323", "Release differs from validated instructions")
    return bytes(image)
