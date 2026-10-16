#!/usr/bin/env python3
"""Inject the unchanged-size font PoC into a verified start.dat image."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from inspect_start_dat import read_entries


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
    expected = poc["start_dat"]
    archive = archive_path.read_bytes()
    replacement = replacement_path.read_bytes()
    if sha256(archive) != expected["archive_sha256"]:
        raise ValueError("start.dat hash does not match the font PoC profile")

    _, entries = read_entries(archive_path)
    matches = [entry for entry in entries if entry.name == expected["entry_name"]]
    if len(matches) != 1:
        raise ValueError("start.dat must contain exactly one configured target entry")
    entry = matches[0]
    declared_start = int(expected["data_start"], 0)
    declared_end = int(expected["data_end_exclusive"], 0)
    if (entry.data_start, entry.data_end, entry.span) != (
        declared_start,
        declared_end,
        int(expected["span"]),
    ):
        raise ValueError("start.dat target entry boundary changed")
    original_entry = archive[entry.data_start:entry.data_end]
    if sha256(original_entry) != expected["entry_sha256"]:
        raise ValueError("start.dat target entry hash changed")
    if len(replacement) != entry.span:
        raise ValueError("replacement size differs from the fixed target span")
    if replacement == original_entry:
        raise ValueError("replacement does not change the target entry")

    output = bytearray(archive)
    output[entry.data_start:entry.data_end] = replacement
    output = bytes(output)
    changed = [
        index
        for index, (before, after) in enumerate(zip(archive, output))
        if before != after
    ]
    expected_changed = [
        entry.data_start + index
        for index, (before, after) in enumerate(zip(original_entry, replacement))
        if before != after
    ]
    if changed != expected_changed:
        raise ValueError("start.dat diff is not exactly the declared entry diff")
    if len(output) != len(archive):
        raise ValueError("start.dat size changed")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "start.dat"
    output_path.write_bytes(output)
    report = {
        "schema_version": 1,
        "gate_id": "POC-START-INJECT-001",
        "status": "PASS: unchanged-size start.dat asset injection",
        "input": {
            "path": archive_path.as_posix(),
            "size": len(archive),
            "sha256": sha256(archive),
        },
        "replacement": {
            "path": replacement_path.as_posix(),
            "entry_name": entry.name,
            "entry_start": f"0x{entry.data_start:X}",
            "entry_end_exclusive": f"0x{entry.data_end:X}",
            "entry_span": entry.span,
            "sha256": sha256(replacement),
            "actually_changed_bytes": len(changed),
        },
        "output": {
            "path": output_path.as_posix(),
            "size": len(output),
            "sha256": sha256(output),
            "same_size_as_input": len(output) == len(archive),
        },
        "expected_write": {
            "owner": entry.name,
            "start": f"0x{entry.data_start:X}",
            "end_exclusive": f"0x{entry.data_end:X}",
            "rule": "all changed bytes equal the replacement-vs-original entry diff",
        },
        "not_proved": [
            "NIS LZS recompression compatibility",
            "SYSTEM.DAT NISPACK replacement compatibility",
            "ISO rebuild and PPSSPP runtime visibility",
        ],
    }
    (output_dir / "start_report.json").write_text(
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
