#!/usr/bin/env python3
"""Parse and byte-identically rebuild Prinny DIDT0 DLC containers."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from dataclasses import dataclass, replace
from pathlib import Path


MAGIC = b"DIDT0\0\0\0"
FILE_HEADER_SIZE = 0x40
DLC_TITLE_OFFSET = 0x20
DLC_TITLE_SIZE = 0x20
CHUNK_HEADER = struct.Struct("<4sI8s")

DDEM_RECORD_SIZE = 132
DDEM_SPEAKER_OFFSET = 7
DDEM_SPEAKER_SIZE = 17
DDEM_LINE_OFFSETS = (24, 59, 94)
DDEM_LINE_SIZE = 35

DSTI_SIZE = 0x180
DSTI_HEADER_SIZE = 6
DSTI_SLOT_COUNT = 11
DSTI_SLOT_SIZE = 33
DSTI_FOOTER_SIZE = 15


def _decode_slot(raw: bytes, *, context: str) -> str:
    try:
        terminator = raw.index(0)
    except ValueError as exc:
        raise ValueError(f"{context} has no NUL terminator") from exc
    if any(raw[terminator:]):
        raise ValueError(f"{context} has non-zero bytes after its NUL terminator")
    try:
        return raw[:terminator].decode("cp932", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{context} is not strict CP932: {exc}") from exc


@dataclass(frozen=True)
class Chunk:
    tag: str
    offset: int
    reserved: bytes
    payload: bytes

    def to_bytes(self) -> bytes:
        tag = self.tag.encode("ascii", errors="strict")
        if len(tag) != 4:
            raise ValueError(f"chunk tag must be four ASCII bytes: {self.tag!r}")
        if len(self.reserved) != 8:
            raise ValueError(f"chunk {self.tag} reserved field must be 8 bytes")
        return CHUNK_HEADER.pack(tag, len(self.payload), self.reserved) + self.payload


@dataclass(frozen=True)
class Container:
    header: bytes
    dlc_index: int
    chunks: tuple[Chunk, ...]

    @property
    def title_raw(self) -> bytes:
        return self.header[DLC_TITLE_OFFSET:DLC_TITLE_OFFSET + DLC_TITLE_SIZE]

    @property
    def title(self) -> str:
        return _decode_slot(self.title_raw, context="DIDT0 header title")

    def replace_title_raw(self, title_raw: bytes) -> "Container":
        if len(title_raw) != DLC_TITLE_SIZE:
            raise ValueError(f"DIDT0 header title must be {DLC_TITLE_SIZE} bytes")
        header = bytearray(self.header)
        header[DLC_TITLE_OFFSET:DLC_TITLE_OFFSET + DLC_TITLE_SIZE] = title_raw
        return replace(self, header=bytes(header))

    def chunk(self, tag: str) -> Chunk:
        matches = [chunk for chunk in self.chunks if chunk.tag == tag]
        if len(matches) != 1:
            raise ValueError(f"expected exactly one {tag} chunk, got {len(matches)}")
        return matches[0]

    def replace_chunk_payload(self, tag: str, payload: bytes) -> "Container":
        target = self.chunk(tag)
        chunks = tuple(
            replace(chunk, payload=payload) if chunk is target else chunk
            for chunk in self.chunks
        )
        return replace(self, chunks=chunks)

    def to_bytes(self) -> bytes:
        if len(self.header) != FILE_HEADER_SIZE or self.header[:8] != MAGIC:
            raise ValueError("invalid preserved DIDT0 header")
        output = bytearray(self.header)
        for chunk in self.chunks:
            if chunk.offset != len(output):
                raise ValueError(
                    f"chunk {chunk.tag} offset drifted: expected 0x{chunk.offset:X}, "
                    f"got 0x{len(output):X}"
                )
            output.extend(chunk.to_bytes())
        return bytes(output)


@dataclass(frozen=True)
class DdemRecord:
    index: int
    record_id: int
    raw: bytes

    @property
    def speaker_raw(self) -> bytes:
        return self.raw[DDEM_SPEAKER_OFFSET:DDEM_SPEAKER_OFFSET + DDEM_SPEAKER_SIZE]

    @property
    def lines_raw(self) -> tuple[bytes, bytes, bytes]:
        return tuple(
            self.raw[offset:offset + DDEM_LINE_SIZE]
            for offset in DDEM_LINE_OFFSETS
        )  # type: ignore[return-value]

    @property
    def speaker(self) -> str:
        return _decode_slot(self.speaker_raw, context=f"DDEM {self.record_id:04X} speaker")

    @property
    def lines(self) -> tuple[str, str, str]:
        return tuple(
            _decode_slot(raw, context=f"DDEM {self.record_id:04X} line {index}")
            for index, raw in enumerate(self.lines_raw, 1)
        )  # type: ignore[return-value]


@dataclass(frozen=True)
class DdemTable:
    records: tuple[DdemRecord, ...]
    footer: bytes

    def to_bytes(self) -> bytes:
        return (
            struct.pack("<I", len(self.records))
            + b"".join(record.raw for record in self.records)
            + self.footer
        )


@dataclass(frozen=True)
class DstiTable:
    header: bytes
    slots_raw: tuple[bytes, ...]
    footer: bytes

    @property
    def slots(self) -> tuple[str, ...]:
        return tuple(
            _decode_slot(raw, context=f"DSTI slot {index}")
            for index, raw in enumerate(self.slots_raw)
        )

    def to_bytes(self) -> bytes:
        return self.header + b"".join(self.slots_raw) + self.footer


def parse(data: bytes) -> Container:
    if len(data) < FILE_HEADER_SIZE or data[:8] != MAGIC:
        raise ValueError("not a DIDT0 container")
    header = data[:FILE_HEADER_SIZE]
    dlc_index, = struct.unpack_from("<I", header, 8)
    chunks: list[Chunk] = []
    offset = FILE_HEADER_SIZE
    while offset < len(data):
        if offset + CHUNK_HEADER.size > len(data):
            raise ValueError(f"truncated chunk header at 0x{offset:X}")
        tag_raw, size, reserved = CHUNK_HEADER.unpack_from(data, offset)
        try:
            tag = tag_raw.decode("ascii", errors="strict")
        except UnicodeDecodeError as exc:
            raise ValueError(f"non-ASCII chunk tag at 0x{offset:X}") from exc
        if len(tag) != 4 or not tag.isprintable():
            raise ValueError(f"invalid chunk tag at 0x{offset:X}: {tag_raw.hex()}")
        payload_offset = offset + CHUNK_HEADER.size
        end = payload_offset + size
        if end > len(data):
            raise ValueError(
                f"chunk {tag} exceeds file: end=0x{end:X}, file=0x{len(data):X}"
            )
        chunks.append(Chunk(tag, offset, reserved, data[payload_offset:end]))
        offset = end
        if tag == "NEND":
            if size != 0:
                raise ValueError("NEND payload must be empty")
            break
    if not chunks or chunks[-1].tag != "NEND":
        raise ValueError("DIDT0 container has no terminal NEND chunk")
    if offset != len(data):
        raise ValueError(f"bytes remain after NEND: {len(data) - offset}")
    tags = [chunk.tag for chunk in chunks]
    if len(tags) != len(set(tags)):
        raise ValueError("duplicate DIDT0 chunk tag")
    container = Container(header, dlc_index, tuple(chunks))
    container.title
    return container


def parse_ddem(payload: bytes) -> DdemTable:
    if len(payload) < 4:
        raise ValueError("DDEM payload is too short")
    count, = struct.unpack_from("<I", payload)
    records_end = 4 + count * DDEM_RECORD_SIZE
    if records_end > len(payload):
        raise ValueError(
            f"DDEM count {count} exceeds payload size {len(payload)}"
        )
    records: list[DdemRecord] = []
    previous_id = -1
    for index in range(count):
        offset = 4 + index * DDEM_RECORD_SIZE
        raw = payload[offset:offset + DDEM_RECORD_SIZE]
        record_id, = struct.unpack_from("<H", raw)
        if record_id <= previous_id:
            raise ValueError(f"DDEM IDs are not strictly increasing at record {index}")
        previous_id = record_id
        record = DdemRecord(index, record_id, raw)
        record.speaker
        record.lines
        if raw[129:132] != bytes(3):
            raise ValueError(f"DDEM record {record_id:04X} has a non-zero tail")
        records.append(record)
    footer = payload[records_end:]
    if any(footer):
        raise ValueError(f"DDEM footer is not zero-filled: {footer.hex()}")
    return DdemTable(tuple(records), footer)


def parse_dsti(payload: bytes) -> DstiTable:
    if len(payload) != DSTI_SIZE:
        raise ValueError(f"DSTI payload must be {DSTI_SIZE} bytes, got {len(payload)}")
    slots_end = DSTI_HEADER_SIZE + DSTI_SLOT_COUNT * DSTI_SLOT_SIZE
    slots = tuple(
        payload[offset:offset + DSTI_SLOT_SIZE]
        for offset in range(DSTI_HEADER_SIZE, slots_end, DSTI_SLOT_SIZE)
    )
    table = DstiTable(
        payload[:DSTI_HEADER_SIZE],
        slots,
        payload[slots_end:],
    )
    table.slots
    if len(table.footer) != DSTI_FOOTER_SIZE or any(table.footer):
        raise ValueError("DSTI 15-byte footer is not zero-filled")
    return table


def export_summary(path: Path, source: bytes, container: Container) -> dict[str, object]:
    ddem = parse_ddem(container.chunk("DDEM").payload)
    dsti = parse_dsti(container.chunk("DSTI").payload)
    return {
        "schema_version": 1,
        "source": {
            "path": path.as_posix(),
            "size": len(source),
            "sha256": hashlib.sha256(source).hexdigest(),
        },
        "dlc_index": container.dlc_index,
        "header_title": container.title,
        "chunks": [
            {
                "tag": chunk.tag,
                "offset": f"0x{chunk.offset:08X}",
                "size": len(chunk.payload),
                "reserved_hex": chunk.reserved.hex(),
            }
            for chunk in container.chunks
        ],
        "dsti": {
            "slot_count": len(dsti.slots_raw),
            "nonempty_slots": sum(bool(text) for text in dsti.slots),
        },
        "ddem": {
            "record_count": len(ddem.records),
            "footer_size": len(ddem.footer),
            "record_ids": [f"0x{record.record_id:04X}" for record in ddem.records],
            "nonempty_text_slots": sum(
                bool(text)
                for record in ddem.records
                for text in (record.speaker, *record.lines)
            ),
        },
        "roundtrip": "PASS" if container.to_bytes() == source else "FAIL",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--roundtrip", action="store_true")
    args = parser.parse_args()
    source = args.input.read_bytes()
    container = parse(source)
    if args.roundtrip:
        rebuilt = container.to_bytes()
        if rebuilt != source:
            raise SystemExit("FAIL: DIDT0 round-trip mismatch")
        print(f"OK: byte-identical DIDT0 round-trip ({len(source)} bytes)")
    elif args.json:
        print(json.dumps(export_summary(args.input, source, container), ensure_ascii=False, indent=2))
    else:
        ddem = parse_ddem(container.chunk("DDEM").payload)
        dsti = parse_dsti(container.chunk("DSTI").payload)
        print(
            f"OK: DLC {container.dlc_index}, {len(container.chunks)} chunks, "
            f"DDEM {len(ddem.records)} records, DSTI {len(dsti.slots_raw)} slots"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
