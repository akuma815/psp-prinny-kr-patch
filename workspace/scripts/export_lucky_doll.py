#!/usr/bin/env python3
"""Export and seed the LuckyDoll.dat translation table."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import struct
from pathlib import Path

import decompress_nis_lzs
from build_translated_images_iso import (
    nispack_payload,
    parse_nispack,
    read_start_entries,
)
from lucky_doll import (
    EXPECTED_SIZE,
    FOOTER_SIZE,
    RECORD_COUNT,
    RECORD_OFFSET,
    RECORD_STRIDE,
    TEXT_OFFSET,
    TEXT_PAYLOAD_SIZE,
    TEXT_SLOT_SIZE,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AREA_NAMES = {
    "魔風草原": "마풍 초원",
    "書の大森林": "책의 대삼림",
    "死神の処刑塔": "사신의 처형탑",
    "魔海のアリア": "마해의 아리아",
    "溶岩星の忍砦": "용암성의 닌자 요새",
    "モーブ大要塞": "모브 대요새",
    "黒砂の菓子砂漠": "흑사의 과자 사막",
    "スイーツパレス": "스위츠 팰리스",
    "スイーツガーデン": "스위츠 가든",
}
FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")
TIMED_PATTERN = re.compile(
    r"^(?P<area>.+)【残り(?P<hours>[０-９]+)魔時間】にいたラッキードール。$"
)
TUTORIAL_SOURCE = "チュートリアルステージ２にいたラッキードール。"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_lucky_doll(system_path: Path) -> bytes:
    system = system_path.read_bytes()
    start_entry = next(
        entry for entry in parse_nispack(system) if entry["name"] == "start.lzs"
    )
    start, extension = decompress_nis_lzs.decompress(
        nispack_payload(system, start_entry)
    )
    if extension != "dat":
        raise ValueError(f"unexpected start.lzs extension: {extension}")
    _, entries = read_start_entries(start)
    lucky = next(entry for entry in entries if entry.name == "LuckyDoll.dat")
    return start[lucky.data_start : lucky.data_end]


def seed_translation(source: str) -> str:
    if source == TUTORIAL_SOURCE:
        return "튜토리얼 스테이지 2에 있으면 럭키 돌."
    match = TIMED_PATTERN.fullmatch(source)
    if not match:
        raise ValueError(f"unsupported LuckyDoll source: {source}")
    area = AREA_NAMES[match.group("area")]
    hours = match.group("hours").translate(FULLWIDTH_DIGITS)
    return f"{area}【남은 {hours}마계 시간】에 있으면 럭키 돌."


def preserved_edits(csv_path: Path) -> dict[str, dict[str, str]]:
    if not csv_path.is_file():
        return {}
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {row["entry_id"]: row for row in csv.DictReader(handle)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--system",
        type=Path,
        default=PROJECT_ROOT / "extracted/PSP_GAME/USRDIR/SYSTEM.DAT",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=PROJECT_ROOT / "workspace/text/translation/lucky_doll.csv",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=PROJECT_ROOT / "workspace/text/source/lucky_doll_manifest.json",
    )
    args = parser.parse_args()

    source = extract_lucky_doll(args.system)
    if len(source) != EXPECTED_SIZE:
        raise ValueError(f"unexpected LuckyDoll.dat size: {len(source)}")
    if struct.unpack_from("<I", source, 0)[0] != RECORD_COUNT:
        raise ValueError("unexpected LuckyDoll record count")
    if any(source[-FOOTER_SIZE:]):
        raise ValueError("LuckyDoll footer is not zero-filled")

    previous = preserved_edits(args.csv)
    rows: list[dict[str, object]] = []
    for index in range(RECORD_COUNT):
        record_index = index + 1
        record_offset = RECORD_OFFSET + index * RECORD_STRIDE
        text_offset = record_offset + TEXT_OFFSET
        record_id = struct.unpack_from("<H", source, record_offset)[0]
        slot = source[text_offset : text_offset + TEXT_SLOT_SIZE]
        payload = slot.split(b"\0", 1)[0]
        if not payload or any(slot[len(payload) + 1 :]):
            raise ValueError(f"invalid LuckyDoll string slot: {record_index}")
        ja = payload.decode("cp932", errors="strict")
        entry_id = f"lucky-doll-{record_index:03d}"
        old = previous.get(entry_id)
        seeded = seed_translation(ja)
        if old and old.get("source_bytes") == payload.hex().upper():
            ko = old.get("ko") or seeded
            status = old.get("status") or "draft"
            notes = old.get("notes", "")
        else:
            ko = seeded
            status = "draft"
            notes = ""
        rows.append(
            {
                "entry_id": entry_id,
                "record_index": record_index,
                "record_id": record_id,
                "source_offset": f"0x{text_offset:04X}",
                "max_bytes": TEXT_PAYLOAD_SIZE,
                "source_bytes": payload.hex().upper(),
                "ja": ja,
                "ko": ko,
                "status": status,
                "notes": notes,
            }
        )

    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    manifest = {
        "format": "Prinny LuckyDoll.dat fixed-record string table",
        "source": str(args.system.resolve()),
        "source_sha256": sha256(source),
        "source_size": len(source),
        "record_count": RECORD_COUNT,
        "record_offset": RECORD_OFFSET,
        "record_stride": RECORD_STRIDE,
        "text_offset_in_record": TEXT_OFFSET,
        "text_slot_size": TEXT_SLOT_SIZE,
        "max_payload_bytes": TEXT_PAYLOAD_SIZE,
        "footer_hex": source[-FOOTER_SIZE:].hex(),
        "translation_csv": str(args.csv.resolve()),
        "row_count": len(rows),
        "unique_source_count": len({row["ja"] for row in rows}),
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
