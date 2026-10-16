#!/usr/bin/env python3
"""Export LuckyItem/MusicShop/Collection/Honor string tables to translation CSVs.

Layouts (verified 2026-07-29 against work/system/start.dat):
  LuckyItem.dat  header 6, 60 records x 92B: name(21B slot), desc(65B slot)
  Collection.dat header 6, 60 records x 72B: desc(66B slot)
  Honor.dat      header 6, 30 records x 204B: title(65B), line1(65B), line2(66B)
  MusicShop.dat  header 4, 30 records x 92B: short(21B at +3), title(65B at +24)

Slot budget (max_bytes) is slot size minus the mandatory NUL.  Trailing
per-record numeric fields and file footers are not exported.
"""

from __future__ import annotations

import argparse
import csv
import json
import struct
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

TABLES: dict[str, dict[str, object]] = {
    "LuckyItem.dat": {
        "csv": "lucky_item.csv",
        "header": 6,
        "records": 60,
        "stride": 92,
        "slots": [("name", 0x00, 21), ("desc", 0x15, 65)],
    },
    "MusicShop.dat": {
        "csv": "music_shop.csv",
        "header": 4,
        "records": 30,
        "stride": 92,
        "slots": [("short", 0x03, 21), ("title", 0x18, 65)],
    },
    "Collection.dat": {
        "csv": "collection.csv",
        "header": 6,
        "records": 60,
        "stride": 72,
        "slots": [("desc", 0x00, 66)],
    },
    "Honor.dat": {
        "csv": "honor.csv",
        "header": 6,
        "records": 30,
        "stride": 204,
        "slots": [("title", 0x00, 65), ("line1", 0x41, 65), ("line2", 0x82, 66)],
    },
}

# Terms already fixed by existing project translations.
GLOSSARY: dict[str, str] = {
    "魔界レコード": "마계 레코드",
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--start", type=Path, default=PROJECT_ROOT / "work/system/start.dat"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "workspace/text/translation",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_ROOT / "work/analysis/start_tables_export.json",
    )
    args = parser.parse_args()

    summary = {}
    for member, spec in TABLES.items():
        data = read_start_member(args.start, member)
        header = int(spec["header"])
        records = int(spec["records"])
        stride = int(spec["stride"])
        declared = struct.unpack_from("<I" if header == 6 else "<H", data)[0]
        if declared != records:
            raise ValueError(f"{member}: unexpected record count {declared}")
        rows = []
        for index in range(records):
            base = header + index * stride
            for field, rel, slot_size in spec["slots"]:  # type: ignore[misc]
                slot = data[base + rel:base + rel + slot_size]
                payload = slot.split(b"\x00")[0]
                if not payload:
                    continue
                text = payload.decode("cp932")
                ko = GLOSSARY.get(text, "")
                rows.append(
                    {
                        "entry_id": f"{spec['csv'][:-4]}/{index:03d}/{field}",
                        "record_index": index,
                        "field": field,
                        "slot_rel_offset": f"0x{rel:03X}",
                        "source_offset": f"0x{base + rel:05X}",
                        "max_bytes": slot_size - 1,
                        "source_bytes": len(payload),
                        "ja": text,
                        "ko": ko,
                        "status": "glossary" if ko else "todo",
                        "notes": "",
                    }
                )
        output = args.output_dir / str(spec["csv"])
        with output.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        unique_ja = len({row["ja"] for row in rows})
        summary[member] = {
            "csv": str(output),
            "rows": len(rows),
            "unique_ja": unique_ja,
            "prefilled": sum(1 for row in rows if row["ko"]),
        }

    report = {
        "schema_version": 1,
        "gate_id": "START-TABLES-EXPORT-001",
        "status": "PASS",
        "tables": summary,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
