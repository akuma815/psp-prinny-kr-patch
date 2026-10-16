#!/usr/bin/env python3
"""Patch mixed-width CP932 dialogue reveal and Korean dialogue tracking."""

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

# The original typewriter loop uses strlen / 2 as a character count and then
# strncpy(count * 2).  Korean text contains single-byte CP932 spaces and ASCII
# punctuation, so this can expose or terminate in the middle of a Hangul pair.
# ASCII spaces do not allocate glyph-cache cells in the renderer.  Excluding
# them from the reveal-unit count also preserves the original 216-cell cache
# budget instead of spending an extra progressive-reveal step on every space.
COUNT_CALL_VA = 0x088653A0
COUNT_DIVIDE_VA = 0x088653AC
COPY_CALL_VA = 0x088653E8
COPY_MULTIPLY_VA = 0x088653EC
COPY_TRAILING_NUL_VA = 0x088653FC

ORIGINAL_COUNT_CALL = 0x0E20469A  # jal 0x08811A68 (strlen)
ORIGINAL_COUNT_DIVIDE = 0x00021843  # sra v1, v0, 1
ORIGINAL_COPY_CALL = 0x0E2046A0  # jal 0x08811A80 (strncpy-like helper)
ORIGINAL_COPY_MULTIPLY = 0x00023040  # sll a2, v0, 1
ORIGINAL_COPY_TRAILING_NUL = 0xA0400000  # sb zero, 0(v0)

SPACE_ADVANCE_VA = 0x08899760
DOUBLE_BYTE_ADVANCE_VA = 0x088997C0
ORIGINAL_SPACE_ADVANCE = 0x26B5000D
ORIGINAL_DOUBLE_BYTE_ADVANCE = 0x2406000D

# The renderer only recognizes ASCII letters/digits (plus a few hard-coded
# marks) as one-byte glyphs.  Other ASCII punctuation falls through to the
# two-byte CP932 path, where it is paired with the following byte or NUL.
# Rebuild the classification as: byte < 0x80 => one-byte glyph, otherwise
# preserve the original 0x81-0x9F / 0xE0-0xFC lead-byte calculation.
ASCII_CLASSIFY_VA = 0x08899948
ASCII_BRANCH_VA = 0x0889994C
LEAD_LOWER_VA = 0x0889995C
LEAD_INVERT_VA = 0x08899960
LEAD_UPPER_VA = 0x08899964
ORIGINAL_ASCII_CLASSIFY = 0x50400004
ORIGINAL_ASCII_BRANCH = 0x28A20081
ORIGINAL_LEAD_LOWER = 0x38420001
ORIGINAL_LEAD_INVERT = 0x304600FF
ORIGINAL_LEAD_UPPER = 0x28A200A0

# The final 2,308 bytes of .rodata.sceNid are zero padding.  All import NID
# pointers end at 0x088D0DCB, immediately before this cave.  Reserve 2 KiB:
# enough for helpers plus a 216-entry halfword glyph-id cache.
CODE_CAVE_VA = 0x088D0DCC
CODE_CAVE_SIZE = 0x800

ATLAS_PAGE_STORE_VA = 0x088996F8
ORIGINAL_ATLAS_PAGE_STORE = 0xAC8341D4  # sw v1, 0x41D4(a0)
ATLAS_ALT_PAGE_STORE_VA = 0x08899C34
ORIGINAL_ATLAS_ALT_PAGE_STORE = 0xAC5E41D4  # sw fp, 0x41D4(v0)
ATLAS_RESET_VA = 0x0888E22C
ORIGINAL_ATLAS_RESET = 0xAC60421C  # sw zero, 0x421C(v1)
ATLAS_CAP_CHECK_VA = 0x08899738
ORIGINAL_ATLAS_CAP_CHECK = 0x286100D8  # slti at, v1, 216
GLYPH_ID_READY_VA = 0x088999E0
ORIGINAL_GLYPH_ID_READY = 0x0065F023  # subu fp, v1, a1
ATLAS_CAPACITY = 216
ATLAS_STATE_VA = CODE_CAVE_VA + 0x300
ATLAS_PAGE0_COUNT_VA = ATLAS_STATE_VA
ATLAS_PAGE1_COUNT_VA = ATLAS_STATE_VA + 4
ATLAS_PAGE0_CACHE_VA = ATLAS_STATE_VA + 8
ATLAS_PAGE1_CACHE_VA = ATLAS_PAGE0_CACHE_VA + ATLAS_CAPACITY * 2
ATLAS_CACHE_CLEAR_BYTES = ATLAS_CAPACITY * 2 * 2
ATLAS_CACHE_CLEAR_WORDS = ATLAS_CACHE_CLEAR_BYTES // 4

