#!/usr/bin/env python3
"""Parse and byte-identically serialize Prinny's MusicShop.dat table.

This tool validates the one supported ULJS00150 baseline.  It intentionally
does not import translated text or rewrite the source file: the three numeric
fields surrounding the strings and the runtime consumer are not understood
well enough to define a safe edit policy yet.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path


ENCODING = "cp932"
HEADER = struct.Struct("<HH")
RECORD = struct.Struct("<HB21s65sBH")
FOOTER = struct.Struct("<I")
SHORT_SLOT_OFFSET = 3
DISPLAY_SLOT_OFFSET = 24


@dataclass(frozen=True)
class FixedString:
    raw: bytes
    text: str
    content_size: int


@dataclass(frozen=True)
class MusicShopRecord:
    index: int
    file_offset: int
    record_index_id: int
    unknown_0: int
    short_name: FixedString
    display_name: FixedString
    unknown_1: int
    unknown_2: int


@dataclass(frozen=True)
class MusicShopFile:
    records: tuple[MusicShopRecord, ...]
    header_unknown: int
    footer: int

    def to_bytes(self) -> bytes:
        output = bytearray(HEADER.pack(len(self.records), self.header_unknown))
        for expected_index, record in enumerate(self.records):
            if record.index != expected_index:
                raise ValueError(
                    f"record index mismatch: expected {expected_index}, "
                    f"got {record.index}"
                )
            _validate_slot(record.short_name, "short_name")
            _validate_slot(record.display_name, "display_name")
            output.extend(
                RECORD.pack(
                    record.record_index_id,
                    record.unknown_0,
                    record.short_name.raw,
                    record.display_name.raw,
                    record.unknown_1,
                    record.unknown_2,
                )
            )
        output.extend(FOOTER.pack(self.footer))
        return bytes(output)


def _parse_slot(raw: bytes, record_index: int, field_name: str) -> FixedString:
    terminator = raw.find(b"\0")
    if terminator < 0:
        raise ValueError(
            f"record {record_index} {field_name} has no NUL terminator"
        )
    if any(raw[terminator + 1 :]):
        raise ValueError(
            f"record {record_index} {field_name} has non-zero bytes after NUL"
        )
    content = raw[:terminator]
    try:
        text = content.decode(ENCODING, errors="strict")
    except UnicodeDecodeError as error:
        raise ValueError(
            f"record {record_index} {field_name} is not valid {ENCODING}: {error}"
        ) from error
    if text.encode(ENCODING, errors="strict") != content:
        raise ValueError(
            f"record {record_index} {field_name} is not byte-reversible {ENCODING}"
        )
    return FixedString(raw=raw, text=text, content_size=len(content))


def _validate_slot(slot: FixedString, field_name: str) -> None:
    expected_size = 21 if field_name == "short_name" else 65
    if len(slot.raw) != expected_size:
        raise ValueError(
            f"{field_name} slot must be {expected_size} bytes, got {len(slot.raw)}"
        )
    reparsed = _parse_slot(slot.raw, -1, field_name)
    if reparsed.text != slot.text or reparsed.content_size != slot.content_size:
        raise ValueError(f"{field_name} protected raw bytes and decoded text differ")


def parse(data: bytes) -> MusicShopFile:
    if len(data) < HEADER.size + FOOTER.size:
        raise ValueError("MusicShop.dat is too short for its header and footer")
    count, header_unknown = HEADER.unpack_from(data, 0)
    expected_size = HEADER.size + count * RECORD.size + FOOTER.size
    if len(data) != expected_size:
        raise ValueError(
            f"MusicShop.dat size mismatch: count={count} requires "
            f"{expected_size} bytes, got {len(data)}"
        )

    records: list[MusicShopRecord] = []
    for index in range(count):
        offset = HEADER.size + index * RECORD.size
        (
            record_index_id,
            unknown_0,
            short_raw,
            display_raw,
            unknown_1,
            unknown_2,
        ) = RECORD.unpack_from(data, offset)
        records.append(
            MusicShopRecord(
                index=index,
                file_offset=offset,
                record_index_id=record_index_id,
                unknown_0=unknown_0,
                short_name=_parse_slot(short_raw, index, "short_name"),
                display_name=_parse_slot(display_raw, index, "display_name"),
                unknown_1=unknown_1,
                unknown_2=unknown_2,
            )
        )

    footer = FOOTER.unpack_from(data, expected_size - FOOTER.size)[0]
    return MusicShopFile(
        records=tuple(records), header_unknown=header_unknown, footer=footer
    )


def _slot_json(slot: FixedString, slot_offset: int) -> dict[str, object]:
    return {
        "slot_offset": slot_offset,
        "slot_size": len(slot.raw),
        "raw_hex": slot.raw.hex(),
        "text": slot.text,
        "content_size": slot.content_size,
        "terminator_offset": slot.content_size,
        "padding_size": len(slot.raw) - slot.content_size - 1,
    }


def export_json(path: Path, source: bytes, table: MusicShopFile) -> dict[str, object]:
    return {
        "schema_version": 1,
        "asset_id": "asset/text/music-shop",
        "source": {
            "path": path.as_posix(),
            "size": len(source),
            "sha256": hashlib.sha256(source).hexdigest(),
            "encoding": ENCODING,
        },
        "layout": {
            "endian": "little",
            "header_size": HEADER.size,
            "header_unknown": table.header_unknown,
            "record_count": len(table.records),
            "record_size": RECORD.size,
            "footer_size": FOOTER.size,
            "footer_raw_hex": FOOTER.pack(table.footer).hex(),
        },
        "entries": [
            {
                "entry_id": f"music-shop/{record.record_index_id:04d}",
                "index": record.index,
                "file_offset": f"0x{record.file_offset:08X}",
                "record_index_id": record.record_index_id,
                "unknown_0": record.unknown_0,
                "short_name": _slot_json(record.short_name, SHORT_SLOT_OFFSET),
                "display_name": _slot_json(
                    record.display_name, DISPLAY_SLOT_OFFSET
                ),
                "unknown_1": record.unknown_1,
                "unknown_2": record.unknown_2,
            }
            for record in table.records
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--json", action="store_true", help="print protected JSON")
    mode.add_argument(
        "--roundtrip", action="store_true", help="require byte-identical serialization"
    )
    args = parser.parse_args()

    source = args.input.read_bytes()
    table = parse(source)
    rebuilt = table.to_bytes()
    if rebuilt != source:
        raise SystemExit("ERROR: parse -> serialize differs from source bytes")

    digest = hashlib.sha256(source).hexdigest()
    if args.json:
        print(
            json.dumps(
                export_json(args.input, source, table),
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.roundtrip:
        print(
            f"PASS: byte-identical roundtrip; records={len(table.records)}, "
            f"size={len(source)}, sha256={digest}"
        )
    else:
        max_short = max((item.short_name.content_size for item in table.records), default=0)
        max_display = max(
            (item.display_name.content_size for item in table.records), default=0
        )
        print(
            f"OK: records={len(table.records)}, record_size={RECORD.size}, "
            f"header_unknown=0x{table.header_unknown:04X}, "
            f"footer=0x{table.footer:08X}, sha256={digest}"
        )
        print(
            f"slots: short_name=21 bytes (max used {max_short}), "
            f"display_name=65 bytes (max used {max_display})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
