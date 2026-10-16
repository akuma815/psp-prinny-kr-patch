#!/usr/bin/env python3
"""Parse and patch Prinny's fixed-slot PictureBook.dat monster encyclopedia."""

from __future__ import annotations

import csv
import struct
from pathlib import Path


RECORD_COUNT = 91
HEADER_SIZE = 6
RECORD_STRIDE = 444
EXPECTED_ROWS = 1386


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != EXPECTED_ROWS:
        raise ValueError(f"unexpected PictureBook row count: {len(rows)}")
    return rows


def patch(
    source: bytes,
    rows: list[dict[str, str]],
    character_map: dict[str, bytes],
) -> tuple[bytes, list[dict[str, object]]]:
    if len(source) < HEADER_SIZE + RECORD_COUNT * RECORD_STRIDE:
        raise ValueError(f"unexpected PictureBook.dat size: {len(source)}")
    if struct.unpack_from("<I", source, 0)[0] != RECORD_COUNT:
        raise ValueError("unexpected PictureBook record count")

    output = bytearray(source)
    report: list[dict[str, object]] = []
    seen: set[tuple[int, int]] = set()
    for row in rows:
        record_index = int(row["record_index"])
        rel_offset = int(row["slot_rel_offset"], 0)
        key = (record_index, rel_offset)
        if key in seen:
            raise ValueError(f"duplicate PictureBook slot: {row['entry_id']}")
        seen.add(key)
        if not 0 <= record_index < RECORD_COUNT:
            raise ValueError(f"invalid PictureBook record index: {record_index}")

        absolute = HEADER_SIZE + record_index * RECORD_STRIDE + rel_offset
        if absolute != int(row["source_offset"], 0):
            raise ValueError(f"{row['entry_id']} offset mismatch")
        max_bytes = int(row["max_bytes"])
        slot_size = max_bytes + 1

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
            continue  # deliberately left untranslated (flags, proper nouns)

        payload = bytearray()
        for character in translation:
            if character in character_map:
                payload.extend(character_map[character])
            else:
                payload.extend(character.encode("cp932", errors="strict"))
        if len(payload) > max_bytes:
            raise ValueError(
                f"{row['entry_id']} exceeds {max_bytes} bytes: {len(payload)}"
            )
        output[absolute:absolute + slot_size] = bytes(payload) + bytes(
            slot_size - len(payload)
        )
        report.append(
            {
                "entry_id": row["entry_id"],
                "offset": f"0x{absolute:05X}",
                "encoded_bytes": len(payload),
                "remaining_bytes": max_bytes - len(payload),
            }
        )
    return bytes(output), report
