#!/usr/bin/env python3
"""Parse and patch Prinny's fixed-record LuckyDoll.dat string table."""

from __future__ import annotations

import csv
import struct
from pathlib import Path


RECORD_COUNT = 120
RECORD_OFFSET = 4
RECORD_STRIDE = 68
TEXT_OFFSET = 2
TEXT_SLOT_SIZE = 66
TEXT_PAYLOAD_SIZE = 65
FOOTER_SIZE = 12
EXPECTED_SIZE = RECORD_OFFSET + RECORD_COUNT * RECORD_STRIDE + FOOTER_SIZE


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != RECORD_COUNT:
        raise ValueError(f"unexpected LuckyDoll row count: {len(rows)}")
    return rows


def patch(
    source: bytes,
    rows: list[dict[str, str]],
    character_map: dict[str, bytes],
) -> tuple[bytes, list[dict[str, object]]]:
    if len(source) != EXPECTED_SIZE:
        raise ValueError(f"unexpected LuckyDoll.dat size: {len(source)}")
    if struct.unpack_from("<I", source, 0)[0] != RECORD_COUNT:
        raise ValueError("unexpected LuckyDoll record count")
    if any(source[-FOOTER_SIZE:]):
        raise ValueError("LuckyDoll footer is not zero-filled")

    output = bytearray(source)
    report: list[dict[str, object]] = []
    seen_records: set[int] = set()
    for row in rows:
        record_index = int(row["record_index"])
        if record_index in seen_records:
            raise ValueError(f"duplicate LuckyDoll record index: {record_index}")
        seen_records.add(record_index)
        if not 1 <= record_index <= RECORD_COUNT:
            raise ValueError(f"invalid LuckyDoll record index: {record_index}")

        record_offset = RECORD_OFFSET + (record_index - 1) * RECORD_STRIDE
        text_offset = record_offset + TEXT_OFFSET
        declared_offset = int(row["source_offset"], 0)
        if declared_offset != text_offset:
            raise ValueError(f"{row['entry_id']} offset mismatch")
        record_id = struct.unpack_from("<H", source, record_offset)[0]
        if int(row["record_id"]) != record_id:
            raise ValueError(f"{row['entry_id']} record id mismatch")

        slot = source[text_offset : text_offset + TEXT_SLOT_SIZE]
        source_payload = bytes.fromhex(row["source_bytes"])
        if slot[: len(source_payload)] != source_payload:
            raise ValueError(f"{row['entry_id']} source payload mismatch")
        if slot[len(source_payload)] != 0 or any(slot[len(source_payload) + 1 :]):
            raise ValueError(f"{row['entry_id']} source padding mismatch")

        translation = row.get("ko", "")
        if not translation:
            raise ValueError(f"{row['entry_id']} has no Korean translation")
        payload = bytearray()
        for character in translation:
            if character in character_map:
                payload.extend(character_map[character])
            else:
                payload.extend(character.encode("cp932", errors="strict"))
        if len(payload) > TEXT_PAYLOAD_SIZE:
            raise ValueError(
                f"{row['entry_id']} exceeds {TEXT_PAYLOAD_SIZE} bytes: {len(payload)}"
            )
        replacement = bytes(payload) + bytes(TEXT_SLOT_SIZE - len(payload))
        output[text_offset : text_offset + TEXT_SLOT_SIZE] = replacement
        report.append(
            {
                "entry_id": row["entry_id"],
                "record_id": record_id,
                "offset": f"0x{text_offset:04X}",
                "encoded_bytes": len(payload),
                "remaining_bytes": TEXT_PAYLOAD_SIZE - len(payload),
            }
        )

    if seen_records != set(range(1, RECORD_COUNT + 1)):
        raise ValueError("LuckyDoll record population is incomplete")
    if output[-FOOTER_SIZE:] != source[-FOOTER_SIZE:]:
        raise ValueError("LuckyDoll footer changed")
    return bytes(output), report
