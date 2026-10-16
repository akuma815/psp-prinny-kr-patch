#!/usr/bin/env python3
"""Replace start.lzs inside a verified SYSTEM.DAT without moving other entries."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from decompress_nis_lzs import decompress
from inspect_nispack import ENTRY, read_entries


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build(
    profile_path: Path,
    archive_path: Path,
    replacement_path: Path,
    output_dir: Path,
) -> dict[str, object]:
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    poc = profile.get("multi_poc", profile.get("poc"))
    if not poc:
        raise ValueError("font profile has no poc or multi_poc section")
    expected = poc["system_dat"]
    archive = archive_path.read_bytes()
    replacement = replacement_path.read_bytes()

    if sha256(archive) != expected["archive_sha256"]:
        raise ValueError("SYSTEM.DAT hash does not match the font PoC profile")
    if sha256(replacement) != expected["replacement_sha256"]:
        raise ValueError("replacement start.lzs hash does not match the font PoC profile")

    entries = read_entries(archive_path)
    matches = [entry for entry in entries if entry.name == expected["entry_name"]]
    if len(matches) != 1:
        raise ValueError("SYSTEM.DAT must contain exactly one configured target entry")
    entry = matches[0]
    configured = (
        int(expected["entry_offset"], 0),
        int(expected["entry_size"]),
        int(expected["entry_unknown"], 0),
    )
    if (entry.offset, entry.size, entry.unknown) != configured:
        raise ValueError("SYSTEM.DAT target entry metadata changed")

    original_entry = archive[entry.offset:entry.offset + entry.size]
    if sha256(original_entry) != expected["entry_sha256"]:
        raise ValueError("original start.lzs hash changed")
    next_offset = int(expected["next_entry_offset"], 0)
    ordered = sorted(entries, key=lambda item: item.offset)
    position = ordered.index(entry)
    observed_next = ordered[position + 1].offset if position + 1 < len(ordered) else len(archive)
    if observed_next != next_offset:
        raise ValueError("next NISPACK entry boundary changed")
    if len(replacement) > next_offset - entry.offset:
        raise ValueError("replacement start.lzs does not fit the existing entry extent")

    original_padding = archive[entry.offset + entry.size:next_offset]
    if any(original_padding):
        raise ValueError("target entry padding is not all zero")
    restored, extension = decompress(replacement)
    if extension != "dat" or sha256(restored) != expected["replacement_start_dat_sha256"]:
        raise ValueError("replacement start.lzs does not restore the configured PoC start.dat")

    output = bytearray(archive)
    output[entry.offset:entry.offset + len(replacement)] = replacement
    output[entry.offset + len(replacement):next_offset] = bytes(
        next_offset - entry.offset - len(replacement)
    )
    record_start = len(b"NISPACK\0\0\0\0\0") + 4 + entry.index * ENTRY.size
    size_field_start = record_start + 32 + 4
    output[size_field_start:size_field_start + 4] = struct.pack("<I", len(replacement))
    output = bytes(output)
    if len(output) != len(archive):
        raise ValueError("SYSTEM.DAT size changed")

    allowed = [(size_field_start, size_field_start + 4), (entry.offset, next_offset)]
    illegal = [
        index
        for index, (before, after) in enumerate(zip(archive, output))
        if before != after and not any(start <= index < end for start, end in allowed)
    ]
    if illegal:
        raise ValueError(f"SYSTEM.DAT changed outside declared ownership at 0x{illegal[0]:X}")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "SYSTEM.DAT"
    output_path.write_bytes(output)
    output_entries = read_entries(output_path)
    output_target = next(item for item in output_entries if item.name == entry.name)
    if (output_target.offset, output_target.size, output_target.unknown) != (
        entry.offset,
        len(replacement),
        entry.unknown,
    ):
        raise ValueError("written target metadata failed re-read verification")
    if output[entry.offset:entry.offset + len(replacement)] != replacement:
        raise ValueError("written start.lzs differs from replacement")
    for before, after in zip(entries, output_entries):
        if before.index != entry.index and before != after:
            raise ValueError(f"non-target entry metadata changed: {before.name}")
        if before.index != entry.index:
            start, end = before.offset, before.offset + before.size
            if archive[start:end] != output[start:end]:
                raise ValueError(f"non-target entry data changed: {before.name}")

    changed_bytes = sum(before != after for before, after in zip(archive, output))
    report = {
        "schema_version": 1,
        "gate_id": "POC-SYSTEM-INJECT-001",
        "status": "PASS: in-place NISPACK start.lzs replacement",
        "input": {
            "path": archive_path.as_posix(),
            "size": len(archive),
            "sha256": sha256(archive),
        },
        "replacement": {
            "path": replacement_path.as_posix(),
            "entry_name": entry.name,
            "offset": f"0x{entry.offset:X}",
            "original_size": entry.size,
            "new_size": len(replacement),
            "size_delta": len(replacement) - entry.size,
            "sha256": sha256(replacement),
            "restored_start_dat_sha256": sha256(restored),
        },
        "extent": {
            "end_exclusive": f"0x{next_offset:X}",
            "original_padding": len(original_padding),
            "remaining_padding": next_offset - entry.offset - len(replacement),
        },
        "output": {
            "path": output_path.as_posix(),
            "size": len(output),
            "sha256": sha256(output),
            "same_size_as_input": len(output) == len(archive),
            "changed_bytes": changed_bytes,
        },
        "expected_write": {
            "owners": ["start.lzs size field", "start.lzs fixed allocation extent"],
            "size_field": f"0x{size_field_start:X}..0x{size_field_start + 4:X}",
            "data_extent": f"0x{entry.offset:X}..0x{next_offset:X}",
            "other_entry_offsets_preserved": True,
            "other_entry_metadata_and_data_preserved": True,
        },
        "not_proved": [
            "ISO rebuild compatibility",
            "PPSSPP runtime visibility",
        ],
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
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    report = build(args.profile, args.archive, args.replacement, args.output_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