ATLAS_PAGE_RESET_HELPER_ASM = rf"""
    addiu $sp, $sp, -0x10
    sw    $v0, 0($sp)
    sw    $t0, 4($sp)
    sw    $t1, 8($sp)
    lw    $v0, 0x41D4($a0)
    beq   $v0, $v1, atlas_page_same
    nop
    beq   $v0, $zero, atlas_page_load_new
    nop
    lw    $t0, 0x4214($a0)
    lw    $t1, 0x421C($a0)
    beq   $v0, $t0, atlas_page_save_zero
    nop
    lui   $t0, 0x{(ATLAS_PAGE1_COUNT_VA >> 16) & 0xFFFF:04X}
    addiu $t0, $t0, 0x{ATLAS_PAGE1_COUNT_VA & 0xFFFF:04X}
    sw    $t1, 0($t0)
    b     atlas_page_save_done
    nop
atlas_page_save_zero:
    lui   $t0, 0x{(ATLAS_PAGE0_COUNT_VA >> 16) & 0xFFFF:04X}
    addiu $t0, $t0, 0x{ATLAS_PAGE0_COUNT_VA & 0xFFFF:04X}
    sw    $t1, 0($t0)
atlas_page_save_done:
atlas_page_load_new:
    lw    $t0, 0x4214($a0)
    beq   $v1, $t0, atlas_page_load_zero
    nop
    lui   $t0, 0x{(ATLAS_PAGE1_COUNT_VA >> 16) & 0xFFFF:04X}
    addiu $t0, $t0, 0x{ATLAS_PAGE1_COUNT_VA & 0xFFFF:04X}
    lw    $t1, 0($t0)
    b     atlas_page_load_done
    nop
atlas_page_load_zero:
    lui   $t0, 0x{(ATLAS_PAGE0_COUNT_VA >> 16) & 0xFFFF:04X}
    addiu $t0, $t0, 0x{ATLAS_PAGE0_COUNT_VA & 0xFFFF:04X}
    lw    $t1, 0($t0)
atlas_page_load_done:
    sw    $t1, 0x421C($a0)
atlas_page_same:
    sw    $v1, 0x41D4($a0)
    lw    $v0, 0($sp)
    lw    $t0, 4($sp)
    lw    $t1, 8($sp)
    addiu $sp, $sp, 0x10
    jr    $ra
    nop
"""


