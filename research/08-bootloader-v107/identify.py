# Copyright 2026 patsys
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only identification of the RY7203: ROM table IDs, controller registers, info flash.

word_read_stub() is ry72xx-flasher's metadata read stub generalised to a fixed
allowlist of windows. It only loads words and replies; it never stores outside
the native reply buffer.
"""
import struct

import diag_stub  # noqa: F401  (puts ry72xx_flasher on sys.path)
from ry72xx_flasher.image import require
from ry72xx_flasher.stubs import GUARD, SEND, blank, mov32, place

WINDOWS = {
    "rom_table": (0xE00FF000, 0xE0100000),
    "flash_controller": (0x40013000, 0x40013100),
    "info_flash": (0x10000000, 0x10000800),
}
CHUNK = 56


def word_read_stub(address, length):
    require(address % 4 == 0 and length % 4 == 0 and 4 <= length <= CHUNK, "Word read must fit one reply")
    require(any(lo <= address and address + length <= hi for lo, hi in WINDOWS.values()), "Read outside the identification windows")
    image = blank()
    place(image, 0x80, GUARD, 0xDA)
    tail = mov32("r0", address) + f""";
        mov r2,r4; adds r2,#8; movs r1,#{length // 4};
    loop: ldr r3,[r0]; str r3,[r2]; adds r0,#4; adds r2,#4;
        subs r1,#1; bne loop; movs r1,#{length};
    """ + SEND
    place(image, 0x140, tail, 440)
    return bytes(image)


def read_words(transport, address, length):
    out = bytearray()
    for current in range(address, address + length, CHUNK):
        count = min(CHUNK, address + length - current)
        out.extend(transport.start(word_read_stub(current, count), count))
    return bytes(out)


def decode_rom_table(block):
    """block: the last 0x30 bytes of the ROM table (0xE00FFFD0..0xE00FFFFF)."""
    pidr4, _, _, _, pidr0, pidr1, pidr2, pidr3, cidr0, cidr1, cidr2, cidr3 = struct.unpack("<12I", block)
    designer = ((pidr1 >> 4) & 0xF) | ((pidr2 & 7) << 4)
    return dict(
        pidr=[hex(v) for v in (pidr0, pidr1, pidr2, pidr3, pidr4)],
        cidr=[hex(v) for v in (cidr0, cidr1, cidr2, cidr3)],
        valid_component=(cidr0, cidr1 & 0x0F, cidr2, cidr3) == (0x0D, 0x00, 0x05, 0xB1),
        uses_jep106=bool(pidr2 & 8),
        jep106_continuation=pidr4 & 0xF,
        jep106_id=hex(designer),
        part_number=hex(pidr0 & 0xFF | (pidr1 & 0xF) << 8),
        revision=pidr2 >> 4,
    )


def identify(transport):
    rom_entries = read_words(transport, 0xE00FF000, 16)
    rom_ids = read_words(transport, 0xE00FFFD0, 0x30)
    controller = read_words(transport, 0x40013000, 0x100)
    info = read_words(transport, 0x10000000, 0x800)
    return dict(
        rom_table_entries=[hex(v) for v in struct.unpack("<4I", rom_entries)],
        rom_table=decode_rom_table(rom_ids),
        flash_controller={hex(o): hex(v) for o, v in zip(range(0, 0x100, 4), struct.unpack("<64I", controller))},
    ), controller, info
