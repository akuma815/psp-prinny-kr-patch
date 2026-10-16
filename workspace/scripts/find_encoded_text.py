#!/usr/bin/env python3
"""Find encoded text bytes in files or directory trees."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def iter_files(paths: list[Path]):
    for path in paths:
        if path.is_file():
            yield path
        elif path.is_dir():
            yield from (candidate for candidate in path.rglob("*") if candidate.is_file())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("text")
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--encoding", default="cp932")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--context", type=int, default=128)
    args = parser.parse_args()

    needle = args.text.encode(args.encoding, errors="strict")
    matches: list[dict[str, object]] = []
    scanned_files = 0
    scanned_bytes = 0
    for path in iter_files(args.paths):
        try:
            data = path.read_bytes()
        except OSError:
            continue
        scanned_files += 1
        scanned_bytes += len(data)
        cursor = 0
        while True:
            offset = data.find(needle, cursor)
            if offset < 0:
                break
            matches.append({
                "path": str(path),
                "offset": f"0x{offset:X}",
                "size": len(needle),
                "context": data[
                    max(0, data.rfind(b"\0", max(0, offset - args.context), offset) + 1):
                    min(
                        len(data),
                        (
                            data.find(
                                b"\0",
                                offset + len(needle),
                                min(len(data), offset + len(needle) + args.context),
                            )
                        )
                        if data.find(
                            b"\0",
                            offset + len(needle),
                            min(len(data), offset + len(needle) + args.context),
                        ) >= 0
                        else offset + len(needle) + args.context
                    )
                ].decode(args.encoding, errors="replace"),
            })
            cursor = offset + 1

    report = {
        "status": "PASS",
        "text": args.text,
        "encoding": args.encoding,
        "needle_hex": needle.hex().upper(),
        "scanned_files": scanned_files,
        "scanned_bytes": scanned_bytes,
        "match_count": len(matches),
        "matches": matches,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    sys.stdout.buffer.write(rendered.encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