def _glyph_reuse_helper_asm() -> str:
    """Return an atlas cell for a glyph, reusing an existing cell when possible.

    The renderer's normal tail increments the global counter.  On a cache hit
    this helper decrements it once and jumps directly to vertex construction,
    so the tail increment restores the old value without allocating a cell.
    """
    return rf"""
    subu  $fp, $v1, $a1
    addiu $a0, $a0, 1
    lui   $t0, 0x08A5
    lw    $t1, 0x41D4($t0)
    lw    $t2, 0x4214($t0)
    beq   $t1, $t2, glyph_cache_page_zero
    nop
    lui   $t0, 0x{(ATLAS_PAGE1_CACHE_VA >> 16) & 0xFFFF:04X}
    addiu $t0, $t0, 0x{ATLAS_PAGE1_CACHE_VA & 0xFFFF:04X}
    b     glyph_cache_page_ready
    nop
glyph_cache_page_zero:
    lui   $t0, 0x{(ATLAS_PAGE0_CACHE_VA >> 16) & 0xFFFF:04X}
    addiu $t0, $t0, 0x{ATLAS_PAGE0_CACHE_VA & 0xFFFF:04X}
glyph_cache_page_ready:
    move  $t1, $zero
glyph_cache_scan:
    beq   $t1, $v1, glyph_cache_new
    nop
    sll   $t2, $t1, 1
    addu  $t2, $t0, $t2
    lhu   $t3, 0($t2)
    beq   $t3, $a0, glyph_cache_hit
    nop
    addiu $t1, $t1, 1
    b     glyph_cache_scan
    nop
glyph_cache_new:
    slti  $t2, $v1, 0xD8
    beq   $t2, $zero, glyph_cache_full
    nop
    sll   $t2, $v1, 1
    addu  $t2, $t0, $t2
    sh    $a0, 0($t2)
    addiu $a0, $a0, -1
    jr    $ra
    nop
glyph_cache_hit:
    move  $fp, $t1
    move  $s6, $zero
glyph_cache_div12:
    slti  $t2, $fp, 12
    bne   $t2, $zero, glyph_cache_cell_ready
    nop
    addiu $fp, $fp, -12
    addiu $s6, $s6, 1
    b     glyph_cache_div12
    nop
glyph_cache_cell_ready:
    lui   $t0, 0x08A5
    lw    $t1, 0x421C($t0)
    addiu $t1, $t1, -1
    sw    $t1, 0x421C($t0)
    lui   $ra, 0x0889
    ori   $ra, $ra, 0x9A48
    jr    $ra
    nop
glyph_cache_full:
    lui   $ra, 0x0889
    ori   $ra, $ra, 0x9B60
    jr    $ra
    nop
"""


def _atlas_reset_helper_asm(return_va: int) -> str:
    return rf"""
    addiu $sp, $sp, -0x10
    sw    $t0, 0($sp)
    sw    $t1, 4($sp)
    lui   $t0, 0x08A5
    sw    $zero, 0x421C($t0)
    sw    $zero, 0x41D4($t0)
    lui   $t0, 0x{(ATLAS_PAGE0_COUNT_VA >> 16) & 0xFFFF:04X}
    addiu $t0, $t0, 0x{ATLAS_PAGE0_COUNT_VA & 0xFFFF:04X}
    sw    $zero, 0($t0)
    sw    $zero, 4($t0)
    lui   $t0, 0x{(ATLAS_PAGE0_CACHE_VA >> 16) & 0xFFFF:04X}
    addiu $t0, $t0, 0x{ATLAS_PAGE0_CACHE_VA & 0xFFFF:04X}
    addiu $t1, $zero, {ATLAS_CACHE_CLEAR_WORDS}
atlas_cache_clear_loop:
    sw    $zero, 0($t0)
    addiu $t0, $t0, 4
    addiu $t1, $t1, -1
    bne   $t1, $zero, atlas_cache_clear_loop
    nop
    lui   $at, 0x{(return_va >> 16) & 0xFFFF:04X}
    ori   $at, $at, 0x{return_va & 0xFFFF:04X}
    lw    $t0, 0($sp)
    lw    $t1, 4($sp)
    addiu $sp, $sp, 0x10
    jr    $at
    nop
"""


def _atlas_alt_page_wrapper_asm(page_helper_va: int) -> str:
    """Adapt the alternate renderer's v0/fp page-store registers."""
    return rf"""
    addiu $sp, $sp, -8
    sw    $ra, 0($sp)
    move  $a0, $v0
    move  $v1, $fp
    jal   0x{page_helper_va:08X}
    nop
    lw    $ra, 0($sp)
    addiu $sp, $sp, 8
    jr    $ra
    nop
"""

