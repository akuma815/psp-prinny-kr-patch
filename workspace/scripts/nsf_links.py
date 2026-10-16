#!/usr/bin/env python3
"""Resolve BaseTalk.dat resource keys through a Prinny NSF key map."""

from __future__ import annotations

import argparse
import json
import struct
from dataclasses import dataclass
from pathlib import Path

import base_talk


HEADER_SIZE = 0x20
PAIR = struct.Struct("<II")


@dataclass(frozen=True)
class Link:
    key: int
    script_offset: int


@dataclass(frozen=True)
class Block:
    index: int
    start: int
    end: int


@dataclass(frozen=True)
class Nsf:
    links: tuple[Link, ...]
    blocks: tuple[Block, ...]
    code_base: int
    code: bytes

    @property
    def block_count(self) -> int:
        return len(self.blocks)


def parse_nsf(data: bytes) -> Nsf:
    if len(data) < HEADER_SIZE:
        raise ValueError("NSF is too short")
    code_size, = struct.unpack_from("<I", data, 4)
    key_count, = struct.unpack_from("<I", data, 8)
    block_count, = struct.unpack_from("<I", data, 0x10)
    key_map_end = HEADER_SIZE + key_count * PAIR.size
    block_map_end = key_map_end + block_count * 8
    code_base = block_map_end
    if code_base > len(data):
        raise ValueError("NSF metadata arrays exceed the file")
    if code_base + code_size != len(data):
        raise ValueError(
            f"NSF code size mismatch: base=0x{code_base:X}, "
            f"declared=0x{code_size:X}, file=0x{len(data):X}"
        )
    links = tuple(
        Link(*PAIR.unpack_from(data, HEADER_SIZE + i * PAIR.size))
        for i in range(key_count)
    )
    if any(a.key >= b.key for a, b in zip(links, links[1:])):
        raise ValueError("NSF keys are not strictly increasing")
    if any(link.script_offset >= code_size for link in links):
        raise ValueError("NSF script offset is outside the code region")
    blocks = tuple(
        Block(index, *PAIR.unpack_from(data, key_map_end + index * PAIR.size))
        for index in range(block_count)
    )
    if any(block.start > block.end for block in blocks):
        raise ValueError("NSF block has an inverted range")
    if any(block.end >= code_size for block in blocks):
        raise ValueError("NSF block exceeds the code region")
    block_starts = {block.start for block in blocks}
    if any(link.script_offset not in block_starts for link in links):
        raise ValueError("NSF key does not resolve to a declared block start")
    return Nsf(links, blocks, code_base, data[code_base:])


def parse_key_map(data: bytes) -> tuple[Link, ...]:
    return parse_nsf(data).links


def resolve(table: base_talk.Table, links: tuple[Link, ...]) -> dict[int, int]:
    index = {link.key: link.script_offset for link in links}
    keys = {key for record in table.records for key in record.script_keys}
    missing = sorted(keys - index.keys())
    if missing:
        rendered = ", ".join(f"0x{key:08X}" for key in missing)
        raise ValueError(f"BaseTalk keys missing from NSF map: {rendered}")
    return {key: index[key] for key in sorted(keys)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_talk", type=Path)
    parser.add_argument("nsf", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    table = base_talk.parse(args.base_talk.read_bytes())
    links = parse_key_map(args.nsf.read_bytes())
    resolved = resolve(table, links)
    if args.json:
        print(json.dumps({f"0x{k:08X}": f"0x{v:08X}" for k, v in resolved.items()}, indent=2))
    else:
        print(f"OK: resolved {len(resolved)} unique BaseTalk keys through {len(links)} NSF entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
