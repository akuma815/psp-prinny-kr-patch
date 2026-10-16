#!/usr/bin/env python3
"""Export PictureBook.dat (91 monster encyclopedia records) to a translation CSV.

Layout (verified 2026-07-29):
  header 6 bytes (record count 0x5B + 0x0001), then 91 records x 444 bytes.
  Each record is a table of fixed NUL-terminated CP932 string slots; the
  canonical slot start offsets are derived from the union of string starts
  across all records.  Trailing per-record bytes (flags) are not exported.

The ko column is pre-filled for the name slot (slot 0) from an editorial
glossary that follows existing project translations; everything else is left
empty for manual translation.  max_bytes is the hard insertion budget
(slot size minus the mandatory NUL).
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

HEADER_SIZE = 6
RECORD_COUNT = 91
RECORD_STRIDE = 444
# String area within a record; 0x1B6.. holds non-string flag bytes.
STRING_AREA_END = 0x1B6

# Name pre-translations.  basis "existing" = same term already used in
# stage_info.csv / lucky_doll.csv / boot_ui_translation.json / demo00
# translations; basis "draft" = new transliteration, review recommended.
NAME_KO: dict[int, tuple[str, str, str]] = {
    0: ("모브 병사", "existing", ""),
    1: ("빅 아이", "draft", ""),
    2: ("백베어드", "existing", ""),
    3: ("하급 닌자", "draft", "下忍"),
    4: ("마스터 섀도우", "draft", ""),
    5: ("우드 포크", "draft", ""),
    6: ("트렌트", "draft", ""),
    7: ("시공 암흑검", "draft", ""),
    8: ("럭키 돌", "existing", ""),
    9: ("좀비 돌", "existing", ""),
    10: ("콘 워크", "draft", ""),
    11: ("콘 킹", "existing", ""),
    12: ("저글러 헤드", "existing", ""),
    13: ("레드 아이돌", "draft", ""),
    14: ("아이돌3", "draft", ""),
    15: ("스펙터", "draft", ""),
    16: ("스펙터 마미", "draft", ""),
    17: ("스펙타", "draft", "スペクター+太 말장난"),
    18: ("임프", "draft", ""),
    19: ("그렘린", "draft", ""),
    20: ("아가시온", "draft", ""),
    21: ("커먼 그리모어", "draft", ""),
    22: ("리프트 거너", "draft", ""),
    23: ("고스트 프루트", "draft", ""),
    24: ("고스트 봄버", "draft", ""),
    25: ("타르맨", "draft", ""),
    26: ("아처", "draft", ""),
    27: ("마계 허수아비", "existing", ""),
    28: ("마법사", "draft", ""),
    29: ("가고일", "existing", ""),
    30: ("가고일 스리", "existing", ""),
    31: ("메탈 골렘", "draft", ""),
    32: ("터미네이터", "draft", ""),
    33: ("네코 사벨", "draft", "猫+サーベル 말장난"),
    34: ("모스맨", "draft", ""),
    35: ("언노운", "draft", ""),
    36: ("모브 총사병", "draft", ""),
    37: ("좀비", "existing", ""),
    38: ("유령♂", "draft", "オバケ"),
    39: ("유령♀", "draft", "オバケ"),
    40: ("모브 포격병", "draft", ""),
    41: ("만드라고라", "draft", ""),
    42: ("만드라 히어로", "draft", ""),
    43: ("봄버 헤드", "draft", ""),
    44: ("드루이드", "draft", ""),
    45: ("통 몬스터", "draft", "タル=통(기존 번역)"),
    46: ("마법 양탄자", "existing", ""),
    47: ("서큐버스", "draft", ""),
    48: ("릴림", "draft", ""),
    49: ("데몬", "existing", ""),
    50: ("구르메 오거", "existing", "2026-07-29 demo00의 '미식 오거'를 구르메 오거로 통일 완료"),
    51: ("파프리카", "existing", ""),
    52: ("나츠", "existing", ""),
    53: ("메그", "existing", ""),
    54: ("카르다몬", "existing", ""),
    55: ("세사미", "existing", "2026-07-29 boot UI의 '세서미'를 세사미로 통일 완료"),
    56: ("아니스", "existing", ""),
    57: ("요리의 철거인", "existing", ""),
    58: ("터메릭", "existing", ""),
    59: ("바쿠치", "existing", ""),
    60: ("호시카게", "existing", "boot UI에는 'VS 별빛' 표기 불일치 있음"),
    61: ("리샹롱", "existing", ""),
    62: ("모건", "existing", ""),
    63: ("다스 모브", "existing", ""),
    64: ("에트나", "existing", ""),
    65: ("프리니", "existing", ""),
    66: ("프리니 라하르", "existing", ""),
    67: ("프리니 바알", "existing", ""),
    68: ("아사기", "existing", ""),
    69: ("프리니 아사기", "existing", ""),
    70: ("스위츠 남작", "existing", ""),
    71: ("사이클롭스", "existing", ""),
    72: ("로젠가르텐", "existing", ""),
    73: ("프로슈", "existing", ""),
    74: ("트로켄", "existing", ""),
    75: ("부활의 말뚝", "existing", ""),
    76: ("통", "existing", ""),
    77: ("폭탄", "existing", ""),
    78: ("푸딩", "existing", ""),
    79: ("쇼트케이크", "existing", ""),
    80: ("파르페", "existing", ""),
    81: ("아이스바", "existing", ""),
    82: ("속죄의 말뚝", "existing", ""),
    83: ("튜토리얼 가게", "existing", ""),
    84: ("기록소", "existing", ""),
    85: ("음악실", "existing", ""),
    86: ("리플레이", "existing", ""),
    87: ("럭키 교수", "existing", ""),
    88: ("야반도주", "existing", ""),
    89: ("시공 안내인", "existing", ""),
    90: ("저장가게", "existing", ""),
}


def read_start_member(start_path: Path, member: str) -> bytes:
    import build_direct_run as bdr

    start = start_path.read_bytes()
    _, entries = bdr.read_start_entries(start)
    by_name = {entry.name: entry for entry in entries}
    if member not in by_name:
        raise ValueError(f"start.dat has no member {member}")
    entry = by_name[member]
    return start[entry.data_start:entry.data_end]


def record_string_starts(record: bytes) -> list[int]:
    starts = []
    position = 0
    while position < STRING_AREA_END:
        if record[position] != 0:
            starts.append(position)
            end = record.find(b"\x00", position, STRING_AREA_END)
            position = end if end >= 0 else STRING_AREA_END
        else:
            position += 1
    return starts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--start",
        type=Path,
        default=PROJECT_ROOT / "work/system/start.dat",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "workspace/text/translation/picture_book.csv",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_ROOT / "work/analysis/picture_book_export.json",
    )
    args = parser.parse_args()

    data = read_start_member(args.start, "PictureBook.dat")
    if len(data) < HEADER_SIZE + RECORD_COUNT * RECORD_STRIDE:
        raise ValueError("PictureBook.dat is smaller than the expected layout")
    declared = int.from_bytes(data[0:4], "little")
    if declared != RECORD_COUNT:
        raise ValueError(f"unexpected record count: {declared}")

    records = [
        data[HEADER_SIZE + i * RECORD_STRIDE:HEADER_SIZE + (i + 1) * RECORD_STRIDE]
        for i in range(RECORD_COUNT)
    ]
    canonical = sorted({s for record in records for s in record_string_starts(record)})
    boundaries = canonical + [STRING_AREA_END]

    rows = []
    misaligned = []
    for index, record in enumerate(records):
        for start in record_string_starts(record):
            if start not in canonical:
                misaligned.append((index, hex(start)))
    if misaligned:
        raise ValueError(f"string starts outside canonical slots: {misaligned[:10]}")

    skipped_binary = []
    for index, record in enumerate(records):
        for slot_index, slot_start in enumerate(canonical):
            slot_end = boundaries[boundaries.index(slot_start) + 1]
            payload = record[slot_start:slot_end].split(b"\x00")[0]
            if not payload:
                continue
            try:
                text = payload.decode("cp932")
            except UnicodeDecodeError:
                # e.g. record 37 rel 0xE4 holds binary bytes, not a string
                skipped_binary.append(
                    {"record_index": index, "offset": f"0x{slot_start:03X}"}
                )
                continue
            if any(character < " " for character in text):
                # rel 0x011 / 0xE4 hold one-byte record flags, not text
                skipped_binary.append(
                    {"record_index": index, "offset": f"0x{slot_start:03X}"}
                )
                continue
            absolute = HEADER_SIZE + index * RECORD_STRIDE + slot_start
            ko, status, note = "", "todo", ""
            if slot_index == 0 and index in NAME_KO:
                ko, basis, note = NAME_KO[index]
                status = f"name-{basis}"
            rows.append(
                {
                    "entry_id": f"picture_book/{index:03d}/{slot_start:03X}",
                    "record_index": index,
                    "slot_index": slot_index,
                    "slot_rel_offset": f"0x{slot_start:03X}",
                    "source_offset": f"0x{absolute:05X}",
                    "max_bytes": slot_end - slot_start - 1,
                    "source_bytes": len(payload),
                    "ja": text,
                    "ko": ko,
                    "status": status,
                    "notes": note,
                }
            )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    report = {
        "schema_version": 1,
        "gate_id": "PICTURE-BOOK-EXPORT-001",
        "status": "PASS",
        "records": RECORD_COUNT,
        "record_stride": RECORD_STRIDE,
        "canonical_slots": [f"0x{s:03X}" for s in canonical],
        "rows": len(rows),
        "name_rows_prefilled": sum(
            1 for row in rows if str(row["status"]).startswith("name-")
        ),
        "skipped_binary_slots": skipped_binary,
        "output": str(args.output),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
