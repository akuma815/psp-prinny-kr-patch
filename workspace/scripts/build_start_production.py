#!/usr/bin/env python3
"""Repack start.dat with verified production assets and relocated end offsets."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from inspect_start_dat import ENTRY, HEADER, read_entries


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build(profile_path: Path, archive_path: Path, replacements_dir: Path, output_dir: Path) -> dict[str, object]:
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    expected = profile["containers"]["start.dat"]
    source = archive_path.read_bytes()
    if len(source) != int(expected["size"]) or sha256(source) != expected["sha256"]:
        raise ValueError("start.dat does not match the supported revision")
    data_marker, entries = read_entries(archive_path)
    if data_marker != int(expected["data_marker"], 0) or len(entries) != int(expected["entry_count"]):
        raise ValueError("start.dat index geometry changed")
    configured = expected["replacements"]
    if set(configured) != {"font.fnt", "font.txp", "Demo00.dat"}:
        raise ValueError("production start.dat replacement set changed")
    by_name = {entry.name: entry for entry in entries}
    if not set(configured) <= set(by_name):
        raise ValueError("start.dat is missing a production target")

    payloads: list[bytes] = []
    replacement_reports: list[dict[str, object]] = []
    for entry in entries:
        original = source[entry.data_start:entry.data_end]
        if entry.name not in configured:
            payloads.append(original)
            continue
        if sha256(original) != configured[entry.name]:
            raise ValueError(f"source entry hash changed: {entry.name}")
        replacement = (replacements_dir / entry.name).read_bytes()
        if not replacement:
            raise ValueError(f"empty production replacement: {entry.name}")
        payloads.append(replacement)
        replacement_reports.append({
            "entry_name": entry.name,
            "original_size": len(original),
            "replacement_size": len(replacement),
            "delta": len(replacement) - len(original),
            "sha256": sha256(replacement),
        })

    prefix = bytearray(source[:data_marker])
    cursor = data_marker
    relocated = 0
    for entry, payload in zip(entries, payloads):
        cursor += len(payload)
        record_offset = HEADER.size + entry.index * ENTRY.size
        stored_end = 0 if entry.index == len(entries) - 1 else cursor
        old_stored_end, = struct.unpack_from("<I", source, record_offset + 28)
        if old_stored_end != stored_end:
            relocated += 1
        struct.pack_into("<I", prefix, record_offset + 28, stored_end)
    output = bytes(prefix) + b"".join(payloads)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "start.dat"
    output_path.write_bytes(output)
    output_marker, output_entries = read_entries(output_path)
    if output_marker != data_marker or len(output_entries) != len(entries):
        raise ValueError("repacked start.dat index did not parse")
    for before, after, expected_payload in zip(entries, output_entries, payloads):
        if (before.name, before.unknown_0, before.unknown_1, before.unknown_2) != (
            after.name, after.unknown_0, after.unknown_1, after.unknown_2
        ):
            raise ValueError(f"index metadata changed: {before.name}")
        if output[after.data_start:after.data_end] != expected_payload:
            raise ValueError(f"repacked payload mismatch: {before.name}")
    changed_end_offsets = [
        entry.index for entry in entries[:-1]
        if source[HEADER.size + entry.index * ENTRY.size + 28:HEADER.size + entry.index * ENTRY.size + 32]
        != output[HEADER.size + entry.index * ENTRY.size + 28:HEADER.size + entry.index * ENTRY.size + 32]
    ]
    report = {
        "schema_version": 1,
        "gate_id": "DEMO00-PRODUCTION-START-001",
        "status": "PASS: start.dat rebuilt and round-trip extracted",
        "input": {"size": len(source), "sha256": sha256(source)},
        "replacements": replacement_reports,
        "index": {
            "entry_count": len(entries),
            "data_marker": f"0x{data_marker:X}",
            "relocated_end_offsets": relocated,
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
        "runtime_gate": {"status": "PENDING", "reason": "LZS, SYSTEM.DAT, ISO, and PPSSPP remain"},
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
