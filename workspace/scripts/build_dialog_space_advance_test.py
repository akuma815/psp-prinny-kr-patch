#!/usr/bin/env python3
"""Patch dialogue spacing instructions in BOOT/EBOOT and build a test ISO."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import struct
from pathlib import Path

from build_iso_poc import locate_iso9660_path


ELF_BASE = 0x08804000
ELF_FILE_OFFSET = 0x54
SPACE_ADVANCE_VA = 0x08899760
DOUBLE_BYTE_ADVANCE_VA = 0x088997C0
ORIGINAL_SPACE_WORD = 0x26B5000D  # addiu s5, s5, 13
ORIGINAL_DOUBLE_BYTE_WORD = 0x2406000D  # addiu a2, zero, 13
BOOT_PATH = "/PSP_GAME/SYSDIR/BOOT.BIN;1"
EBOOT_PATH = "/PSP_GAME/SYSDIR/EBOOT.BIN;1"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def instruction_offset(virtual_address: int = SPACE_ADVANCE_VA) -> int:
    return ELF_FILE_OFFSET + virtual_address - ELF_BASE


def patch_executable(
    data: bytes, space_advance: int, double_byte_advance: int
) -> tuple[bytes, dict[str, object]]:
    if not 1 <= space_advance <= 12:
        raise ValueError("space advance must be between 1 and 12 pixels")
    if not 1 <= double_byte_advance <= 12:
        raise ValueError("double-byte advance must be between 1 and 12 pixels")
    if data[:4] != b"\x7fELF":
        raise ValueError("executable is not a plaintext ELF")
    output = bytearray(data)
    patches = []
    for label, virtual_address, original_word, advance in (
        ("ASCII space", SPACE_ADVANCE_VA, ORIGINAL_SPACE_WORD, space_advance),
        (
            "double-byte character",
            DOUBLE_BYTE_ADVANCE_VA,
            ORIGINAL_DOUBLE_BYTE_WORD,
            double_byte_advance,
        ),
    ):
        offset = instruction_offset(virtual_address)
        if len(data) < offset + 4:
            raise ValueError(f"executable is truncated before the {label} instruction")
        source_word, = struct.unpack_from("<I", data, offset)
        if source_word != original_word:
            raise ValueError(
                f"dialogue {label} instruction mismatch: expected 0x{original_word:08X}, "
                f"got 0x{source_word:08X}"
            )
        patched_word = (original_word & 0xFFFF0000) | advance
        struct.pack_into("<I", output, offset, patched_word)
        patches.append(
            {
                "kind": label,
                "virtual_address": f"0x{virtual_address:08X}",
                "file_offset": f"0x{offset:X}",
                "original_instruction": f"0x{source_word:08X}",
                "patched_instruction": f"0x{patched_word:08X}",
                "original_advance_px": 13,
                "patched_advance_px": advance,
            }
        )
    changed = [index for index, pair in enumerate(zip(data, output)) if pair[0] != pair[1]]
    expected_changed = [
        instruction_offset(SPACE_ADVANCE_VA),
        instruction_offset(DOUBLE_BYTE_ADVANCE_VA),
    ]
    if changed != expected_changed:
        raise ValueError("renderer patch changed bytes outside the immediate value")
    return bytes(output), {
        "instructions": patches,
        "changed_byte_offsets": [f"0x{value:X}" for value in changed],
    }


def _read_extent(path: Path, offset: int, size: int) -> bytes:
    with path.open("rb") as stream:
        stream.seek(offset)
        return stream.read(size)


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
        raise ValueError("BOOT and EBOOT renderer fingerprints differ")

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

    if output_iso.stat().st_size != baseline_iso.stat().st_size:
        raise ValueError("output ISO size changed")
    if locate_iso9660_path(output_iso, BOOT_PATH) != boot_record:
        raise ValueError("BOOT ISO9660 directory record changed")
    if locate_iso9660_path(output_iso, EBOOT_PATH) != eboot_record:
        raise ValueError("EBOOT ISO9660 directory record changed")
    if _read_extent(output_iso, boot_record.offset, boot_record.size) != boot_output:
        raise ValueError("patched BOOT did not round-trip from the ISO")
    if _read_extent(output_iso, eboot_record.offset, eboot_record.size) != eboot_output:
        raise ValueError("patched EBOOT did not round-trip from the ISO")

    report = {
        "schema_version": 1,
        "gate_id": "DIALOG-TRACKING-ADVANCE-001",
        "status": "PASS",
        "baseline": {
            "path": baseline_iso.as_posix(),
            "size": baseline_iso.stat().st_size,
            "sha256": sha256_file(baseline_iso),
        },
        "patch": patch_report,
        "extents": [
            {
                "path": BOOT_PATH,
                "offset": f"0x{boot_record.offset:X}",
                "size": boot_record.size,
                "source_sha256": sha256_bytes(boot_source),
                "output_sha256": sha256_bytes(boot_output),
            },
            {
                "path": EBOOT_PATH,
                "offset": f"0x{eboot_record.offset:X}",
                "size": eboot_record.size,
                "source_sha256": sha256_bytes(eboot_source),
                "output_sha256": sha256_bytes(eboot_output),
            },
        ],
        "output": {
            "path": output_iso.as_posix(),
            "size": output_iso.stat().st_size,
            "sha256": sha256_file(output_iso),
            "same_size_as_baseline": output_iso.stat().st_size == baseline_iso.stat().st_size,
            "changed_bytes": 4,
        },
        "scope": {
            "affected_characters": [
                "ASCII space 0x20 in the confirmed dialogue renderer",
                "double-byte characters using the renderer default-width path",
            ],
            "temporary_risk": (
                "The double-byte default also covers Japanese glyphs. "
                "This visual test precedes a Korean-lead-byte-only hook."
            ),
            "unchanged": [
                "glyph bitmaps",
                "line assignments",
                "ISO9660 directory records",
            ],
        },
        "runtime_gate": {
            "status": "PENDING",
            "reason": "PPSSPP visual confirmation of Korean glyph tracking remains",
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
