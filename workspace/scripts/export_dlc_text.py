#!/usr/bin/env python3
"""Export Prinny DLC DDEM and DSTI text to protected translation CSVs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import didt


DDEM_FIELDS = [
    "entry_id",
    "dlc_id",
    "record_index",
    "record_id",
    "source_offset",
    "speaker_offset",
    "speaker_max_bytes",
    "speaker_bytes",
    "ja_speaker",
    "ko_speaker",
    "line_1_offset",
    "line_1_max_bytes",
    "line_1_bytes",
    "ja_line_1",
    "ko_line_1",
    "line_2_offset",
    "line_2_max_bytes",
    "line_2_bytes",
    "ja_line_2",
    "ko_line_2",
    "line_3_offset",
    "line_3_max_bytes",
    "line_3_bytes",
    "ja_line_3",
    "ko_line_3",
    "status",
    "notes",
]

DDEM_EDITABLE_FIELDS = (
    "ko_speaker",
    "ko_line_1",
    "ko_line_2",
    "ko_line_3",
    "status",
    "notes",
)

DSTI_FIELDS = [
    "entry_id",
    "dlc_id",
    "slot_index",
    "kind",
    "source_offset",
    "max_bytes",
    "source_bytes",
    "ja",
    "ko",
    "status",
    "notes",
]

EXPECTED_SOURCES = {
    "DL0000.EDAT": {
        "index": 0,
        "size": 1624784,
        "sha256": "a0209702de5210b2f35c57e7c12bfddbeb691200de06769b615ca50254d48c1b",
        "ddem_records": 29,
    },
    "DL0001.EDAT": {
        "index": 1,
        "size": 1540688,
        "sha256": "86b48d56b6ba853f09ffb0a524ccebf4f601c78cb0f4937cb885ec8815bdb7a7",
        "ddem_records": 23,
    },
    "DL0002.EDAT": {
        "index": 2,
        "size": 1365296,
        "sha256": "3fbc26ed99c1b3f474e50dd5290eb0497e61f0a7e8e9268fb82980a426079be9",
        "ddem_records": 15,
    },
}


def _payload(slot: bytes, *, context: str) -> bytes:
    try:
        end = slot.index(0)
    except ValueError as exc:
        raise ValueError(f"{context} has no NUL terminator") from exc
    if any(slot[end:]):
        raise ValueError(f"{context} has non-zero padding")
    return slot[:end]


def _load_editable(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return {
            row["entry_id"]: {
                "ko": row.get("ko", ""),
                "status": row.get("status", ""),
                "notes": row.get("notes", ""),
            }
            for row in reader
            if row.get("entry_id")
        }


def _load_dialogue_editable(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not set(DDEM_EDITABLE_FIELDS).issubset(reader.fieldnames or []):
            return {}
        return {
            row["entry_id"]: {
                field: row.get(field, "")
                for field in DDEM_EDITABLE_FIELDS
            }
            for row in reader
            if row.get("entry_id")
        }


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _portable_path(path: Path, project: Path) -> str:
    try:
        return path.resolve().relative_to(project.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def export(
    input_dir: Path,
    translation_dir: Path,
    manifest_path: Path,
) -> dict[str, object]:
    project = Path(__file__).resolve().parents[2]
    dsti_path = translation_dir / "dlc_stage_info.csv"
    old_dsti = _load_editable(dsti_path)
    dsti_rows: list[dict[str, object]] = []
    source_manifests: list[dict[str, object]] = []

    for filename, expected in EXPECTED_SOURCES.items():
        path = input_dir / filename
        source = path.read_bytes()
        digest = hashlib.sha256(source).hexdigest()
        if len(source) != expected["size"] or digest != expected["sha256"]:
            raise ValueError(
                f"unsupported {filename}: size={len(source)}, sha256={digest}"
            )
        container = didt.parse(source)
        if container.dlc_index != expected["index"]:
            raise ValueError(
                f"{filename} DLC index is {container.dlc_index}, expected {expected['index']}"
            )
        if container.to_bytes() != source:
            raise ValueError(f"{filename} DIDT0 round-trip mismatch")

        ddem_chunk = container.chunk("DDEM")
        ddem = didt.parse_ddem(ddem_chunk.payload)
        if len(ddem.records) != expected["ddem_records"]:
            raise ValueError(
                f"{filename} has {len(ddem.records)} DDEM records, "
                f"expected {expected['ddem_records']}"
            )
        dlc_id = filename[:6].lower()
        ddem_path = translation_dir / f"{dlc_id}_ddem.csv"
        old_ddem = _load_dialogue_editable(ddem_path)
        ddem_rows: list[dict[str, object]] = []
        ddem_manifest: list[dict[str, object]] = []
        ddem_payload_offset = ddem_chunk.offset + didt.CHUNK_HEADER.size

        for record in ddem.records:
            record_offset = ddem_payload_offset + 4 + record.index * didt.DDEM_RECORD_SIZE
            entry_id = f"{dlc_id}-ddem-{record.record_id:04x}"
            editable = old_ddem.get(entry_id, {})
            speaker_payload = _payload(
                record.speaker_raw,
                context=f"{filename} {record.record_id:04X} speaker",
            )
            line_payloads = tuple(
                _payload(raw, context=f"{filename} {record.record_id:04X} line {index}")
                for index, raw in enumerate(record.lines_raw, 1)
            )
            row: dict[str, object] = {
                "entry_id": entry_id,
                "dlc_id": dlc_id,
                "record_index": record.index,
                "record_id": f"0x{record.record_id:04X}",
                "source_offset": f"0x{record_offset:08X}",
                "speaker_offset": f"0x{record_offset + didt.DDEM_SPEAKER_OFFSET:08X}",
                "speaker_max_bytes": didt.DDEM_SPEAKER_SIZE - 1,
                "speaker_bytes": speaker_payload.hex(),
                "ja_speaker": record.speaker,
                "ko_speaker": editable.get("ko_speaker", ""),
                "status": editable.get("status", "untranslated"),
                "notes": editable.get("notes", ""),
            }
            for line_index, (relative_offset, raw, payload, ja) in enumerate(
                zip(
                    didt.DDEM_LINE_OFFSETS,
                    record.lines_raw,
                    line_payloads,
                    record.lines,
                    strict=True,
                ),
                1,
            ):
                row[f"line_{line_index}_offset"] = f"0x{record_offset + relative_offset:08X}"
                row[f"line_{line_index}_max_bytes"] = len(raw) - 1
                row[f"line_{line_index}_bytes"] = payload.hex()
                row[f"ja_line_{line_index}"] = ja
                row[f"ko_line_{line_index}"] = editable.get(f"ko_line_{line_index}", "")
            ddem_rows.append(row)
            ddem_manifest.append(
                {
                    "record_index": record.index,
                    "record_id": f"0x{record.record_id:04X}",
                    "source_offset": f"0x{record_offset:08X}",
                    "raw_sha256": hashlib.sha256(record.raw).hexdigest(),
                    "protected": {
                        key: row[key]
                        for key in row
                        if key not in DDEM_EDITABLE_FIELDS
                    },
                }
            )
        _write_csv(ddem_path, DDEM_FIELDS, ddem_rows)

        dsti_chunk = container.chunk("DSTI")
        dsti = didt.parse_dsti(dsti_chunk.payload)
        dsti_payload_offset = dsti_chunk.offset + didt.CHUNK_HEADER.size
        dsti_manifest: list[dict[str, object]] = []
        for slot_index, (raw, ja) in enumerate(zip(dsti.slots_raw, dsti.slots, strict=True)):
            payload = _payload(raw, context=f"{filename} DSTI slot {slot_index}")
            kind = "title" if slot_index == 0 else f"line-{slot_index:02d}"
            entry_id = f"{dlc_id}-dsti-{kind}"
            editable = old_dsti.get(entry_id, {})
            source_offset = dsti_payload_offset + didt.DSTI_HEADER_SIZE + slot_index * didt.DSTI_SLOT_SIZE
            status = editable.get("status", "untranslated" if ja else "empty")
            row = {
                "entry_id": entry_id,
                "dlc_id": dlc_id,
                "slot_index": slot_index,
                "kind": kind,
                "source_offset": f"0x{source_offset:08X}",
                "max_bytes": didt.DSTI_SLOT_SIZE - 1,
                "source_bytes": payload.hex(),
                "ja": ja,
                "ko": editable.get("ko", ""),
                "status": status,
                "notes": editable.get("notes", ""),
            }
            dsti_rows.append(row)
            dsti_manifest.append({key: row[key] for key in row if key not in {"ko", "status", "notes"}})

        summary = didt.export_summary(path, source, container)
        summary["source"]["path"] = _portable_path(path, project)
        source_manifests.append(
            {
                **summary,
                "translation_csv": _portable_path(ddem_path, project),
                "ddem_entries": ddem_manifest,
                "dsti_entries": dsti_manifest,
            }
        )

    _write_csv(dsti_path, DSTI_FIELDS, dsti_rows)
    manifest = {
        "schema_version": 1,
        "scope": "Prinny ULJS00150 optional DLC DIDT0 text baseline",
        "editable_fields": {
            "ddem": list(DDEM_EDITABLE_FIELDS),
            "dsti": ["ko", "status", "notes"],
        },
        "protected_fields": {
            "ddem": [field for field in DDEM_FIELDS if field not in DDEM_EDITABLE_FIELDS],
            "dsti": [field for field in DSTI_FIELDS if field not in {"ko", "status", "notes"}],
        },
        "dsti_translation_csv": _portable_path(dsti_path, project),
        "sources": source_manifests,
        "totals": {
            "files": len(source_manifests),
            "ddem_records": sum(source["ddem"]["record_count"] for source in source_manifests),
            "ddem_rows": sum(source["ddem"]["record_count"] for source in source_manifests),
            "ddem_text_slots": sum(source["ddem"]["record_count"] * 4 for source in source_manifests),
            "ddem_nonempty_text_slots": sum(
                source["ddem"]["nonempty_text_slots"] for source in source_manifests
            ),
            "dsti_rows": len(dsti_rows),
            "dsti_nonempty_text_slots": sum(bool(row["ja"]) for row in dsti_rows),
        },
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    project = script_dir.parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=project / "original/Prinny DLC",
    )
    parser.add_argument(
        "--translation-dir",
        type=Path,
        default=project / "workspace/text/translation/dlc",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=project / "workspace/text/source/dlc_manifest.json",
    )
    args = parser.parse_args()
    manifest = export(args.input_dir, args.translation_dir, args.manifest)
    totals = manifest["totals"]
    print(
        "PASS: "
        f"{totals['files']} files, {totals['ddem_records']} DDEM records, "
        f"{totals['ddem_nonempty_text_slots']} nonempty DDEM slots, "
        f"{totals['dsti_nonempty_text_slots']} nonempty DSTI slots"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
