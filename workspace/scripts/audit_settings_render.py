#!/usr/bin/env python3
"""Locate code that loads the settings-menu string pointer entries."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from capstone import CS_ARCH_MIPS, CS_MODE_LITTLE_ENDIAN, CS_MODE_MIPS32, Cs


ELF_BASE = 0x08804000
ELF_FILE_OFFSET = 0x54
TABLE_BASE = 0x088E0628
SETTINGS_FIRST_INDEX = 33
SETTINGS_LAST_INDEX = 49
RENDERER = 0x08899698


def va_to_offset(va: int) -> int:
    return ELF_FILE_OFFSET + va - ELF_BASE


def decode_jal(word: int, pc: int) -> int | None:
    if word >> 26 != 0x03:
        return None
    return ((pc + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("boot", type=Path)
    parser.add_argument("--start", type=lambda value: int(value, 0))
    parser.add_argument("--end", type=lambda value: int(value, 0))
    args = parser.parse_args()

    data = args.boot.read_bytes()
    if data[:4] != b"\x7fELF":
        raise SystemExit("BOOT.BIN is not a plaintext ELF")

    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32 | CS_MODE_LITTLE_ENDIAN)
    md.detail = False
    if args.start is not None or args.end is not None:
        if args.start is None or args.end is None or args.end <= args.start:
            raise SystemExit("--start and --end must define a non-empty VA range")
        start_offset = va_to_offset(args.start)
        end_offset = va_to_offset(args.end)
        for insn in md.disasm(data[start_offset:end_offset], args.start):
            word, = struct.unpack_from("<I", data, va_to_offset(insn.address))
            target = decode_jal(word, insn.address)
            suffix = ""
            if target is not None:
                suffix = f"  ; jal_target=0x{target:08X}"
            print(
                f"0x{insn.address:08X}: "
                f"{insn.mnemonic:<8} {insn.op_str}{suffix}"
            )
        return

    code_end = min(len(data), va_to_offset(TABLE_BASE))
    code = data[ELF_FILE_OFFSET:code_end]
    words = list(struct.unpack(f"<{len(code) // 4}I", code[: len(code) & ~3]))
    hits: set[int] = set()

    # Direct form: lui rx,0x088E; lw ry,0x06AC(rx), etc.
    wanted_offsets = {
        (TABLE_BASE & 0xFFFF) + index * 4
        for index in range(SETTINGS_FIRST_INDEX, SETTINGS_LAST_INDEX + 1)
    }
    for index, word in enumerate(words):
        if word >> 26 != 0x0F or (word & 0xFFFF) != 0x088E:
            continue
        base_register = (word >> 16) & 0x1F
        for lookahead in range(index + 1, min(index + 25, len(words))):
            candidate = words[lookahead]
            opcode = candidate >> 26
            base = (candidate >> 21) & 0x1F
            immediate = candidate & 0xFFFF
            if opcode == 0x23 and base == base_register and immediate in wanted_offsets:
                hits.add(lookahead)

    # Base-plus-index form: materialize TABLE_BASE, then use small indexed loads.
    for index, word in enumerate(words):
        if word >> 26 != 0x0F or (word & 0xFFFF) != 0x088E:
            continue
        base_register = (word >> 16) & 0x1F
        for lookahead in range(index + 1, min(index + 10, len(words))):
            candidate = words[lookahead]
            opcode = candidate >> 26
            rs = (candidate >> 21) & 0x1F
            rt = (candidate >> 16) & 0x1F
            immediate = candidate & 0xFFFF
            if (
                opcode in (0x09, 0x0D)
                and rs == base_register
                and rt == base_register
                and immediate == (TABLE_BASE & 0xFFFF)
            ):
                hits.add(lookahead)

    print(f"settings pointer offsets: {min(wanted_offsets):#x}..{max(wanted_offsets):#x}")
    print(f"candidate instructions: {len(hits)}")
    for hit in sorted(hits):
        start = max(0, hit - 12)
        end = min(len(words), hit + 28)
        start_va = ELF_BASE + start * 4
        blob = code[start * 4 : end * 4]
        print(f"\n=== candidate 0x{ELF_BASE + hit * 4:08X} ===")
        for insn in md.disasm(blob, start_va):
            marker = ">>" if insn.address == ELF_BASE + hit * 4 else "  "
            word = words[(insn.address - ELF_BASE) // 4]
            target = decode_jal(word, insn.address)
            suffix = ""
            if target == RENDERER:
                suffix = "  ; COMMON_RENDERER"
            print(
                f"{marker} 0x{insn.address:08X}: "
                f"{insn.mnemonic:<8} {insn.op_str}{suffix}"
            )


if __name__ == "__main__":
    main()
