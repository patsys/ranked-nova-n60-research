# Copyright 2026 patsys
# SPDX-License-Identifier: GPL-3.0-or-later
"""Strict Intel HEX parsing and application-only overlays. No USB imports."""
from dataclasses import dataclass
import hashlib
import struct

START = 0x2000
END = 0x10A00
FLASH_SIZE = 0x20000
PAGE_SIZE = 512
BOOT_SHA = "e46c6d9300a13f4d2eea7c16584d24ea6e4e1b83815e5f84f389d4aeb0915f62"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class Image:
    data: dict
    entry: int | None = None

    def overlay(self, before):
        require(len(before) == FLASH_SIZE, "Full 128 KiB pre-write backup required")
        require(digest(before[:START]) == BOOT_SHA, "Unsupported bootloader bytes")
        result = bytearray(before)
        for address, value in self.data.items():
            require(START <= address < END, "Image outside supported application pages")
            result[address] = value
        require(result[:START] == before[:START] and result[END:] == before[END:], "Protected region changed")
        return bytes(result)


def parse_hex(text):
    data = {}
    base = 0
    entry = None
    eof = False
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        require(not eof, f"Record after EOF at line {line_number}")
        require(line.startswith(":"), f"Missing record marker at line {line_number}")
        require(all(c in "0123456789abcdefABCDEF" for c in line[1:]), "Non-hex record data")
        try:
            record = bytes.fromhex(line[1:])
        except ValueError as error:
            raise ValueError(f"Invalid record at line {line_number}") from error
        require(len(record) >= 5 and len(record) == record[0] + 5, "Incorrect record length")
        require(sum(record) & 255 == 0, "Intel HEX checksum mismatch")
        size, address, kind = record[0], int.from_bytes(record[1:3], "big"), record[3]
        payload = record[4:-1]
        if kind == 0:
            require(size > 0 and address + size <= 0x10000, "Invalid data record span")
            for offset, value in enumerate(payload):
                absolute = base + address + offset
                require(START <= absolute < END, "Image touches bootloader, settings or unsupported pages")
                require(absolute not in data, "Overlapping Intel HEX records")
                data[absolute] = value
        elif kind == 1:
            require(size == 0 and address == 0, "Malformed EOF")
            eof = True
        elif kind in (2, 4):
            require(size == 2 and address == 0, "Malformed address extension")
            base = int.from_bytes(payload, "big") << (4 if kind == 2 else 16)
        elif kind in (3, 5):
            require(size == 4 and address == 0 and entry is None, "Malformed or repeated entry point")
            entry = ((int.from_bytes(payload[:2], "big") << 4) + int.from_bytes(payload[2:], "big")) if kind == 3 else int.from_bytes(payload, "big")
        else:
            raise ValueError(f"Unsupported Intel HEX record type {kind}")
    require(eof and data, "Missing EOF or empty image")
    require(all(address in data for address in range(START, START + 160)), "Complete application vector table required")
    vectors = struct.unpack("<40I", bytes(data[address] for address in range(START, START + 160)))
    require(0x20000008 <= vectors[0] <= 0x20001C50 and vectors[0] % 8 == 0, "Invalid initial stack")
    for index, vector in enumerate(vectors[1:], 1):
        if vector == 0 and index not in (1, 15, 20):
            continue
        require(vector & 1 and (vector & ~1) in data, f"Invalid application vector {index}")
    require(entry is None or entry == vectors[1], "HEX entry point disagrees with reset vector")
    return Image(data, entry)
