#!/usr/bin/env python3
"""Patch fixed-slot start.dat string tables (LuckyItem/Collection/Honor/MusicShop).

Layouts match export_start_tables.py; see that module for the verified
structure of each table.  Slots are NUL-padded to their fixed size and the
surrounding numeric fields and footers are preserved byte-identically.
"""

from __future__ import annotations

import csv
import struct
from pathlib import Path


TABLES: dict[str, dict[str, object]] = {
    "LuckyItem.dat": {
        "header": 6,
        "records": 60,
        "stride": 92,
        "slots": {"name": (0x00, 21), "desc": (0x15, 65)},
        "rows": 120,
    },
    "MusicShop.dat": {
        "header": 4,
        "records": 30,
        "stride": 92,
        "slots": {"short": (0x03, 21), "title": (0x18, 65)},
        "rows": 60,
    },
    "Collection.dat": {
        "header": 6,
        "records": 60,
        "stride": 72,
        "slots": {"desc": (0x00, 66)},
        "rows": 60,
    },
    "Honor.dat": {
        "header": 6,
        "records": 30,
        "stride": 204,
        "slots": {"title": (0x00, 65), "line1": (0x41, 65), "line2": (0x82, 66)},
        "rows": 90,
    },
}


def load_rows(path: Path, member: str) -> list[dict[str, str]]:
    spec = TABLES[member]
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != int(spec["rows"]):  # type: ignore[arg-type]
        raise ValueError(f"unexpected {member} row count: {len(rows)}")
    return rows


def patch(
    member: str,
    source: bytes,
    rows: list[dict[str, str]],
    character_map: dict[str, bytes],
) -> tuple[bytes, list[dict[str, object]]]:
    spec = TABLES[member]
    header = int(spec["header"])
    records = int(spec["records"])
    stride = int(spec["stride"])
    slots: dict[str, tuple[int, int]] = spec["slots"]  # type: ignore[assignment]
    declared = struct.unpack_from("<I" if header == 6 else "<H", source)[0]
    if declared != records:
        raise ValueError(f"{member}: unexpected record count {declared}")

    output = bytearray(source)
    report: list[dict[str, object]] = []
    seen: set[tuple[int, str]] = set()
    for row in rows:
        record_index = int(row["record_index"])
        field = str(row["field"])
        key = (record_index, field)
        if key in seen:
            raise ValueError(f"duplicate {member} slot: {row['entry_id']}")
        seen.add(key)
        if not 0 <= record_index < records:
            raise ValueError(f"invalid {member} record index: {record_index}")
        rel, slot_size = slots[field]
        absolute = header + record_index * stride + rel
        if absolute != int(row["source_offset"], 0):
            raise ValueError(f"{row['entry_id']} offset mismatch")

        source_payload = str(row["ja"]).encode("cp932")
        slot = source[absolute:absolute + slot_size]
        if slot[: len(source_payload)] != source_payload:
            raise ValueError(f"{row['entry_id']} source payload mismatch")
        if any(slot[len(source_payload):]):
            raise ValueError(f"{row['entry_id']} source padding mismatch")

        translation = str(row.get("ko", "")).strip()
        if not translation:
            raise ValueError(f"{row['entry_id']} has no Korean translation")
        if translation == str(row["ja"]).strip():
            continue

        payload = bytearray()
        for character in translation:
            if character in character_map:
                payload.extend(character_map[character])
            else:
                payload.extend(character.encode("cp932", errors="strict"))
        if len(payload) > slot_size - 1:
            raise ValueError(
                f"{row['entry_id']} exceeds {slot_size - 1} bytes: {len(payload)}"
            )
        output[absolute:absolute + slot_size] = bytes(payload) + bytes(
            slot_size - len(payload)
        )
        report.append(
            {
                "entry_id": row["entry_id"],
                "offset": f"0x{absolute:05X}",
                "encoded_bytes": len(payload),
                "remaining_bytes": slot_size - 1 - len(payload),
            }
        )
    return bytes(output), report
