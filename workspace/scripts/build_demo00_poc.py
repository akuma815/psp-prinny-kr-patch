#!/usr/bin/env python3
"""Build one fixed-slot translated Demo00.dat PoC with protected metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import demo00


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encode_slot(proxy: str, size: int, field: str) -> bytes:
    payload = proxy.encode("cp932", errors="strict")
    if payload.decode("cp932") != proxy:
        raise ValueError(f"{field} proxy is not byte-reversible CP932")
    if len(payload) >= size:
        raise ValueError(
            f"{field} requires {len(payload) + 1} bytes including NUL, slot is {size}"
        )
    return payload + bytes(size - len(payload))


def build(
    profile_path: Path,
    artifact_path: Path,
    source_path: Path,
    output_dir: Path,
) -> dict[str, object]:
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    source = source_path.read_bytes()
    expected = profile["multi_poc"]["dialog"]
    if sha256(source) != expected["source_sha256"]:
        raise ValueError("Demo00.dat hash does not match the E2E profile")
    if artifact["source"]["sha256"] != expected["source_sha256"]:
        raise ValueError("translation artifact source identity is stale")
    entries = artifact.get("entries", [])
    if len(entries) != 1:
        raise ValueError("dialog E2E artifact must contain exactly one entry")
    item = entries[0]
    if item["status"] != "poc_approved":
        raise ValueError("dialog E2E entry is not approved for the PoC build")
    if item["record_id"] != expected["record_id"]:
        raise ValueError("dialog E2E record ID differs from the profile")

    table = demo00.parse(source)
    matches = [record for record in table.records if record.record_id == item["record_id"]]
    if len(matches) != 1:
        raise ValueError("configured Demo00 record ID is not unique")
    original = matches[0]
    if original.index != expected["record_index"]:
        raise ValueError("configured Demo00 record index changed")
    record_offset = demo00.HEADER.size + original.index * demo00.RECORD_SIZE
    if record_offset != int(expected["record_offset"], 0):
        raise ValueError("configured Demo00 record offset changed")
    if original.to_bytes().hex() != item["original_raw_hex"]:
        raise ValueError("protected original record bytes changed")
    if original.speaker != item["source_speaker"] or list(original.lines) != item["source_lines"]:
        raise ValueError("translation artifact source text differs from the current record")

    speaker_raw = encode_slot(
        item["proxy_cp932_speaker"], demo00.SPEAKER_SIZE, "speaker"
    )
    lines_raw = tuple(
        encode_slot(value, demo00.LINE_SIZE, f"line {index}")
        for index, value in enumerate(item["proxy_cp932_lines"])
    )
    if len(lines_raw) != 3:
        raise ValueError("dialog E2E requires exactly three line slots")
    patched_record = replace(
        original,
        speaker_raw=speaker_raw,
        lines_raw=lines_raw,
    )
    records = list(table.records)
    records[original.index] = patched_record
    output = demo00.Table(tuple(records), table.footer).to_bytes()
    reparsed = demo00.parse(output)
    if reparsed.records[original.index].speaker != item["proxy_cp932_speaker"]:
        raise ValueError("rebuilt speaker proxy did not round-trip")
    if list(reparsed.records[original.index].lines) != item["proxy_cp932_lines"]:
        raise ValueError("rebuilt line proxies did not round-trip")

    protected = set(range(record_offset + 7, record_offset + 24))
    for line_offset in demo00.LINE_OFFSETS:
        protected.update(
            range(record_offset + line_offset, record_offset + line_offset + demo00.LINE_SIZE)
        )
    changed = [
        index for index, (before, after) in enumerate(zip(source, output))
        if before != after
    ]
    if not changed or not set(changed) <= protected:
        raise ValueError("Demo00 PoC changed bytes outside the target string slots")
    before_record = source[record_offset:record_offset + demo00.RECORD_SIZE]
    after_record = output[record_offset:record_offset + demo00.RECORD_SIZE]
    for offset in list(range(0, 7)) + list(range(129, 132)):
        if before_record[offset] != after_record[offset]:
            raise ValueError("Demo00 control metadata changed")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "Demo00.dat"
    output_path.write_bytes(output)
    report = {
        "schema_version": 1,
        "gate_id": "POC-DIALOG-REINSERT-001",
        "status": "PASS: one fixed-slot Demo00 record rebuilt",
        "source": {
            "path": source_path.as_posix(),
            "size": len(source),
            "sha256": sha256(source),
        },
        "entry": {
            "entry_id": item["entry_id"],
            "record_id": item["record_id"],
            "record_index": original.index,
            "record_offset": f"0x{record_offset:X}",
            "source_speaker": item["source_speaker"],
            "source_lines": item["source_lines"],
            "ko_speaker": item["ko_speaker"],
            "ko_lines": item["ko_lines"],
            "proxy_cp932_speaker": item["proxy_cp932_speaker"],
            "proxy_cp932_lines": item["proxy_cp932_lines"],
            "control_metadata_byte_identical": True,
            "actually_changed_bytes": len(changed),
        },
        "output": {
            "path": output_path.as_posix(),
            "size": len(output),
            "sha256": sha256(output),
            "same_size_as_input": len(output) == len(source),
        },
        "expected_write": {
            "owner": "Demo00.dat record 0x07D0 string slots",
            "speaker": f"0x{record_offset + 7:X}..0x{record_offset + 24:X}",
            "line_0": f"0x{record_offset + 24:X}..0x{record_offset + 59:X}",
            "line_1": f"0x{record_offset + 59:X}..0x{record_offset + 94:X}",
            "line_2": f"0x{record_offset + 94:X}..0x{record_offset + 129:X}",
            "all_changes_inside_declared_slots": True,
        },
        "not_proved": [
            "runtime rendering of the Korean translation",
            "production-safe character allocation",
            "general writer policy for every Demo00 record",
        ],
    }
    (output_dir / "demo00_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("source", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    report = build(args.profile, args.artifact, args.source, args.output_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