COUNT_HELPER_ASM = r"""
    move  $v0, $zero
count_loop:
    lbu   $v1, 0($a0)
    beq   $v1, $zero, count_done
    addiu $a0, $a0, 1
    addiu $t1, $zero, 0x20
    beq   $v1, $t1, count_loop
    nop
    sltiu $t0, $v1, 0x81
    bne   $t0, $zero, count_one
    nop
    sltiu $t0, $v1, 0xA0
    bne   $t0, $zero, count_lead
    nop
    sltiu $t0, $v1, 0xE0
    bne   $t0, $zero, count_one
    nop
    sltiu $t0, $v1, 0xFD
    beq   $t0, $zero, count_one
    nop
count_lead:
    addiu $a0, $a0, 1
count_one:
    addiu $v0, $v0, 1
    b     count_loop
    nop
count_done:
    jr    $ra
    nop
"""

# The helper must not touch anything past the bytes it writes.  An earlier
# revision blank-filled 41 bytes at the destination before copying; on real
# hardware that wiped memory next to the reveal buffer and the firmware save
# dialog closed the moment it was opened (PPSSPP tolerated it).  The original
# game code only wrote the copied bytes plus one terminator, so do the same:
# copy_done stores the NUL at exactly the end of what was copied.
COPY_HELPER_ASM = r"""
    move  $v0, $a0
copy_loop:
    beq   $a2, $zero, copy_done
    nop
    lbu   $v1, 0($a1)
    beq   $v1, $zero, copy_done
    nop
    sb    $v1, 0($a0)
    addiu $a0, $a0, 1
    addiu $a1, $a1, 1
    addiu $t1, $zero, 0x20
    beq   $v1, $t1, copy_loop
    nop
    sltiu $t0, $v1, 0x81
    bne   $t0, $zero, copy_one
    nop
    sltiu $t0, $v1, 0xA0
    bne   $t0, $zero, copy_lead
    nop
    sltiu $t0, $v1, 0xE0
    bne   $t0, $zero, copy_one
    nop
    sltiu $t0, $v1, 0xFD
    beq   $t0, $zero, copy_one
    nop
copy_lead:
    lbu   $t1, 0($a1)
    beq   $t1, $zero, copy_done
    nop
    sb    $t1, 0($a0)
    addiu $a0, $a0, 1
    addiu $a1, $a1, 1
copy_one:
    addiu $a2, $a2, -1
    b     copy_loop
    nop
copy_done:
    sb    $zero, 0($a0)
    jr    $ra
    nop
"""


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


def _jal(target: int) -> int:
    return 0x0C000000 | ((target >> 2) & 0x03FFFFFF)


def _j(target: int) -> int:
    return 0x08000000 | ((target >> 2) & 0x03FFFFFF)


def _assemble(source: str, address: int) -> bytes:
    assembler = Ks(KS_ARCH_MIPS, KS_MODE_MIPS32 | KS_MODE_LITTLE_ENDIAN)
    encoded, _ = assembler.asm(source, addr=address, as_bytes=True)
    return bytes(encoded)


def _read_extent(path: Path, offset: int, size: int) -> bytes:
    with path.open("rb") as stream:
        stream.seek(offset)
        return stream.read(size)


