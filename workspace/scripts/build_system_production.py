#!/usr/bin/env python3
"""Repack SYSTEM.DAT around an expanded production start.lzs."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from decompress_nis_lzs import decompress
from inspect_nispack import ENTRY, SIGNATURE, read_entries


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def align(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def build(profile_path: Path, archive_path: Path, replacement_path: Path, expected_start_path: Path, output_dir: Path) -> dict[str, object]:
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    expected = profile["containers"]["SYSTEM.DAT"]
    source = archive_path.read_bytes()
    replacement = replacement_path.read_bytes()
    if len(source) != int(expected["size"]) or sha256(source) != expected["sha256"]:
        raise ValueError("SYSTEM.DAT does not match the supported revision")
    entries = read_entries(archive_path)
    if len(entries) != int(expected["entry_count"]):
        raise ValueError("SYSTEM.DAT entry count changed")
    target_name = expected["replacement_name"]
    targets = [entry for entry in entries if entry.name == target_name]
    if len(targets) != 1:
        raise ValueError("SYSTEM.DAT production target is not unique")
    target = targets[0]
    original_target = source[target.offset:target.offset + target.size]
    if sha256(original_target) != expected["replacement_source_sha256"]:
        raise ValueError("original start.lzs hash changed")
    restored, extension = decompress(replacement)
    expected_start = expected_start_path.read_bytes()
    if extension != "dat" or restored != expected_start:
        raise ValueError("production start.lzs does not restore the expected start.dat")

    ordered = sorted(entries, key=lambda entry: entry.offset)
    table_end = len(SIGNATURE) + 4 + len(entries) * ENTRY.size
    previous_end = table_end
    for entry in ordered:
        gap = source[previous_end:entry.offset]
        if any(gap):
            raise ValueError(f"non-zero alignment gap before {entry.name}")
        previous_end = entry.offset + entry.size

    alignment = int(expected["alignment"])
    target_position = ordered.index(target)
    next_offset = (
        ordered[target_position + 1].offset
        if target_position + 1 < len(ordered)
        else len(source)
    )
    in_place = len(replacement) <= next_offset - target.offset
    if in_place:
        output_buffer = bytearray(source)
        output_buffer[target.offset:next_offset] = replacement + bytes(
            next_offset - target.offset - len(replacement)
        )
        record = len(SIGNATURE) + 4 + target.index * ENTRY.size
        struct.pack_into("I", output_buffer, record + 36, len(replacement))
        output = bytes(output_buffer)
        output_offsets = {
            entry.index: (entry.offset, len(replacement) if entry.index == target.index else entry.size)
            for entry in entries
        }
        moved_entries = 0
    else:
        header = bytearray(source[:ordered[0].offset])
        cursor = ordered[0].offset
        chunks: list[bytes] = []
        output_offsets: dict[int, tuple[int, int]] = {}
        moved_entries = 0
        for position, entry in enumerate(ordered):
            if cursor % alignment:
                padding = align(cursor, alignment) - cursor
                chunks.append(bytes(padding))
                cursor += padding
            payload = replacement if entry.index == target.index else source[entry.offset:entry.offset + entry.size]
            output_offsets[entry.index] = (cursor, len(payload))
            if cursor != entry.offset:
                moved_entries += 1
            chunks.append(payload)
            cursor += len(payload)
            if position + 1 < len(ordered):
                padding = align(cursor, alignment) - cursor
                chunks.append(bytes(padding))
                cursor += padding

        for entry in entries:
            offset, size = output_offsets[entry.index]
            record = len(SIGNATURE) + 4 + entry.index * ENTRY.size
            struct.pack_into("<II", header, record + 32, offset, size)
        output = bytes(header) + b"".join(chunks)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "SYSTEM.DAT"
    output_path.write_bytes(output)
    output_entries = read_entries(output_path)
    for before, after in zip(entries, output_entries):
        if (before.name, before.unknown) != (after.name, after.unknown):
            raise ValueError(f"NISPACK metadata changed: {before.name}")
        expected_payload = replacement if before.index == target.index else source[before.offset:before.offset + before.size]
        if output[after.offset:after.offset + after.size] != expected_payload:
            raise ValueError(f"NISPACK payload changed: {before.name}")

    report = {
        "schema_version": 1,
        "gate_id": "DEMO00-PRODUCTION-SYSTEM-001",
        "status": (
            "PASS: in-place SYSTEM.DAT replacement and round-trip extraction"
            if in_place else
            "PASS: variable-size SYSTEM.DAT repacked and round-trip extracted"
        ),
        "input": {"size": len(source), "sha256": sha256(source)},
        "replacement": {
            "entry_name": target_name,
            "original_size": target.size,
            "replacement_size": len(replacement),
            "size_delta": len(replacement) - target.size,
            "sha256": sha256(replacement),
            "restored_start_dat_sha256": sha256(restored),
        },
        "index": {
            "alignment": alignment,
            "in_place_fixed_extent": in_place,
            "moved_entries": moved_entries,
            "names_and_unknown_fields_preserved": True,
            "all_non_target_payloads_byte_identical": True,
        },
        "output": {
            "path": output_path.as_posix(),
            "size": len(output),
            "size_delta": len(output) - len(source),
            "sha256": sha256(output),
            "roundtrip_extraction": True,
        },
        "runtime_gate": {"status": "PENDING", "reason": "ISO extent relocation and PPSSPP remain"},
    }
    (output_dir / "system_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    parser.add_argument("archive", type=Path)
    parser.add_argument("replacement", type=Path)
    parser.add_argument("expected_start", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    report = build(args.profile, args.archive, args.replacement, args.expected_start, args.output_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
