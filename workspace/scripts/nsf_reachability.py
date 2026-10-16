#!/usr/bin/env python3
"""Validate NSF message candidates against block-local BOOT dispatcher stepping."""

from __future__ import annotations

import argparse
import bisect
import struct
from dataclasses import dataclass
from pathlib import Path

import demo00
import nsf_links
import nsf_messages

try:
    from unicorn import (
        UC_ARCH_MIPS,
        UC_HOOK_CODE,
        UC_HOOK_MEM_INVALID,
        UC_MODE_LITTLE_ENDIAN,
        UC_MODE_MIPS32,
        Uc,
        UcError,
    )
    from unicorn.mips_const import (
        UC_MIPS_REG_A0,
        UC_MIPS_REG_PC,
        UC_MIPS_REG_RA,
        UC_MIPS_REG_S0,
        UC_MIPS_REG_S1,
        UC_MIPS_REG_S3,
        UC_MIPS_REG_S4,
        UC_MIPS_REG_S7,
        UC_MIPS_REG_SP,
        UC_MIPS_REG_V0,
    )
except ImportError as exc:  # pragma: no cover - exercised by CLI environments
    raise SystemExit(
        "unicorn 2.1.4 is required; install it into work/pydeps as documented in docs/build.md"
    ) from exc


ELF_BASE = 0x08804000
ELF_FILE_OFFSET = 84
ELF_LOAD_END = 0x00113144
RAM_BASE = 0x08000000
RAM_SIZE = 0x02000000
VM = 0x09000000
SCRIPT = 0x09100000
SCRATCH = 0x09200000
STACK = 0x09EFF000
SENTINEL = 0x09FFF000
DISPATCH_START = 0x088825B0
DISPATCH_NEXT = 0x088825A0
DISPATCH_RETURN = 0x08882D68
DISPATCH_END = DISPATCH_RETURN
OPERAND_START = 0x08872DBC
OPERAND_END = 0x08872F14
GROUP_TABLES = 0x088F6AE4


@dataclass(frozen=True)
class Step:
    start: int
    end: int
    outcome: str


@dataclass(frozen=True)
class Audit:
    proven_offsets: frozenset[int]
    attempted_blocks: int
    completed_blocks: int
    failed_blocks: int


class DispatcherStepper:
    def __init__(self, boot: bytes, nsf: nsf_links.Nsf):
        self.boot = boot
        self.nsf = nsf
        pointers = set()
        for group in range(0x3C, 0x100):
            table = self._u32_va(GROUP_TABLES + group * 4)
            if not 0x088D0000 <= table < 0x08920000:
                continue
            for subopcode in range(0x100):
                handler = self._u32_va(table + subopcode * 4)
                if ELF_BASE <= handler < 0x088D00C4:
                    pointers.add(handler)
        self.handler_starts = tuple(sorted(pointers))

    @staticmethod
    def _file_offset(va: int) -> int:
        return ELF_FILE_OFFSET + va - ELF_BASE

    def _u32_va(self, va: int) -> int:
        offset = self._file_offset(va)
        if offset < 0 or offset + 4 > len(self.boot):
            return 0
        return struct.unpack_from("<I", self.boot, offset)[0]

    def _handler(self, logical_offset: int) -> int:
        opcode = self.nsf.code[logical_offset]
        if opcode < 0x3C or logical_offset + 1 >= len(self.nsf.code):
            return 0
        table = self._u32_va(GROUP_TABLES + opcode * 4)
        if not 0x088D0000 <= table < 0x08920000:
            return 0
        return self._u32_va(table + self.nsf.code[logical_offset + 1] * 4)

    def step(self, logical_offset: int, seed: int = 0) -> Step:
        if not 0 <= logical_offset < len(self.nsf.code):
            return Step(logical_offset, logical_offset, "outside")
        mu = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 | UC_MODE_LITTLE_ENDIAN)
        mu.mem_map(RAM_BASE, RAM_SIZE)
        mu.mem_write(ELF_BASE, self.boot[ELF_FILE_OFFSET:ELF_LOAD_END])
        mu.mem_write(SCRIPT, self.nsf.code)
        mu.mem_write(SCRATCH, struct.pack("<I", seed & 0xFFFFFFFF) * 0x800)
        mu.mem_write(VM + 0x48, struct.pack("<I", logical_offset + 1))
        mu.mem_write(VM + 0x44, struct.pack("<I", SCRATCH))
        mu.mem_write(VM + 0x54, struct.pack("<I", SCRATCH))
        mu.mem_write(SCRATCH + 4, struct.pack("<I", SCRIPT))
        mu.mem_write(SCRATCH + 0x24, struct.pack("<I", SCRATCH + 0x1000))
        for register, value in (
            (UC_MIPS_REG_SP, STACK),
            (UC_MIPS_REG_A0, self.nsf.code[logical_offset]),
            (UC_MIPS_REG_S0, 1),
            (UC_MIPS_REG_S1, VM + 0x48),
            (UC_MIPS_REG_S3, SCRIPT),
            (UC_MIPS_REG_S4, VM),
            (UC_MIPS_REG_S7, SCRATCH),
            (UC_MIPS_REG_RA, SENTINEL),
        ):
            mu.reg_write(register, value)

        handler = self._handler(logical_offset)
        handler_end = 0
        if handler in self.handler_starts:
            index = bisect.bisect_right(self.handler_starts, handler)
            handler_end = (
                self.handler_starts[index]
                if index < len(self.handler_starts)
                else 0x088D00C4
            )
        outcome = "limit"

        def hook(emu: Uc, address: int, _size: int, _user: object) -> None:
            nonlocal outcome
            if address == DISPATCH_NEXT:
                outcome = "next"
                emu.emu_stop()
                return
            if address == DISPATCH_RETURN:
                outcome = "return"
                emu.emu_stop()
                return
            allowed = (
                DISPATCH_START <= address < DISPATCH_END
                or OPERAND_START <= address < OPERAND_END
                or handler != 0 and handler <= address < handler_end
            )
            if not allowed:
                # External side effects are irrelevant to byte consumption. Return a safe pointer/value.
                emu.reg_write(UC_MIPS_REG_V0, SCRATCH)
                emu.reg_write(UC_MIPS_REG_PC, emu.reg_read(UC_MIPS_REG_RA))

        mu.hook_add(UC_HOOK_CODE, hook)

        def map_dummy_page(
            emu: Uc,
            _access: int,
            address: int,
            _size: int,
            _value: int,
            _user: object,
        ) -> bool:
            page = address & ~0xFFF
            try:
                emu.mem_map(page, 0x1000)
            except UcError:
                return False
            return True

        mu.hook_add(UC_HOOK_MEM_INVALID, map_dummy_page)
        try:
            mu.emu_start(DISPATCH_START, 0, count=5000)
        except UcError:
            outcome = "error"
        end, = struct.unpack("<I", mu.mem_read(VM + 0x48, 4))
        return Step(logical_offset, end, outcome)


