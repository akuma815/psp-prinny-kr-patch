#!/usr/bin/env python3
"""Inventory STAGE.DAT .dat payload types and NFG2 four-letter section tags."""

from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

import inspect_nispack


TAG = re.compile(rb"[A-Z][A-Z0-9]{3}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage_dat", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    rows = []
    magic_counts: collections.Counter[str] = collections.Counter()
    tag_counts: collections.Counter[str] = collections.Counter()
    with args.stage_dat.open("rb") as stream:
        for entry in inspect_nispack.read_entries(args.stage_dat):
            if not entry.name.lower().endswith(".dat"):
                continue
            stream.seek(entry.offset)
            data = stream.read(entry.size)
            magic = data[:5].hex()
            magic_counts[magic] += 1
            tags = []
            if data.startswith(b"NFG2"):
                for match in TAG.finditer(data):
                    tag = match.group().decode("ascii")
                    if match.start() % 16 == 0:
                        tags.append({"offset": match.start(), "tag": tag})
                        tag_counts[tag] += 1
            rows.append({"name": entry.name, "size": entry.size, "magic": magic, "tags": tags})
    report = {
        "status": "PASS: STAGE.DAT data-entry and NFG2 tag survey completed",
        "dat_entries": len(rows),
        "magic_counts": dict(magic_counts.most_common()),
        "nfg20_aligned_tag_counts": dict(tag_counts.most_common()),
        "nfg2_entries": sum(row["magic"].startswith("4e464732") for row in rows),
        "non_nfg2": [row for row in rows if not row["magic"].startswith("4e464732")],
        "entries": rows,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(report["status"])
    print(json.dumps({key: report[key] for key in ("dat_entries", "magic_counts", "nfg20_aligned_tag_counts")}, indent=2))
    print(f"nfg2_entries={report['nfg2_entries']} non_nfg2={len(report['non_nfg2'])}")
    print(f"report={args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
