#!/usr/bin/env python3
"""Add spacing around dialogue punctuation on the typewriter-fix v2 ISO."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import struct
from pathlib import Path

from keystone import KS_ARCH_MIPS, KS_MODE_LITTLE_ENDIAN, KS_MODE_MIPS32, Ks

from build_iso_poc import locate_iso9660_path


ELF_BASE = 0x08804000
ELF_FILE_OFFSET = 0x54
BOOT_PATH = "/PSP_GAME/SYSDIR/BOOT.BIN;1"
EBOOT_PATH = "/PSP_GAME/SYSDIR/EBOOT.BIN;1"

# v2 already occupies the first 316 bytes of the audited 0x200-byte cave.
CODE_CAVE_VA = 0x088D0DCC
V2_HELPERS_SIZE = 316
CODE_CAVE_SIZE = 0x200
PUNCT_HELPER_VA = CODE_CAVE_VA + V2_HELPERS_SIZE
V2_HELPERS_SHA256 = "de137e3f75da55140e0137b6d3a69958bc4f0b1001d2849773c6d646fa7734d8"

# Replace v2's byte<0x80 classifier with a tail-call helper.  The helper
# returns to the same ASCII/non-ASCII continuations after shifting only the
# visible punctuation glyph origin.  ASCII '.' has already been remapped by
# the renderer to CP932 0x8144 at this point, so it is recognized separately.
ASCII_CLASSIFY_VA = 0x08899948
ASCII_BRANCH_VA = 0x0889994C
V2_ASCII_CLASSIFY = 0x2CA20080
V2_ASCII_BRANCH = 0x10400003
ASCII_CONTINUE_VA = 0x08899950
NON_ASCII_CONTINUE_VA = 0x0889995C

# The v2 test patch changed the shared renderer's default double-byte advance
# from 13 to 9 pixels.  That also compressed original Japanese UI, while the
# UI texture refresh/clear path still used its original geometry.  Repeated
# menu changes consequently left old Japanese cell fragments behind.  Route
# the advance selection through the remaining code-cave bytes: only CP932
# user-defined lead bytes F0-F9 (the production Hangul allocation) use 9px;
# original Japanese double-byte glyphs keep the native 13px advance.
ADVANCE_BRANCH_VA = 0x088997BC
ADVANCE_DELAY_VA = 0x088997C0
ADVANCE_ASCII_VA = 0x088997C4
ADVANCE_JUMP_VA = 0x088997C8
ADVANCE_STORE_DELAY_VA = 0x088997CC
ADVANCE_STORE_VA = 0x088997D0
V2_ADVANCE_WORDS = (
    0x50400004,
    0x24060009,
    0x24060006,
    0x10000002,
    0xAFA60038,
    0xAFA60038,
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _offset(virtual_address: int) -> int:
    return ELF_FILE_OFFSET + virtual_address - ELF_BASE


def _jump(target: int) -> int:
    return 0x08000000 | ((target >> 2) & 0x03FFFFFF)


def _assemble(source: str, address: int) -> bytes:
    assembler = Ks(KS_ARCH_MIPS, KS_MODE_MIPS32 | KS_MODE_LITTLE_ENDIAN)
    encoded, _ = assembler.asm(source, addr=address, as_bytes=True)
    return bytes(encoded)


def _helper_source(leading_gap: int) -> str:
    return f"""
        sltiu $v0, $a1, 0x80
        beq   $v0, $zero, check_period
        nop
        addiu $t0, $zero, 0x21
        beq   $a1, $t0, add_gap
        nop
        addiu $t0, $zero, 0x2C
        beq   $a1, $t0, add_gap
        nop
        addiu $t0, $zero, 0x3F
        beq   $a1, $t0, add_gap
        nop
        j     0x{ASCII_CONTINUE_VA:08X}
        nop
    check_period:
        addiu $t0, $zero, 0x81
        bne   $a1, $t0, non_ascii
        nop
        addiu $t0, $zero, 0x44
        bne   $a0, $t0, non_ascii
        nop
    add_gap:
        addiu $s5, $s5, {leading_gap}
        lw    $t1, 0x38($sp)
        addiu $t1, $t1, {leading_gap}
        sw    $t1, 0x38($sp)
        sltiu $v0, $a1, 0x80
        bne   $v0, $zero, ascii
        nop
    non_ascii:
        j     0x{NON_ASCII_CONTINUE_VA:08X}
        nop
    ascii:
        j     0x{ASCII_CONTINUE_VA:08X}
        nop
    """


def _hangul_advance_helper_source(return_va: int) -> str:
    return f"""
        .set noreorder
        sltiu $a2, $a1, 0xF0
        xori  $a2, $a2, 1
        sltiu $t0, $a1, 0xFA
        and   $a2, $a2, $t0
        sll   $a2, $a2, 2
        addiu $t0, $zero, 13
        j     0x{return_va:08X}
        subu  $a2, $t0, $a2
    """


def _read_extent(path: Path, offset: int, size: int) -> bytes:
    with path.open("rb") as stream:
        stream.seek(offset)
        return stream.read(size)


def patch_executable(source: bytes, leading_gap: int) -> tuple[bytes, dict[str, object]]:
    if source[:4] != b"\x7fELF":
        raise ValueError("executable is not a plaintext ELF")
    if not 0 <= leading_gap <= 4:
        raise ValueError("punctuation leading gap must be between 0 and 4 pixels")

    cave_offset = _offset(CODE_CAVE_VA)
    existing_helpers = source[cave_offset:cave_offset + V2_HELPERS_SIZE]
    if _sha256(existing_helpers) != V2_HELPERS_SHA256:
        raise ValueError("typewriter-fix v2 helper fingerprint mismatch")

    helper = _assemble(_helper_source(leading_gap), PUNCT_HELPER_VA)
    remaining = CODE_CAVE_SIZE - V2_HELPERS_SIZE
    advance_helper_va = PUNCT_HELPER_VA + len(helper)
    advance_helper = _assemble(
        _hangul_advance_helper_source(ADVANCE_STORE_VA),
        advance_helper_va,
    )
    combined_helper = helper + advance_helper
    if len(combined_helper) > remaining:
        raise ValueError("punctuation helper exceeds the audited code cave")
    helper_offset = _offset(PUNCT_HELPER_VA)
    if any(source[helper_offset:cave_offset + CODE_CAVE_SIZE]):
        raise ValueError("remaining audited code cave is no longer zero-filled")

    output = bytearray(source)
    patches = [
        (
            ASCII_CLASSIFY_VA,
            V2_ASCII_CLASSIFY,
            _jump(PUNCT_HELPER_VA),
            "route ASCII classification through punctuation spacing helper",
        ),
        (
            ASCII_BRANCH_VA,
            V2_ASCII_BRANCH,
            0x00000000,
            "punctuation helper jump delay slot",
        ),
    ]
    advance_patch = _assemble(
        f"""
            .set noreorder
            bnez  $v0, advance_ascii
            nop
            j     0x{advance_helper_va:08X}
            nop
        advance_ascii:
            addiu $a2, $zero, 6
            sw    $a2, 0x38($sp)
        """,
        ADVANCE_BRANCH_VA,
    )
    if len(advance_patch) != 24:
        raise RuntimeError("unexpected Hangul advance dispatch size")
    for index, (va, expected) in enumerate(
        zip(
            (
                ADVANCE_BRANCH_VA,
                ADVANCE_DELAY_VA,
                ADVANCE_ASCII_VA,
                ADVANCE_JUMP_VA,
                ADVANCE_STORE_DELAY_VA,
                ADVANCE_STORE_VA,
            ),
            V2_ADVANCE_WORDS,
            strict=True,
        )
    ):
        replacement, = struct.unpack_from("<I", advance_patch, index * 4)
        patches.append(
            (
                va,
                expected,
                replacement,
                "dispatch 9px only for CP932 F0-F9 Hangul"
                if index == 0
                else f"Hangul advance dispatch word {index + 1}",
            )
        )
    rows = []
    for va, expected, replacement, label in patches:
        offset = _offset(va)
        actual, = struct.unpack_from("<I", source, offset)
        if actual != expected:
            raise ValueError(
                f"{label} fingerprint mismatch at 0x{va:08X}: "
                f"expected 0x{expected:08X}, got 0x{actual:08X}"
            )
        struct.pack_into("<I", output, offset, replacement)
        rows.append(
            {
                "label": label,
                "virtual_address": f"0x{va:08X}",
                "file_offset": f"0x{offset:X}",
                "original_word": f"0x{expected:08X}",
                "patched_word": f"0x{replacement:08X}",
            }
        )
    output[helper_offset:helper_offset + len(combined_helper)] = combined_helper

    return bytes(output), {
        "instructions": rows,
        "code_cave": {
            "helper_virtual_address": f"0x{PUNCT_HELPER_VA:08X}",
            "file_offset": f"0x{helper_offset:X}",
            "available_bytes": remaining,
            "used_bytes": len(combined_helper),
            "sha256": _sha256(combined_helper),
            "punctuation_helper_bytes": len(helper),
            "hangul_advance_helper_virtual_address": f"0x{advance_helper_va:08X}",
            "hangul_advance_helper_bytes": len(advance_helper),
        },
        "spacing": {
            "punctuation": ["!", ",", ".", "?"],
            "punctuation_leading_gap_px": leading_gap,
            "punctuation_trailing_gap_px": leading_gap,
            "existing_space_advance_px": 6,
            "hangul_cp932_lead_range": "F0-F9",
            "hangul_double_byte_advance_px": 9,
            "original_japanese_double_byte_advance_px": 13,
        },
    }


def build(
    baseline_iso: Path,
    output_iso: Path,
    report_path: Path,
    leading_gap: int,
) -> dict[str, object]:
    boot_record = locate_iso9660_path(baseline_iso, BOOT_PATH)
    eboot_record = locate_iso9660_path(baseline_iso, EBOOT_PATH)
    boot_source = _read_extent(baseline_iso, boot_record.offset, boot_record.size)
    eboot_source = _read_extent(baseline_iso, eboot_record.offset, eboot_record.size)
    boot_output, patch_report = patch_executable(boot_source, leading_gap)
    eboot_output, eboot_patch_report = patch_executable(eboot_source, leading_gap)
    if patch_report != eboot_patch_report:
        raise ValueError("BOOT and EBOOT patch reports differ")

    output_iso.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_iso.with_name(output_iso.name + ".tmp")
    try:
        shutil.copyfile(baseline_iso, temporary)
        with temporary.open("r+b") as stream:
            stream.seek(boot_record.offset)
            stream.write(boot_output)
            stream.seek(eboot_record.offset)
            stream.write(eboot_output)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output_iso)
    finally:
        if temporary.exists():
            temporary.unlink()

    for record, expected in ((boot_record, boot_output), (eboot_record, eboot_output)):
        if _read_extent(output_iso, record.offset, record.size) != expected:
            raise ValueError("patched executable did not round-trip from ISO")
    if output_iso.stat().st_size != baseline_iso.stat().st_size:
        raise ValueError("output ISO size changed")

    report = {
        "schema_version": 1,
        "gate_id": "DIALOG-PUNCTUATION-SPACING-001",
        "status": "PASS",
        "baseline": {
            "path": baseline_iso.as_posix(),
            "size": baseline_iso.stat().st_size,
            "sha256": _sha256_file(baseline_iso),
        },
        "patch": patch_report,
        "output": {
            "path": output_iso.as_posix(),
            "size": output_iso.stat().st_size,
            "sha256": _sha256_file(output_iso),
        },
        "runtime_gate": {
            "status": "PENDING",
            "checks": [
                "visible gap around comma in 자,",
                "visible gap before exclamation and question marks",
                "ellipsis dots remain readable and separated from following text",
                "no regression in Korean glyph or word-space tracking",
                "no transient kanji or malformed Hangul during typewriter reveal",
            ],
        },
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline_iso", type=Path)
    parser.add_argument("output_iso", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--leading-gap", type=int, default=2)
    args = parser.parse_args()
    report = build(args.baseline_iso, args.output_iso, args.report, args.leading_gap)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