def audit(
    stepper: DispatcherStepper,
    references: tuple[nsf_messages.Reference, ...],
) -> Audit:
    candidate_offsets = {reference.logical_offset for reference in references}
    selected_blocks = [
        block for block in stepper.nsf.blocks
        if any(block.start <= offset <= block.end for offset in candidate_offsets)
    ]
    proven: set[int] = set()
    completed = 0
    failed = 0
    step_cache: dict[tuple[int, int], Step] = {}
    for block in selected_blocks:
        pending = [block.start]
        visited = set()
        block_ok = True
        while pending:
            offset = pending.pop()
            if offset in visited or not block.start <= offset <= block.end:
                continue
            visited.add(offset)
            if offset in candidate_offsets:
                proven.add(offset)
            usable_result = False
            for seed in (0, 1, 0xFFFFFFFF, 0x7FFFFFFF):
                cache_key = (offset, seed)
                result = step_cache.get(cache_key)
                if result is None:
                    result = stepper.step(offset, seed)
                    step_cache[cache_key] = result
                if result.outcome == "error" or result.end <= offset:
                    continue
                usable_result = True
                # A zero handler result yields the VM for this tick; the saved PC resumes later.
                if block.start <= result.end <= block.end:
                    pending.append(result.end)
            if not usable_result:
                block_ok = False
        if block_ok:
            completed += 1
        else:
            failed += 1
    return Audit(frozenset(proven), len(selected_blocks), completed, failed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("boot", type=Path)
    parser.add_argument("nsf", type=Path)
    parser.add_argument("demo00", type=Path)
    args = parser.parse_args()
    nsf = nsf_links.parse_nsf(args.nsf.read_bytes())
    table = demo00.parse(args.demo00.read_bytes())
    references = nsf_messages.scan(nsf, table)
    result = audit(DispatcherStepper(args.boot.read_bytes(), nsf), references)
    counts = {status: 0 for status in ("demo00", "dynamic", "unresolved")}
    unproven = counts.copy()
    for reference in references:
        target = counts if reference.logical_offset in result.proven_offsets else unproven
        target[reference.status] += 1
    proven_unique = len({
        reference.message_id for reference in references
        if reference.status == "demo00" and reference.logical_offset in result.proven_offsets
    })
    unresolved_unproven = [
        (f"0x{reference.logical_offset:X}", reference.message_id)
        for reference in references
        if reference.status != "demo00" and reference.logical_offset not in result.proven_offsets
    ]
    print(
        f"OK: blocks={result.attempted_blocks}, completed={result.completed_blocks}, "
        f"failed={result.failed_blocks}; proven={counts} "
        f"({proven_unique} unique Demo00 IDs); unproven={unproven}; "
        f"unproven_special={unresolved_unproven}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
