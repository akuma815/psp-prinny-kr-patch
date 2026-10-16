#!/usr/bin/env python3
"""Export StageInfo00.dat to an editable translation CSV and protected manifest."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
from pathlib import Path


RECORD_COUNT = 20
RECORD_OFFSET = 0x04
RECORD_STRIDE = 0x170
SLOT_COUNT = 11
SLOT_SIZE = 33
PAYLOAD_SIZE = SLOT_SIZE - 1
RECORD_TAIL_SIZE = 3
FOOTER_SIZE = 12
EXPECTED_SIZE = RECORD_OFFSET + RECORD_COUNT * RECORD_STRIDE + FOOTER_SIZE

FIELDNAMES = [
    "entry_id",
    "record_index",
    "record_id",
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


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    game_dir = script_dir.parent.parent
    parser = argparse.ArgumentParser(
        description="Export fixed CP932 slots from StageInfo00.dat."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=game_dir / "work/system/start_assets_survey/StageInfo00.dat",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=game_dir / "workspace/text/translation/stage_info.csv",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=game_dir / "workspace/text/source/stage_info_manifest.json",
    )
    return parser.parse_args()


def load_editable_columns(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = csv.DictReader(handle)
        return {
            row["entry_id"]: {
                "ko": row.get("ko", ""),
                "status": row.get("status", ""),
                "notes": row.get("notes", ""),
            }
            for row in rows
            if row.get("entry_id")
        }


def decode_slot(slot: bytes, offset: int) -> tuple[bytes, str]:
    try:
        nul = slot.index(0)
    except ValueError as exc:
        raise ValueError(f"slot at 0x{offset:X} has no NUL terminator") from exc
    payload = slot[:nul]
    padding = slot[nul:]
    if any(padding):
        raise ValueError(f"slot at 0x{offset:X} has nonzero bytes after NUL")
    try:
        text = payload.decode("cp932", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError(f"invalid CP932 at 0x{offset:X}: {exc}") from exc
    return payload, text


def main() -> int:
    args = parse_args()
    source = args.input.resolve()
    csv_path = args.csv.resolve()
    manifest_path = args.manifest.resolve()
    data = source.read_bytes()

    if len(data) != EXPECTED_SIZE:
        raise ValueError(
            f"unexpected size: {len(data)} (expected {EXPECTED_SIZE}, 0x{EXPECTED_SIZE:X})"
        )
    count = struct.unpack_from("<I", data, 0)[0]
    if count != RECORD_COUNT:
        raise ValueError(f"unexpected record count: {count} (expected {RECORD_COUNT})")
    if any(data[-FOOTER_SIZE:]):
        raise ValueError("12-byte footer is not zero-filled")

    old_editable = load_editable_columns(csv_path)
    rows: list[dict[str, str | int]] = []
    manifest_records: list[dict[str, object]] = []
    nonempty = 0

    for record_index in range(RECORD_COUNT):
        record_offset = RECORD_OFFSET + record_index * RECORD_STRIDE
        record_id = struct.unpack_from("<H", data, record_offset)[0]
        tail_offset = record_offset + 2 + SLOT_COUNT * SLOT_SIZE
        tail = data[tail_offset : tail_offset + RECORD_TAIL_SIZE]
        if any(tail):
            raise ValueError(f"record {record_index + 1} tail is not zero-filled")

        manifest_slots: list[dict[str, object]] = []
        for slot_index in range(SLOT_COUNT):
            slot_offset = record_offset + 2 + slot_index * SLOT_SIZE
            slot = data[slot_offset : slot_offset + SLOT_SIZE]
            payload, ja = decode_slot(slot, slot_offset)
            kind = "title" if slot_index == 0 else "line"
            suffix = "title" if slot_index == 0 else f"line-{slot_index:02d}"
            entry_id = f"stage-{record_index + 1:02d}-{suffix}"
            editable = old_editable.get(entry_id, {})
            if ja:
                nonempty += 1
                default_status = "untranslated"
            else:
                default_status = "empty"

            rows.append(
                {
                    "entry_id": entry_id,
                    "record_index": record_index + 1,
                    "record_id": record_id,
                    "slot_index": slot_index,
                    "kind": kind,
                    "source_offset": f"0x{slot_offset:04X}",
                    "max_bytes": PAYLOAD_SIZE,
                    "source_bytes": payload.hex(),
                    "ja": ja,
                    "ko": editable.get("ko", ""),
                    "status": editable.get("status", default_status),
                    "notes": editable.get("notes", ""),
                }
            )
            manifest_slots.append(
                {
                    "entry_id": entry_id,
                    "slot_index": slot_index,
                    "kind": kind,
                    "offset": slot_offset,
                    "size": SLOT_SIZE,
                    "max_payload_bytes": PAYLOAD_SIZE,
                    "source_bytes": payload.hex(),
                    "ja": ja,
                }
            )

        manifest_records.append(
            {
                "record_index": record_index + 1,
                "record_id": record_id,
                "offset": record_offset,
                "stride": RECORD_STRIDE,
                "tail_hex": tail.hex(),
                "slots": manifest_slots,
            }
        )

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "format": "Prinny StageInfo00.dat fixed-slot table",
        "source": str(source),
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "source_size": len(data),
        "record_count": count,
        "record_offset": RECORD_OFFSET,
        "record_stride": RECORD_STRIDE,
        "slot_count_per_record": SLOT_COUNT,
        "slot_size": SLOT_SIZE,
        "max_payload_bytes": PAYLOAD_SIZE,
        "record_tail_size": RECORD_TAIL_SIZE,
        "footer_hex": data[-FOOTER_SIZE:].hex(),
        "translation_csv": str(csv_path),
        "row_count": len(rows),
        "nonempty_slot_count": nonempty,
        "empty_slot_count": len(rows) - nonempty,
        "records": manifest_records,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"source={source}")
    print(f"sha256={manifest['source_sha256']}")
    print(f"records={count} rows={len(rows)} nonempty={nonempty} empty={len(rows)-nonempty}")
    print(f"csv={csv_path}")
    print(f"manifest={manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
