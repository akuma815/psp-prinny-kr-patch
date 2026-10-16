#!/usr/bin/env python3
"""Find exact occurrences of a binary blob below one or more files/directories."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def iter_files(paths: list[Path]):
    for path in paths:
        if path.is_file():
            yield path
        elif path.is_dir():
            yield from (candidate for candidate in path.rglob("*") if candidate.is_file())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("needle", type=Path)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    needle = args.needle.read_bytes()
    if not needle:
        raise ValueError("needle must not be empty")

    rows = []
    files_scanned = 0
    bytes_scanned = 0
    for path in iter_files(args.paths):
        files_scanned += 1
        data = path.read_bytes()
        bytes_scanned += len(data)
        start = 0
        while True:
            offset = data.find(needle, start)
            if offset < 0:
                break
            rows.append({"path": str(path), "offset": offset, "offset_hex": f"0x{offset:X}"})
            start = offset + 1

    report = {
        "needle": str(args.needle),
        "needle_size": len(needle),
        "files_scanned": files_scanned,
        "bytes_scanned": bytes_scanned,
        "matches": rows,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