def patch_executable(
    source: bytes, space_advance: int, double_byte_advance: int
) -> tuple[bytes, dict[str, object]]:
    if source[:4] != b"\x7fELF":
        raise ValueError("executable is not a plaintext ELF")
    if not 0 <= space_advance <= 13:
        raise ValueError("space advance must be between 0 and 13 pixels")
    if not 1 <= double_byte_advance <= 13:
        raise ValueError("double-byte advance must be between 1 and 13 pixels")

    count_code = _assemble(COUNT_HELPER_ASM, CODE_CAVE_VA)
    copy_va = CODE_CAVE_VA + len(count_code)
    copy_code = _assemble(COPY_HELPER_ASM, copy_va)
    helper_code = count_code + copy_code
    if len(helper_code) > CODE_CAVE_SIZE:
        raise ValueError("typewriter helpers exceed the audited code cave")

    cave_offset = _offset(CODE_CAVE_VA)
    if any(source[cave_offset:cave_offset + CODE_CAVE_SIZE]):
        raise ValueError("audited code cave is no longer zero-filled")

    output = bytearray(source)
    patches = (
        (COUNT_CALL_VA, ORIGINAL_COUNT_CALL, _jal(CODE_CAVE_VA), "logical CP932 character count"),
        (COUNT_DIVIDE_VA, ORIGINAL_COUNT_DIVIDE, 0x00401821, "remove strlen / 2"),
        (COPY_CALL_VA, ORIGINAL_COPY_CALL, _jal(copy_va), "copy complete CP932 characters"),
        (COPY_MULTIPLY_VA, ORIGINAL_COPY_MULTIPLY, 0x00403021, "pass character count, not byte count"),
        (
            COPY_TRAILING_NUL_VA,
            ORIGINAL_COPY_TRAILING_NUL,
            0x00000000,
            "disable obsolete count-times-two terminator",
        ),
        (
            SPACE_ADVANCE_VA,
            ORIGINAL_SPACE_ADVANCE,
            (ORIGINAL_SPACE_ADVANCE & 0xFFFF0000) | space_advance,
            "ASCII space advance",
        ),
        (
            DOUBLE_BYTE_ADVANCE_VA,
            ORIGINAL_DOUBLE_BYTE_ADVANCE,
            (ORIGINAL_DOUBLE_BYTE_ADVANCE & 0xFFFF0000) | double_byte_advance,
            "default glyph advance",
        ),
        (
            ASCII_CLASSIFY_VA,
            ORIGINAL_ASCII_CLASSIFY,
            0x2CA20080,
            "classify all ASCII bytes as one-byte glyphs",
        ),
        (
            ASCII_BRANCH_VA,
            ORIGINAL_ASCII_BRANCH,
            0x10400003,
            "branch non-ASCII bytes to CP932 lead classification",
        ),
        (
            LEAD_LOWER_VA,
            ORIGINAL_LEAD_LOWER,
            0x2CA20081,
            "recompute CP932 lead lower bound",
        ),
        (
            LEAD_INVERT_VA,
            ORIGINAL_LEAD_INVERT,
            0x38420001,
            "invert CP932 lead lower-bound result",
        ),
        (
            LEAD_UPPER_VA,
            ORIGINAL_LEAD_UPPER,
            0x2CA600A0,
            "compute CP932 lead upper bound",
        ),
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
    output[cave_offset:cave_offset + len(helper_code)] = helper_code

    return bytes(output), {
        "instructions": rows,
        "code_cave": {
            "virtual_address": f"0x{CODE_CAVE_VA:08X}",
            "file_offset": f"0x{cave_offset:X}",
            "reserved_bytes": CODE_CAVE_SIZE,
            "used_bytes": len(helper_code),
            "count_helper_bytes": len(count_code),
            "copy_helper_virtual_address": f"0x{copy_va:08X}",
            "copy_helper_bytes": len(copy_code),
            "sha256": _sha256(helper_code),
        },
        "spacing": {
            "space_advance_px": space_advance,
            "default_glyph_advance_px": double_byte_advance,
        },
        "typewriter_units": {
            "unit": "rendered CP932 glyph",
            "ascii_space_consumes_unit": False,
            "ascii_space_is_preserved_in_prefix": True,
        },
    }


def patch_renderer_only(
    source: bytes, space_advance: int, double_byte_advance: int
) -> tuple[bytes, dict[str, object]]:
    """Patch only byte classification/advance, leaving the reveal loop native.

    This is also a diagnostic isolation mode: the broad three-line reveal hook
    is deliberately omitted so menu refreshes can be tested independently.
    """
    if source[:4] != b"\x7fELF":
        raise ValueError("executable is not a plaintext ELF")
    if not 0 <= space_advance <= 13:
        raise ValueError("space advance must be between 0 and 13 pixels")
    if not 1 <= double_byte_advance <= 13:
        raise ValueError("double-byte advance must be between 1 and 13 pixels")

    atlas_helper = _assemble(ATLAS_PAGE_RESET_HELPER_ASM, CODE_CAVE_VA)
    glyph_helper_va = (CODE_CAVE_VA + len(atlas_helper) + 3) & ~3
    glyph_helper = _assemble(_glyph_reuse_helper_asm(), glyph_helper_va)
    reset_helper_va = (glyph_helper_va + len(glyph_helper) + 3) & ~3
    reset_helper = _assemble(
        _atlas_reset_helper_asm(ATLAS_RESET_VA + 8), reset_helper_va
    )
    alt_page_wrapper_va = (reset_helper_va + len(reset_helper) + 3) & ~3
    alt_page_wrapper = _assemble(
        _atlas_alt_page_wrapper_asm(CODE_CAVE_VA), alt_page_wrapper_va
    )
    helper_end_va = alt_page_wrapper_va + len(alt_page_wrapper)
    if helper_end_va > ATLAS_STATE_VA:
        raise ValueError("atlas helpers overlap the fixed per-page state area")
    glyph_cache_bytes = ATLAS_CAPACITY * 2 * 2
    used_cave_bytes = (
        ATLAS_PAGE1_CACHE_VA + ATLAS_CAPACITY * 2 - CODE_CAVE_VA
    )
    if used_cave_bytes > CODE_CAVE_SIZE:
        raise ValueError("atlas helpers and glyph cache exceed the audited code cave")
    cave_offset = _offset(CODE_CAVE_VA)
    if any(source[cave_offset:cave_offset + CODE_CAVE_SIZE]):
        raise ValueError("audited code cave is no longer zero-filled")

    output = bytearray(source)
    patches = (
        (
            ATLAS_PAGE_STORE_VA,
            ORIGINAL_ATLAS_PAGE_STORE,
            _jal(CODE_CAVE_VA),
            "save and restore the independent glyph counter for each atlas page",
        ),
        (
            ATLAS_ALT_PAGE_STORE_VA,
            ORIGINAL_ATLAS_ALT_PAGE_STORE,
            _jal(alt_page_wrapper_va),
            "synchronize atlas pages used by the alternate UI renderer",
        ),
        (
            ATLAS_RESET_VA,
            ORIGINAL_ATLAS_RESET,
            _j(reset_helper_va),
            "reset both atlas-page counters at the native reset point",
        ),
        (
            ATLAS_CAP_CHECK_VA,
            ORIGINAL_ATLAS_CAP_CHECK,
            0x286100D9,
            "allow cache lookup when all 216 atlas cells are allocated",
        ),
        (
            GLYPH_ID_READY_VA,
            ORIGINAL_GLYPH_ID_READY,
            _jal(glyph_helper_va),
            "reuse an existing atlas cell for duplicate glyphs",
        ),
        (
            SPACE_ADVANCE_VA,
            ORIGINAL_SPACE_ADVANCE,
            (ORIGINAL_SPACE_ADVANCE & 0xFFFF0000) | space_advance,
            "ASCII space advance",
        ),
        (
            DOUBLE_BYTE_ADVANCE_VA,
            ORIGINAL_DOUBLE_BYTE_ADVANCE,
            (ORIGINAL_DOUBLE_BYTE_ADVANCE & 0xFFFF0000) | double_byte_advance,
            "default glyph advance",
        ),
        (
            ASCII_CLASSIFY_VA,
            ORIGINAL_ASCII_CLASSIFY,
            0x2CA20080,
            "classify all ASCII bytes as one-byte glyphs",
        ),
        (
            ASCII_BRANCH_VA,
            ORIGINAL_ASCII_BRANCH,
            0x10400003,
            "branch non-ASCII bytes to CP932 lead classification",
        ),
        (
            LEAD_LOWER_VA,
            ORIGINAL_LEAD_LOWER,
            0x2CA20081,
            "recompute CP932 lead lower bound",
        ),
        (
            LEAD_INVERT_VA,
            ORIGINAL_LEAD_INVERT,
            0x38420001,
            "invert CP932 lead lower-bound result",
        ),
        (
            LEAD_UPPER_VA,
            ORIGINAL_LEAD_UPPER,
            0x2CA600A0,
            "compute CP932 lead upper bound",
        ),
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

    glyph_helper_offset = _offset(glyph_helper_va)
    output[cave_offset:cave_offset + len(atlas_helper)] = atlas_helper
    output[
        glyph_helper_offset:glyph_helper_offset + len(glyph_helper)
    ] = glyph_helper
    reset_helper_offset = _offset(reset_helper_va)
    output[
        reset_helper_offset:reset_helper_offset + len(reset_helper)
    ] = reset_helper
    alt_page_wrapper_offset = _offset(alt_page_wrapper_va)
    output[
        alt_page_wrapper_offset:alt_page_wrapper_offset + len(alt_page_wrapper)
    ] = alt_page_wrapper

    return bytes(output), {
        "mode": "renderer_only_with_glyph_cell_reuse",
        "instructions": rows,
        "atlas_page_sync": {
            "installed": True,
            "page_pointer_global": "0x08A541D4",
            "glyph_counter_global": "0x08A5421C",
            "capacity_per_page": 216,
            "helper_virtual_address": f"0x{CODE_CAVE_VA:08X}",
            "helper_bytes": len(atlas_helper),
            "helper_sha256": _sha256(atlas_helper),
            "preserved_registers": ["v0", "t0", "t1"],
            "primary_page_store_hook": f"0x{ATLAS_PAGE_STORE_VA:08X}",
            "alternate_page_store_hook": f"0x{ATLAS_ALT_PAGE_STORE_VA:08X}",
            "alternate_wrapper_virtual_address": f"0x{alt_page_wrapper_va:08X}",
            "alternate_wrapper_bytes": len(alt_page_wrapper),
            "alternate_wrapper_sha256": _sha256(alt_page_wrapper),
            "page0_counter_virtual_address": f"0x{ATLAS_PAGE0_COUNT_VA:08X}",
            "page1_counter_virtual_address": f"0x{ATLAS_PAGE1_COUNT_VA:08X}",
            "native_reset_hook": f"0x{ATLAS_RESET_VA:08X}",
            "reset_helper_virtual_address": f"0x{reset_helper_va:08X}",
            "reset_helper_bytes": len(reset_helper),
            "cache_clear_bytes": ATLAS_CACHE_CLEAR_BYTES,
            "cache_clear_words": ATLAS_CACHE_CLEAR_WORDS,
            "reset_preserved_registers": ["t0", "t1"],
        },
        "glyph_cell_reuse": {
            "installed": True,
            "capacity": ATLAS_CAPACITY,
            "cache_entry": "glyph_id_plus_one_halfword",
            "helper_virtual_address": f"0x{glyph_helper_va:08X}",
            "helper_bytes": len(glyph_helper),
            "page0_cache_virtual_address": f"0x{ATLAS_PAGE0_CACHE_VA:08X}",
            "page1_cache_virtual_address": f"0x{ATLAS_PAGE1_CACHE_VA:08X}",
            "cache_bytes": glyph_cache_bytes,
            "code_cave_used_bytes": used_cave_bytes,
            "helper_sha256": _sha256(glyph_helper),
        },
        "spacing": {
            "space_advance_px": space_advance,
            "default_glyph_advance_px": double_byte_advance,
        },
        "typewriter_hook": {
            "installed": False,
            "reason": "keep menu refresh independent from the broad three-line reveal hook",
        },
    }


def patch_renderer_without_glyph_cache(
    source: bytes, space_advance: int, double_byte_advance: int
) -> tuple[bytes, dict[str, object]]:
    """Patch mixed-width classification and spacing, leaving atlas logic native.

    This is a runtime diagnostic control.  It deliberately omits the custom
    per-page counters, glyph-ID cache, reset helper, and capacity extension so
    a menu can be tested with the exact same translated strings while the
    suspected glyph-cell reuse path is completely absent.
    """
    if source[:4] != b"\x7fELF":
        raise ValueError("executable is not a plaintext ELF")
    if not 0 <= space_advance <= 13:
        raise ValueError("space advance must be between 0 and 13 pixels")
    if not 1 <= double_byte_advance <= 13:
        raise ValueError("double-byte advance must be between 1 and 13 pixels")

    patches = (
        (
            SPACE_ADVANCE_VA,
            ORIGINAL_SPACE_ADVANCE,
            (ORIGINAL_SPACE_ADVANCE & 0xFFFF0000) | space_advance,
            "ASCII space advance",
        ),
        (
            DOUBLE_BYTE_ADVANCE_VA,
            ORIGINAL_DOUBLE_BYTE_ADVANCE,
            (ORIGINAL_DOUBLE_BYTE_ADVANCE & 0xFFFF0000) | double_byte_advance,
            "default glyph advance",
        ),
        (
            ASCII_CLASSIFY_VA,
            ORIGINAL_ASCII_CLASSIFY,
            0x2CA20080,
            "classify all ASCII bytes as one-byte glyphs",
        ),
        (
            ASCII_BRANCH_VA,
            ORIGINAL_ASCII_BRANCH,
            0x10400003,
            "branch non-ASCII bytes to CP932 lead classification",
        ),
        (
            LEAD_LOWER_VA,
            ORIGINAL_LEAD_LOWER,
            0x2CA20081,
            "recompute CP932 lead lower bound",
        ),
        (
            LEAD_INVERT_VA,
            ORIGINAL_LEAD_INVERT,
            0x38420001,
            "invert CP932 lead lower-bound result",
        ),
        (
            LEAD_UPPER_VA,
            ORIGINAL_LEAD_UPPER,
            0x2CA600A0,
            "compute CP932 lead upper bound",
        ),
    )
    output = bytearray(source)
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

    cave_offset = _offset(CODE_CAVE_VA)
    if output[cave_offset:cave_offset + CODE_CAVE_SIZE] != bytes(CODE_CAVE_SIZE):
        raise ValueError("native renderer control unexpectedly modifies the code cave")

    return bytes(output), {
        "mode": "renderer_only_native_atlas_control",
        "instructions": rows,
        "atlas_page_sync": {
            "installed": False,
            "reason": "runtime control leaves the native atlas page logic intact",
        },
        "glyph_cell_reuse": {
            "installed": False,
            "reason": "runtime control isolates the custom glyph-ID cache",
        },
        "spacing": {
            "space_advance_px": space_advance,
            "default_glyph_advance_px": double_byte_advance,
        },
        "typewriter_hook": {
            "installed": False,
            "reason": "keep the native three-line reveal loop",
        },
    }


def build(
    baseline_iso: Path,
    output_iso: Path,
    report_path: Path,
    space_advance: int,
    double_byte_advance: int,
) -> dict[str, object]:
    boot_record = locate_iso9660_path(baseline_iso, BOOT_PATH)
    eboot_record = locate_iso9660_path(baseline_iso, EBOOT_PATH)
    boot_source = _read_extent(baseline_iso, boot_record.offset, boot_record.size)
    eboot_source = _read_extent(baseline_iso, eboot_record.offset, eboot_record.size)
    boot_output, patch_report = patch_executable(
        boot_source, space_advance, double_byte_advance
    )
    eboot_output, eboot_patch_report = patch_executable(
        eboot_source, space_advance, double_byte_advance
    )
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
        "gate_id": "DIALOG-MIXED-CP932-TYPEWRITER-002",
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
                "ASCII comma remains visible",
                "no transient kanji or malformed Hangul during typewriter reveal",
                "Korean glyph tracking and word-space width are visibly reduced",
                "each 0x29-byte temporary line buffer is cleared before prefix copy",
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
    parser.add_argument("--space-advance", type=int, default=6)
    parser.add_argument("--double-byte-advance", type=int, default=9)
    args = parser.parse_args()
    report = build(
        args.baseline_iso,
        args.output_iso,
        args.report,
        args.space_advance,
        args.double_byte_advance,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
