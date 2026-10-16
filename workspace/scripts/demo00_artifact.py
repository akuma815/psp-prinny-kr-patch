#!/usr/bin/env python3
"""Export and validate the complete Demo00 translation artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import demo00


SCHEMA_VERSION = 1
SUPPORTED_DISC = {"disc_id": "ULJS00150", "disc_version": "1.01"}
STATUSES = {
    "untranslated",
    "in_progress",
    "needs_review",
    "needs_human_review",
    "complete",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encode_source_slot(text: str, size: int, field: str) -> bytes:
    try:
        payload = text.encode("cp932", errors="strict")
    except UnicodeEncodeError as error:
        raise ValueError(f"{field} source text is not CP932") from error
    if len(payload) >= size:
        raise ValueError(
            f"{field} needs {len(payload) + 1} bytes including NUL; slot is {size}"
        )
    return payload + bytes(size - len(payload))


def _seed_by_id(seed_path: Path | None) -> dict[int, dict[str, Any]]:
    if seed_path is None:
        return {}
    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    result: dict[int, dict[str, Any]] = {}
    for item in seed.get("entries", []):
        if item.get("status") != "poc_approved":
            continue
        record_id = int(item["record_id"])
        result[record_id] = {
            "speaker": item["ko_speaker"],
            "lines": list(item["ko_lines"]),
            "status": "complete",
            "notes": "화면 검증을 통과한 기존 단일 대화 PoC에서 이관.",
            "flags": ["screen_verified", "temporary_proxy_mapping"],
        }
    return result


def export_artifact(
    source_path: Path,
    source: bytes,
    seed_path: Path | None = None,
) -> dict[str, Any]:
    table = demo00.parse(source)
    seeds = _seed_by_id(seed_path)
    entries = []
    for record in table.records:
        offset = demo00.HEADER.size + record.index * demo00.RECORD_SIZE
        target = seeds.get(record.record_id, {
            "speaker": "",
            "lines": ["", "", ""],
            "status": "untranslated",
            "notes": "",
            "flags": [],
        })
        entries.append({
            "entry_id": f"demo00/{record.record_id:04X}",
            "coordinates": {
                "index": record.index,
                "file_offset": f"0x{offset:08X}",
            },
            "protected": {
                "record_id": record.record_id,
                "raw_hex": record.to_bytes().hex(),
                "controls": {
                    "layout_variant": record.control_2,
                    "reserved_3": record.unknown_3,
                    "face_asset_signed": record.value_4,
                    "speaker_box_style": record.speaker_control,
                    "tail_hex": record.tail.hex(),
                },
                "source": {
                    "speaker": record.speaker,
                    "lines": list(record.lines),
                },
            },
            "translation": target,
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "table_id": "demo00/main",
        "supported_revision": SUPPORTED_DISC,
        "source": {
            "asset_path": "SYSTEM.DAT/start.lzs/start.dat/Demo00.dat",
            "workspace_path": source_path.as_posix(),
            "size": len(source),
            "sha256": sha256(source),
            "consumer": "BOOT.BIN:0x08862F90",
        },
        "layout": {
            "encoding": "cp932",
            "record_count": len(table.records),
            "record_size": demo00.RECORD_SIZE,
            "table_offset": "0x00000004",
            "speaker_size": demo00.SPEAKER_SIZE,
            "line_count": 3,
            "line_size": demo00.LINE_SIZE,
            "footer_size": demo00.FOOTER_SIZE,
            "terminator": "00",
            "padding": "00",
        },
        "edit_policy": {
            "editable_fields": [
                "entries[].translation.speaker",
                "entries[].translation.lines[]",
                "entries[].translation.status",
                "entries[].translation.notes",
                "entries[].translation.flags[]",
            ],
            "protected_fields": [
                "source",
                "layout",
                "entries[].entry_id",
                "entries[].coordinates",
                "entries[].protected",
            ],
            "slot_policy": "fixed",
            "overflow_policy": "error",
            "production_encoding": "not_approved",
        },
        "entries": entries,
    }


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_and_rebuild(artifact: dict[str, Any], current_source: bytes) -> tuple[bytes, dict[str, Any]]:
    _expect(artifact.get("schema_version") == SCHEMA_VERSION, "unsupported schema version")
    _expect(artifact.get("table_id") == "demo00/main", "unexpected table ID")
    _expect(artifact.get("supported_revision") == SUPPORTED_DISC, "unsupported disc revision")
    source_meta = artifact.get("source", {})
    _expect(source_meta.get("size") == len(current_source), "source size is stale")
    _expect(source_meta.get("sha256") == sha256(current_source), "source hash is stale")
    table = demo00.parse(current_source)
    layout = artifact.get("layout", {})
    _expect(layout.get("record_count") == len(table.records), "record count is stale")
    _expect(layout.get("record_size") == demo00.RECORD_SIZE, "record size changed")
    entries = artifact.get("entries")
    _expect(isinstance(entries, list), "entries must be a list")
    _expect(len(entries) == len(table.records), "artifact does not cover every record")

    rebuilt_records = []
    seen_ids: set[str] = set()
    status_counts = {status: 0 for status in sorted(STATUSES)}
    translated_hangul: set[str] = set()
    nonempty_source_slots = 0
    for index, (item, original) in enumerate(zip(entries, table.records)):
        entry_id = f"demo00/{original.record_id:04X}"
        _expect(item.get("entry_id") == entry_id, f"entry identity mismatch at index {index}")
        _expect(entry_id not in seen_ids, f"duplicate entry identity: {entry_id}")
        seen_ids.add(entry_id)
        offset = demo00.HEADER.size + index * demo00.RECORD_SIZE
        coordinates = item.get("coordinates", {})
        _expect(coordinates.get("index") == index, f"index mismatch for {entry_id}")
        _expect(
            coordinates.get("file_offset") == f"0x{offset:08X}",
            f"file offset mismatch for {entry_id}",
        )
        protected = item.get("protected", {})
        _expect(protected.get("record_id") == original.record_id, f"record ID changed for {entry_id}")
        _expect(protected.get("raw_hex") == original.to_bytes().hex(), f"raw bytes changed for {entry_id}")
        controls = protected.get("controls", {})
        expected_controls = {
            "layout_variant": original.control_2,
            "reserved_3": original.unknown_3,
            "face_asset_signed": original.value_4,
            "speaker_box_style": original.speaker_control,
            "tail_hex": original.tail.hex(),
        }
        _expect(controls == expected_controls, f"control metadata changed for {entry_id}")
        source_text = protected.get("source", {})
        _expect(source_text.get("speaker") == original.speaker, f"source speaker changed for {entry_id}")
        _expect(source_text.get("lines") == list(original.lines), f"source lines changed for {entry_id}")
        nonempty_source_slots += bool(original.speaker) + sum(bool(line) for line in original.lines)

        translation = item.get("translation", {})
        speaker = translation.get("speaker")
        lines = translation.get("lines")
        status = translation.get("status")
        _expect(isinstance(speaker, str), f"translation speaker must be text for {entry_id}")
        _expect(isinstance(lines, list) and len(lines) == 3, f"translation lines must have 3 slots for {entry_id}")
        _expect(all(isinstance(line, str) for line in lines), f"translation line must be text for {entry_id}")
        _expect(status in STATUSES, f"invalid translation status for {entry_id}")
        _expect(isinstance(translation.get("notes"), str), f"notes must be text for {entry_id}")
        flags = translation.get("flags")
        _expect(isinstance(flags, list) and all(isinstance(flag, str) for flag in flags), f"flags must be text list for {entry_id}")
        if status == "untranslated":
            _expect(not speaker and not any(lines), f"untranslated entry has target text: {entry_id}")
        status_counts[status] += 1
        for character in speaker + "".join(lines):
            if "가" <= character <= "힣":
                translated_hangul.add(character)

        speaker_raw = encode_source_slot(original.speaker, demo00.SPEAKER_SIZE, f"{entry_id} source speaker")
        lines_raw = tuple(
            encode_source_slot(line, demo00.LINE_SIZE, f"{entry_id} source line {line_index}")
            for line_index, line in enumerate(original.lines)
        )
        rebuilt_records.append(replace(original, speaker_raw=speaker_raw, lines_raw=lines_raw))

    rebuilt = demo00.Table(tuple(rebuilt_records), table.footer).to_bytes()
    _expect(rebuilt == current_source, "source round-trip is not byte-identical")
    report = {
        "schema_version": 1,
        "gate_id": "DEMO00-ARTIFACT-001",
        "status": "PASS: complete population and byte-identical source round-trip",
        "source_sha256": sha256(current_source),
        "record_count": len(table.records),
        "slot_count": len(table.records) * 4,
        "nonempty_source_slots": nonempty_source_slots,
        "status_counts": status_counts,
        "translated_unique_hangul_count": len(translated_hangul),
        "translated_unique_hangul": "".join(sorted(translated_hangul)),
        "protected_fields_match_current_source": True,
        "source_roundtrip_byte_identical": True,
        "production_writer_enabled": False,
        "not_proved": [
            "production-safe Korean code allocation",
            "translation slot fit after production encoding",
            "complete Korean translation of all records",
        ],
    }
    return rebuilt, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    export_parser = subparsers.add_parser("export")
    export_parser.add_argument("source", type=Path)
    export_parser.add_argument("output", type=Path)
    export_parser.add_argument("--seed-poc", type=Path)
    export_parser.add_argument("--force", action="store_true")
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("source", type=Path)
    verify_parser.add_argument("artifact", type=Path)
    verify_parser.add_argument("report", type=Path)
    verify_parser.add_argument("--roundtrip-output", type=Path)
    args = parser.parse_args()

    source = args.source.read_bytes()
    if args.command == "export":
        if args.output.exists() and not args.force:
            raise SystemExit(
                f"REFUSED: {args.output} already exists; use --force only for an approved re-extraction"
            )
        artifact = export_artifact(args.source, source, args.seed_poc)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"OK: exported {len(artifact['entries'])} entries to {args.output}")
        return 0

    artifact = json.loads(args.artifact.read_text(encoding="utf-8"))
    rebuilt, report = validate_and_rebuild(artifact, source)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if args.roundtrip_output:
        args.roundtrip_output.parent.mkdir(parents=True, exist_ok=True)
        args.roundtrip_output.write_bytes(rebuilt)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
