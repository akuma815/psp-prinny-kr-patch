#!/usr/bin/env python3
"""Inspect and byte-identically validate Prinny's BaseTalk.dat table."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path


HEADER = struct.Struct("<HH")
RECORD = struct.Struct("<HH12I")
FOOTER_SIZE = 12


@dataclass(frozen=True)
class Record:
    index: int
    record_id: int
    unknown: int
    script_keys: tuple[int, ...]

    @property
    def script_addresses(self) -> tuple[int, ...]:
        """Deprecated compatibility alias; the values are resolver keys, not addresses."""
        return self.script_keys


@dataclass(frozen=True)
class Table:
    count: int
    header_unknown: int
    records: tuple[Record, ...]
    footer: bytes

    def to_bytes(self) -> bytes:
        output = bytearray(HEADER.pack(self.count, self.header_unknown))
        for record in self.records:
            output.extend(
                RECORD.pack(
                    record.record_id,
                    record.unknown,
                    *record.script_keys,
                )
            )
        output.extend(self.footer)
        return bytes(output)


def parse(data: bytes) -> Table:
    if len(data) < HEADER.size + FOOTER_SIZE:
        raise ValueError("BaseTalk.dat is too short")
    count, header_unknown = HEADER.unpack_from(data)
    expected = HEADER.size + count * RECORD.size + FOOTER_SIZE
    if len(data) != expected:
        raise ValueError(
            f"BaseTalk.dat size mismatch: count={count} requires {expected}, got {len(data)}"
        )
    records = []
    for index in range(count):
        values = RECORD.unpack_from(data, HEADER.size + index * RECORD.size)
        records.append(Record(index, values[0], values[1], tuple(values[2:])))
    footer = data[-FOOTER_SIZE:]
    if footer != bytes(FOOTER_SIZE):
        raise ValueError(f"unexpected non-zero footer: {footer.hex()}")
    return Table(count, header_unknown, tuple(records), footer)


def export(path: Path, source: bytes, table: Table) -> dict[str, object]:
    return {
        "schema_version": 1,
        "asset_id": "asset/script/base-talk",
        "source": {
            "path": path.as_posix(),
            "size": len(source),
            "sha256": hashlib.sha256(source).hexdigest(),
        },
        "layout": {
            "endian": "little",
            "header_size": HEADER.size,
            "record_count": table.count,
            "record_size": RECORD.size,
            "footer_size": FOOTER_SIZE,
        },
        "entries": [
            {
                "entry_id": f"base-talk/{record.record_id:04d}",
                "index": record.index,
                "file_offset": f"0x{HEADER.size + record.index * RECORD.size:08X}",
                "record_id": record.record_id,
                "unknown": record.unknown,
                "script_keys": [f"0x{value:08X}" for value in record.script_keys],
            }
            for record in table.records
        ],
        "footer_raw_hex": table.footer.hex(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--json", action="store_true")
    group.add_argument("--roundtrip", action="store_true")
    args = parser.parse_args()

    source = args.input.read_bytes()
    table = parse(source)
    if args.roundtrip:
        rebuilt = table.to_bytes()
        if rebuilt != source:
            raise SystemExit("FAIL: round-trip mismatch")
        print(f"OK: byte-identical round-trip ({len(source)} bytes)")
    elif args.json:
        print(json.dumps(export(args.input, source, table), indent=2))
    else:
        ids = ", ".join(str(record.record_id) for record in table.records)
        print(
            f"OK: {table.count} records x {RECORD.size} bytes; "
            f"header_unknown={table.header_unknown}; ids=[{ids}]"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
