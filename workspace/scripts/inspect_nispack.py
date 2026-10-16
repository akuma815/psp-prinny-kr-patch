#!/usr/bin/env python3
"""Validate, list, or extract entries from the observed NISPACK archives."""

from __future__ import annotations

import argparse
import json
import struct
from dataclasses import asdict, dataclass
from pathlib import Path


SIGNATURE = b"NISPACK\0\0\0\0\0"
ENTRY = struct.Struct("<32sIII")


@dataclass(frozen=True)
class Entry:
    index: int
    name: str
    offset: int
    size: int
    unknown: int


def read_entries(path: Path) -> list[Entry]:
    file_size = path.stat().st_size
    with path.open("rb") as stream:
        if stream.read(len(SIGNATURE)) != SIGNATURE:
            raise ValueError(f"not a NISPACK archive: {path}")
        count_raw = stream.read(4)
        if len(count_raw) != 4:
            raise ValueError("truncated NISPACK entry count")
        count = struct.unpack("<I", count_raw)[0]
        if len(SIGNATURE) + 4 + count * ENTRY.size > file_size:
            raise ValueError("entry table extends beyond end of file")

        entries: list[Entry] = []
        for index in range(count):
            raw = stream.read(ENTRY.size)
            if len(raw) != ENTRY.size:
                raise ValueError(f"truncated entry record {index}")
            name_raw, offset, size, unknown = ENTRY.unpack(raw)
            name = name_raw.split(b"\0", 1)[0].decode("ascii", errors="strict")
            if not name or Path(name).name != name:
                raise ValueError(f"unsafe or empty entry name at index {index}: {name!r}")
            if offset > file_size or size > file_size - offset:
                raise ValueError(
                    f"entry {index} is outside archive: "
                    f"offset=0x{offset:X}, size={size}"
                )
            entries.append(Entry(index, name, offset, size, unknown))

    ordered = sorted(entries, key=lambda item: item.offset)
    for previous, current in zip(ordered, ordered[1:]):
        if previous.offset + previous.size > current.offset:
            raise ValueError(
                f"overlapping entries: {previous.name!r} and {current.name!r}"
            )
    return entries


def extract(path: Path, entry: Entry, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / entry.name
    with path.open("rb") as source:
        source.seek(entry.offset)
        data = source.read(entry.size)
    if len(data) != entry.size:
        raise ValueError(f"short read while extracting {entry.name!r}")
    destination.write_bytes(data)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--json", action="store_true", help="print JSON inventory")
    parser.add_argument("--extract", metavar="NAME", help="extract one named entry")
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    args = parser.parse_args()

    entries = read_entries(args.archive)
    if args.extract:
        selected = next((item for item in entries if item.name == args.extract), None)
        if selected is None:
            raise SystemExit(f"entry not found: {args.extract}")
        destination = extract(args.archive, selected, args.output_dir)
        print(f"OK: extracted {selected.name} -> {destination} ({selected.size} bytes)")
    elif args.json:
        print(json.dumps([asdict(item) for item in entries], indent=2))
    else:
        print(f"OK: {args.archive} contains {len(entries)} non-overlapping entries")
        for item in entries:
            print(
                f"{item.index:4d}  0x{item.offset:08X}  {item.size:10d}  "
                f"0x{item.unknown:08X}  {item.name}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
