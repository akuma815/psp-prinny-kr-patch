#!/usr/bin/env python3
"""Inspect and byte-identically validate Prinny's Demo00.dat message table."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path


HEADER = struct.Struct("<I")
RECORD_SIZE = 132
FOOTER_SIZE = 12
SPEAKER_SIZE = 17
LINE_SIZE = 35
LINE_OFFSETS = (24, 59, 94)


def _decode_slot(raw: bytes) -> str:
    payload, separator, padding = raw.partition(b"\0")
    if separator and any(padding):
        raise ValueError("fixed string has non-zero bytes after its terminator")
    return payload.decode("cp932")


@dataclass(frozen=True)
class Record:
    index: int
    record_id: int
    control_2: int
    unknown_3: int
    value_4: int
    speaker_control: int
    speaker_raw: bytes
    lines_raw: tuple[bytes, bytes, bytes]
    tail: bytes

    @property
    def speaker(self) -> str:
        return _decode_slot(self.speaker_raw)

    @property
    def lines(self) -> tuple[str, str, str]:
        return tuple(_decode_slot(raw) for raw in self.lines_raw)  # type: ignore[return-value]

    def to_bytes(self) -> bytes:
        output = bytearray(RECORD_SIZE)
        struct.pack_into(
            "<HBBhB", output, 0, self.record_id, self.control_2,
            self.unknown_3, self.value_4, self.speaker_control,
        )
        output[7:24] = self.speaker_raw
        for offset, raw in zip(LINE_OFFSETS, self.lines_raw):
            output[offset:offset + LINE_SIZE] = raw
        output[129:132] = self.tail
        return bytes(output)


@dataclass(frozen=True)
class Table:
    records: tuple[Record, ...]
    footer: bytes

    def to_bytes(self) -> bytes:
        return HEADER.pack(len(self.records)) + b"".join(
            record.to_bytes() for record in self.records
        ) + self.footer


def parse(data: bytes) -> Table:
    if len(data) < HEADER.size + FOOTER_SIZE:
        raise ValueError("Demo00.dat is too short")
    count, = HEADER.unpack_from(data)
    expected = HEADER.size + count * RECORD_SIZE + FOOTER_SIZE
    if len(data) != expected:
        raise ValueError(
            f"Demo00.dat size mismatch: count={count} requires {expected}, got {len(data)}"
        )
    records = []
    previous_id = -1
    for index in range(count):
        offset = HEADER.size + index * RECORD_SIZE
        raw = data[offset:offset + RECORD_SIZE]
        record_id, control_2, unknown_3, value_4, speaker_control = struct.unpack_from(
            "<HBBhB", raw
        )
        if record_id <= previous_id:
            raise ValueError(f"record IDs are not strictly increasing at index {index}")
        previous_id = record_id
        speaker_raw = raw[7:24]
        lines_raw = tuple(raw[start:start + LINE_SIZE] for start in LINE_OFFSETS)
        _decode_slot(speaker_raw)
        for line in lines_raw:
            _decode_slot(line)
        tail = raw[129:132]
        if tail != bytes(3):
            raise ValueError(f"record {index} has a non-zero tail")
        records.append(Record(
            index, record_id, control_2, unknown_3, value_4,
            speaker_control, speaker_raw, lines_raw, tail,
        ))
    footer = data[-FOOTER_SIZE:]
    if footer != bytes(FOOTER_SIZE):
        raise ValueError(f"unexpected non-zero footer: {footer.hex()}")
    return Table(tuple(records), footer)


def export(path: Path, source: bytes, table: Table) -> dict[str, object]:
    return {
        "schema_version": 1,
        "asset_id": "asset/text/demo00",
        "source": {
            "path": path.as_posix(),
            "size": len(source),
            "sha256": hashlib.sha256(source).hexdigest(),
        },
        "layout": {
            "endian": "little",
            "record_count": len(table.records),
            "record_size": RECORD_SIZE,
            "speaker_size": SPEAKER_SIZE,
            "line_size": LINE_SIZE,
            "line_offsets": list(LINE_OFFSETS),
            "footer_size": FOOTER_SIZE,
        },
        "entries": [
            {
                "entry_id": f"demo00/{record.record_id:04X}",
                "index": record.index,
                "file_offset": f"0x{HEADER.size + record.index * RECORD_SIZE:08X}",
                "record_id": record.record_id,
                "control_2": record.control_2,
                "unknown_3": record.unknown_3,
                "value_4": record.value_4,
                "speaker_control": record.speaker_control,
                "speaker": record.speaker,
                "lines": list(record.lines),
            }
            for record in table.records
        ],
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
        if table.to_bytes() != source:
            raise SystemExit("FAIL: round-trip mismatch")
        print(f"OK: byte-identical round-trip ({len(source)} bytes)")
    elif args.json:
        # ASCII escapes keep JSON export reliable on the Korean Windows CP949 console.
        print(json.dumps(export(args.input, source, table), ensure_ascii=True, indent=2))
    else:
        print(f"OK: {len(table.records)} records x {RECORD_SIZE} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
