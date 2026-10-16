#!/usr/bin/env python3
"""Inject verified font.txp and Demo00.dat replacements into start.dat."""

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
    replacements_dir: Path,
    output_dir: Path,
) -> dict[str, object]:
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    expected = profile["multi_poc"]["start_dat"]
    archive = archive_path.read_bytes()
    if sha256(archive) != expected["archive_sha256"]:
        raise ValueError("start.dat hash does not match the dialog E2E profile")
    _, archive_entries = read_entries(archive_path)
    by_name = {entry.name: entry for entry in archive_entries}
    output = bytearray(archive)
    reports = []
    allowed: set[int] = set()
    configured_names = {item["name"] for item in expected["entries"]}
    if configured_names != {"font.txp", "Demo00.dat"}:
        raise ValueError("dialog E2E must configure exactly font.txp and Demo00.dat")

    for item in expected["entries"]:
        name = item["name"]
        if name not in by_name:
            raise ValueError(f"start.dat target entry is missing: {name}")
        entry = by_name[name]
        start = int(item["data_start"], 0)
        end = int(item["data_end_exclusive"], 0)
        if (entry.data_start, entry.data_end, entry.span) != (
            start, end, int(item["span"])
        ):
            raise ValueError(f"start.dat target boundary changed: {name}")
        original = archive[start:end]
        if sha256(original) != item["sha256"]:
            raise ValueError(f"start.dat target hash changed: {name}")
        replacement_path = replacements_dir / name
        replacement = replacement_path.read_bytes()
        if len(replacement) != entry.span:
            raise ValueError(f"replacement size differs from target span: {name}")
        if replacement == original:
            raise ValueError(f"replacement does not change target entry: {name}")
        output[start:end] = replacement
        changed = sum(before != after for before, after in zip(original, replacement))
        allowed.update(range(start, end))
        reports.append(
            {
                "entry_name": name,
                "path": replacement_path.as_posix(),
                "start": f"0x{start:X}",
                "end_exclusive": f"0x{end:X}",
                "span": entry.span,
                "sha256": sha256(replacement),
                "actually_changed_bytes": changed,
            }
        )

    output = bytes(output)
    changed_offsets = {
        index for index, (before, after) in enumerate(zip(archive, output))
        if before != after
    }
    if not changed_offsets or not changed_offsets <= allowed:
        raise ValueError("start.dat changed outside configured replacement entries")
    if len(output) != len(archive):
        raise ValueError("start.dat size changed")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "start.dat"
    output_path.write_bytes(output)
    report = {
        "schema_version": 1,
        "gate_id": "POC-START-DIALOG-INJECT-001",
        "status": "PASS: unchanged-size font and dialog assets injected",
        "input": {
            "path": archive_path.as_posix(),
            "size": len(archive),
            "sha256": sha256(archive),
        },
        "replacements": reports,
        "output": {
            "path": output_path.as_posix(),
            "size": len(output),
            "sha256": sha256(output),
            "same_size_as_input": len(output) == len(archive),
            "actually_changed_bytes": len(changed_offsets),
        },
        "expected_write": {
            "owners": sorted(configured_names),
            "all_changes_inside_configured_entries": True,
        },
        "not_proved": [
            "LZS recompression and NISPACK compatibility",
            "ISO and PPSSPP runtime rendering",
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
    parser.add_argument("replacements_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    report = build(args.profile, args.archive, args.replacements_dir, args.output_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
