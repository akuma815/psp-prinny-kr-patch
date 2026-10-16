#!/usr/bin/env python3
"""Inspect and extract the observed decompressed start.dat index.

The header's second word is the first file's start.  Each index record's final
word is that record's end (and therefore the next record's start).  A zero end
on the final record means EOF.
"""

from __future__ import annotations

import argparse
import json
import struct
from dataclasses import asdict, dataclass
from pathlib import Path


HEADER = struct.Struct("<II")
ENTRY = struct.Struct("<16sIIII")


@dataclass
class Entry:
    index: int
    name: str
    unknown_0: int
    unknown_1: int
    unknown_2: int
    data_start: int
    data_end: int
    span: int


def read_entries(path: Path) -> tuple[int, list[Entry]]:
    file_size = path.stat().st_size
    with path.open("rb") as stream:
        header = stream.read(HEADER.size)
        if len(header) != HEADER.size:
            raise ValueError("start.dat header is truncated")
        count, data_marker = HEADER.unpack(header)
        table_end = HEADER.size + count * ENTRY.size
        if table_end > file_size:
            raise ValueError("start.dat index extends beyond end of file")

        entries: list[Entry] = []
        for index in range(count):
            raw = stream.read(ENTRY.size)
            if len(raw) != ENTRY.size:
                raise ValueError(f"truncated start.dat index record {index}")
            name_raw, unknown_0, unknown_1, unknown_2, data_end_raw = ENTRY.unpack(raw)
            name = name_raw.split(b"\0", 1)[0].decode("ascii", errors="strict")
            if not name or Path(name).name != name:
                raise ValueError(f"unsafe or empty name in index record {index}")
            data_end = file_size if data_end_raw == 0 and index == count - 1 else data_end_raw
            data_start = data_marker if index == 0 else entries[-1].data_end
            if data_start < table_end or data_start > file_size:
                raise ValueError(
                    f"record {index} has invalid start: 0x{data_start:X}"
                )
            if data_end < data_start or data_end > file_size:
                raise ValueError(
                    f"record {index} has invalid end: 0x{data_end:X}"
                )
            entries.append(
                Entry(
                    index,
                    name,
                    unknown_0,
                    unknown_1,
                    unknown_2,
                    data_start,
                    data_end,
                    data_end - data_start,
                )
            )
    return data_marker, entries


def extract(path: Path, entry: Entry, output_dir: Path) -> Path:
    if entry.span <= 0:
        raise ValueError(f"entry has no usable data span: {entry.name}")
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / entry.name
    with path.open("rb") as source:
        source.seek(entry.data_start)
        data = source.read(entry.span)
    if len(data) != entry.span:
        raise ValueError(f"short read while extracting {entry.name}")
    destination.write_bytes(data)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--extract", metavar="NAME")
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    args = parser.parse_args()

    data_marker, entries = read_entries(args.archive)
    if args.extract:
        selected = next((item for item in entries if item.name == args.extract), None)
        if selected is None:
            raise SystemExit(f"entry not found: {args.extract}")
        destination = extract(args.archive, selected, args.output_dir)
        print(
            f"OK: extracted analysis span for {selected.name} -> {destination} "
            f"({selected.span} bytes, 0x{selected.data_start:X}..0x{selected.data_end:X})"
        )
    elif args.json:
        print(
            json.dumps(
                {"data_marker": data_marker, "entries": [asdict(x) for x in entries]},
                indent=2,
            )
        )
    else:
        print(
            f"OK: {args.archive} contains {len(entries)} index records; "
            f"data marker=0x{data_marker:X}"
        )
        for item in entries:
            print(
                f"{item.index:4d}  0x{item.data_start:08X}..0x{item.data_end:08X}  "
                f"{item.span:>10}  "
                f"{item.name}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
