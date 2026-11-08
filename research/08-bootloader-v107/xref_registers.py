# Copyright 2026 patsys
# SPDX-License-Identifier: GPL-3.0-or-later
"""Static cross-reference of peripheral register accesses in the v1.0.7 bootloader and stock app.

Linear Thumb disassembly with simple constant propagation per straight-line block:
registers loaded from PC-relative literals or built by movs/lsls/adds/subs are tracked;
branches and calls reset (calls clobber r0-r3, r12). Each ldr/str [rN,#imm] with a known
base inside a watched block is reported with the stored value when it is constant.
Heuristic: literal pools disassembled as code can add noise; every hit lists its address.

usage: xref_registers.py [base ...]   (default 0x40013000 0x40014000)
"""
import struct
import sys
from collections import defaultdict
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_MCLASS, CS_MODE_THUMB, Cs
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_OP_REG

DUMP = Path(__file__).resolve().parent / "v107_dump/flash_pass1.bin"
IMAGES = {"boot": (0x0, 0x1834), "app": (0x2000, 0x2000 + 0xE908)}


def trace(flash, start, end, blocks):
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    md.detail = True
    hits = []
    known = {}
    address = start
    while address < end:
        decoded = next(md.disasm(flash[address:address + 4], address), None)
        if decoded is None:
            known = {}
            address += 2
            continue
        i = decoded
        ops = i.operands
        name = i.mnemonic.split(".")[0]
        reg = lambda op: i.reg_name(op.reg)
        if name == "ldr" and len(ops) == 2 and ops[1].type == ARM_OP_MEM and i.reg_name(ops[1].mem.base) == "pc":
            literal = ((i.address + 4) & ~3) + ops[1].mem.disp
            if 0 <= literal < len(flash) - 3:
                known[reg(ops[0])] = struct.unpack_from("<I", flash, literal)[0]
            else:
                known.pop(reg(ops[0]), None)
        elif name in ("ldr", "ldrh", "ldrb", "str", "strh", "strb") and len(ops) == 2 and ops[1].type == ARM_OP_MEM:
            base = i.reg_name(ops[1].mem.base)
            index = ops[1].mem.index
            if base in known and not index:
                target = known[base] + ops[1].mem.disp
                for lo, hi in blocks:
                    if lo <= target < hi:
                        value = known.get(reg(ops[0])) if name.startswith("str") else None
                        hits.append((i.address, name, target, value))
            if name.startswith("ldr"):
                known.pop(reg(ops[0]), None)
        elif name == "movs" and len(ops) == 2 and ops[1].type == ARM_OP_IMM:
            known[reg(ops[0])] = ops[1].imm
        elif name == "mov" and len(ops) == 2 and ops[1].type == ARM_OP_REG:
            if reg(ops[1]) in known:
                known[reg(ops[0])] = known[reg(ops[1])]
            else:
                known.pop(reg(ops[0]), None)
        elif name in ("lsls", "lsrs", "adds", "subs", "orrs", "bics", "ands") and ops and ops[0].type == ARM_OP_REG:
            dst = reg(ops[0])
            src, operand = (ops[1], ops[2]) if len(ops) == 3 else (ops[0], ops[1])
            a = known.get(reg(src)) if src.type == ARM_OP_REG else src.imm
            b = operand.imm if operand.type == ARM_OP_IMM else known.get(reg(operand))
            if a is None or b is None:
                known.pop(dst, None)
            else:
                known[dst] = {"lsls": lambda: a << b, "lsrs": lambda: a >> b, "adds": lambda: a + b,
                              "subs": lambda: a - b, "orrs": lambda: a | b, "bics": lambda: a & ~b,
                              "ands": lambda: a & b}[name]() & 0xFFFFFFFF
        elif name in ("bl", "blx"):
            for r in ("r0", "r1", "r2", "r3", "r12", "lr"):
                known.pop(r, None)
        elif name.startswith("b") or name in ("pop", "bx", "cbz", "cbnz"):
            known = {}
        elif ops and ops[0].type == ARM_OP_REG:
            known.pop(reg(ops[0]), None)
        address += i.size
    return hits


def main():
    bases = [int(a, 0) for a in sys.argv[1:]] or [0x40013000, 0x40014000]
    blocks = [(b, b + 0x1000) for b in bases]
    flash = DUMP.read_bytes()
    table = defaultdict(list)
    for image, (start, end) in IMAGES.items():
        for address, op, target, value in trace(flash, start, end, blocks):
            table[target].append((image, address, op, value))
    for target in sorted(table):
        print(f"{target:#010x}")
        for image, address, op, value in table[target]:
            print(f"    {image:4} {address:#07x} {op:5} {'' if value is None else hex(value)}")


if __name__ == "__main__":
    main()
