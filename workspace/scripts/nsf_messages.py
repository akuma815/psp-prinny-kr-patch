#!/usr/bin/env python3
"""Catalog Demo00 message-reference candidates in Prinny's demo.nsf code region."""

from __future__ import annotations

import argparse
import json
import struct
from dataclasses import dataclass
from pathlib import Path

import demo00
import nsf_links


ARG_SIZES = {0: 1, 1: 1, 2: 2, 3: 3, 4: 4}
MESSAGE_OPCODES = (1, 2, 3)


@dataclass(frozen=True)
class Operand:
    tag: int
    raw: bytes
    value: int | None


@dataclass(frozen=True)
class Reference:
    logical_offset: int
    file_offset: int
    opcode: int
    channel: int
    message_id: int | None
    status: str
    object_operand: Operand | None
    x_operand: Operand
    y_operand: Operand
    final_control: int
    raw: bytes


def parse_operand(code: bytes, offset: int) -> tuple[Operand, int]:
    if offset >= len(code):
        raise ValueError("operand tag is outside the code region")
    tag = code[offset]
    if tag not in ARG_SIZES:
        raise ValueError(f"unsupported operand tag {tag}")
    size = ARG_SIZES[tag]
    end = offset + 1 + size
    if end > len(code):
        raise ValueError("operand payload is truncated")
    raw = code[offset + 1:end]
    value = None if tag == 0 else int.from_bytes(
        raw, "little", signed=tag in (1, 2, 3)
    )
    return Operand(tag, raw, value), end


def _s8(value: int) -> int:
    return value - 0x100 if value >= 0x80 else value


def parse_candidate(
    nsf: nsf_links.Nsf,
    logical_offset: int,
    message_ids: set[int],
) -> Reference:
    code = nsf.code
    start = logical_offset
    if code[start:start + 2] not in (b"\x42\x01", b"\x42\x02", b"\x42\x03"):
        raise ValueError("not a supported message opcode")
    opcode = code[start + 1]
    offset = start + 2
    if offset >= len(code):
        raise ValueError("truncated channel")
    channel = _s8(code[offset])
    offset += 1

    if opcode == 1:
        message_operand, offset = parse_operand(code, offset)
        message_id = message_operand.value
    else:
        if offset + 4 > len(code):
            raise ValueError("truncated literal message ID")
        message_id, = struct.unpack_from("<I", code, offset)
        offset += 4

    object_operand = None
    if opcode == 3:
        object_operand, offset = parse_operand(code, offset)
    x_operand, offset = parse_operand(code, offset)
    y_operand, offset = parse_operand(code, offset)
    if offset >= len(code):
        raise ValueError("truncated final control byte")
    final_control = _s8(code[offset])
    offset += 1

    if message_id is None:
        status = "dynamic"
    elif message_id in message_ids:
        status = "demo00"
    else:
        status = "unresolved"
    return Reference(
        start, nsf.code_base + start, opcode, channel, message_id, status,
        object_operand, x_operand, y_operand, final_control, code[start:offset],
    )


def scan(nsf: nsf_links.Nsf, table: demo00.Table) -> tuple[Reference, ...]:
    message_ids = {record.record_id for record in table.records}
    references = []
    for opcode in MESSAGE_OPCODES:
        pattern = bytes((0x42, opcode))
        offset = 0
        while True:
            offset = nsf.code.find(pattern, offset)
            if offset < 0:
                break
            try:
                references.append(parse_candidate(nsf, offset, message_ids))
            except ValueError:
                pass
            offset += 1
    references.sort(key=lambda item: item.logical_offset)
    return tuple(references)


def _operand_json(operand: Operand | None) -> dict[str, object] | None:
    if operand is None:
        return None
    return {"tag": operand.tag, "raw_hex": operand.raw.hex(), "value": operand.value}


def export(nsf_path: Path, nsf: nsf_links.Nsf, references: tuple[Reference, ...]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "scope": "consumer-shaped candidates; full instruction reachability is not yet proven",
        "source": nsf_path.as_posix(),
        "layout": {
            "code_base": f"0x{nsf.code_base:08X}",
            "code_size": len(nsf.code),
            "key_count": len(nsf.links),
            "block_count": nsf.block_count,
        },
        "counts": {
            status: sum(reference.status == status for reference in references)
            for status in ("demo00", "dynamic", "unresolved")
        },
        "references": [
            {
                "reference_id": f"demo-nsf/{reference.logical_offset:08X}",
                "logical_offset": f"0x{reference.logical_offset:08X}",
                "file_offset": f"0x{reference.file_offset:08X}",
                "opcode": f"42 {reference.opcode:02X}",
                "channel": reference.channel,
                "message_id": reference.message_id,
                "status": reference.status,
                "object_operand": _operand_json(reference.object_operand),
                "x_operand": _operand_json(reference.x_operand),
                "y_operand": _operand_json(reference.y_operand),
                "final_control": reference.final_control,
                "raw_hex": reference.raw.hex(),
            }
            for reference in references
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("nsf", type=Path)
    parser.add_argument("demo00", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    nsf = nsf_links.parse_nsf(args.nsf.read_bytes())
    table = demo00.parse(args.demo00.read_bytes())
    references = scan(nsf, table)
    counts = {status: sum(item.status == status for item in references) for status in (
        "demo00", "dynamic", "unresolved"
    )}
    if args.json:
        print(json.dumps(export(args.nsf, nsf, references), indent=2))
    else:
        unique = len({item.message_id for item in references if item.status == "demo00"})
        print(
            f"OK: code base=0x{nsf.code_base:X}, size=0x{len(nsf.code):X}; "
            f"Demo00 candidates={counts['demo00']} ({unique} unique IDs), "
            f"dynamic={counts['dynamic']}, unresolved={counts['unresolved']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
