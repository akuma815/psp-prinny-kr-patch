#!/usr/bin/env python3
"""Audit whether enemy.nsf target key belongs to a descriptor-less script family."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import audit_demo00_population


CHARACTER_COUNT = struct.Struct("<I")
CHARACTER_RECORD_SIZE = 68
CHARACTER_NAME_SIZE = 16
CHARACTER_NAME_OFFSET = 4
CHARACTER_ROOT_KEY_OFFSET = 60
CHARACTER_ID_OFFSET = 0
CHARACTER_TRAILER_SIZE = 4
TARGET_KEY = 0x014466E8
TARGET_FAMILY_BASE = 0x014466E0
FAMILY_SPAN = 0x64
TARGET_LOGICAL_OFFSET = 0x0001851C


@dataclass(frozen=True)
class CharacterRecord:
    index: int
    name: str
    root_key: int
    character_id: int


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_characters(data: bytes) -> tuple[CharacterRecord, ...]:
    if len(data) < CHARACTER_COUNT.size:
        raise ValueError("Character00.dat is too short")
    count, = CHARACTER_COUNT.unpack_from(data)
    expected = CHARACTER_COUNT.size + count * CHARACTER_RECORD_SIZE + CHARACTER_TRAILER_SIZE
    if len(data) != expected:
        raise ValueError(
            f"Character00.dat size mismatch: count={count} requires {expected}, got {len(data)}"
        )
    if data[-CHARACTER_TRAILER_SIZE:] != b"\0" * CHARACTER_TRAILER_SIZE:
        raise ValueError("Character00.dat trailing sentinel changed")
    records = []
    for index in range(count):
        start = CHARACTER_COUNT.size + index * CHARACTER_RECORD_SIZE
        raw_name = data[
            start + CHARACTER_NAME_OFFSET : start + CHARACTER_NAME_OFFSET + CHARACTER_NAME_SIZE
        ].split(b"\0", 1)[0]
        name = raw_name.decode("ascii", errors="strict")
        root_key, = struct.unpack_from("<I", data, start + CHARACTER_ROOT_KEY_OFFSET)
        character_id, = struct.unpack_from("<I", data, start + CHARACTER_ID_OFFSET)
        records.append(CharacterRecord(index, name, root_key, character_id))
    return tuple(records)


def elf_address_to_offset(data: bytes, address: int) -> int:
    if data[:4] != b"\x7fELF":
        raise ValueError("BOOT.BIN is not ELF")
    phoff, = struct.unpack_from("<I", data, 0x1C)
    phentsize, = struct.unpack_from("<H", data, 0x2A)
    phnum, = struct.unpack_from("<H", data, 0x2C)
    for index in range(phnum):
        entry = phoff + index * phentsize
        kind, file_offset, vaddr, _, file_size = struct.unpack_from("<IIIII", data, entry)
        if kind == 1 and vaddr <= address < vaddr + file_size:
            return file_offset + address - vaddr
    raise ValueError(f"address is outside ELF load segments: 0x{address:08X}")


def word_at_address(data: bytes, address: int) -> int:
    return struct.unpack_from("<I", data, elf_address_to_offset(data, address))[0]


def jal_word(target: int) -> int:
    return 0x0C000000 | ((target >> 2) & 0x03FFFFFF)


def boot_contract(data: bytes) -> dict[str, Any]:
    # Fixed-address assertions are deliberately paired with the BOOT hash in the report.
    assertions = {
        "base_character_load_call": (0x0888B1D4, jal_word(0x088A1720)),
        "base_character_slot_zero": (0x0888B1D8, 0x00002021),
        "dlc_character_load_call": (0x088CF254, jal_word(0x088A1720)),
        "dlc_character_slot_one": (0x088CF250, 0x24040001),
        "dlc_character_clear_call": (0x088CF4FC, jal_word(0x088A1750)),
        "character_count_load": (0x088A172C, 0x94A60000),
        "character_records_plus_four": (0x088A1734, 0x24A40004),
        "character_lookup_id_load": (0x088A17D4, 0x94830000),
        "character_lookup_stride_68_a": (0x088A17C4, 0x00051900),
        "character_lookup_stride_68_b": (0x088A17C8, 0x00651821),
        "character_lookup_stride_68_c": (0x088A17CC, 0x00031880),
        "descriptor_lookup_call": (0x08848F28, jal_word(0x088A1778)),
        "descriptor_store": (0x08848F7C, 0xAC850144),
        "root_key_load": (0x08849010, 0x8C45003C),
    }
    observed = {
        name: {
            "address": f"0x{address:08X}",
            "word": f"0x{word_at_address(data, address):08X}",
            "expected": f"0x{expected:08X}",
        }
        for name, (address, expected) in assertions.items()
    }
    if any(int(item["word"], 16) != int(item["expected"], 16) for item in observed.values()):
        raise ValueError("BOOT character-table contract changed")
    return {
        "status": "PASS",
        "assertions": observed,
        "interpretation": (
            "The base ISO loads Character00 into slot 0. Optional DLC loads slot 1. "
            "The shared resolver performs an exact ID search over 68-byte records; the returned "
            "descriptor is stored unchanged and its +0x3C root key is consumed unchanged."
        ),
    }


def occurrences(data: bytes, needle: bytes) -> list[int]:
    result = []
    start = 0
    while True:
        offset = data.find(needle, start)
        if offset < 0:
            return result
        result.append(offset)
        start = offset + 1


def audit(
    enemy_path: Path,
    enemy_data: bytes,
    character_path: Path,
    character_data: bytes,
    start_path: Path,
    start_data: bytes,
    boot_path: Path,
    boot_data: bytes,
) -> dict[str, Any]:
    nsf, trailing, invalid_blocks = audit_demo00_population.parse_declared_nsf(
        enemy_data
    )
    characters = parse_characters(character_data)
    contract = boot_contract(boot_data)
    links = {link.key: link.script_offset for link in nsf.links}
    if links.get(TARGET_KEY) != 0x1851B:
        raise ValueError("target key no longer resolves to the observed block start")
    family_links = [
        link
        for link in nsf.links
        if TARGET_FAMILY_BASE <= link.key < TARGET_FAMILY_BASE + FAMILY_SPAN
    ]
    family_roots = [
        item
        for item in characters
        if TARGET_FAMILY_BASE <= item.root_key < TARGET_FAMILY_BASE + FAMILY_SPAN
    ]
    previous_candidates = [
        item for item in characters if item.root_key == TARGET_FAMILY_BASE - 0x2710
    ]
    following_candidates = [
        item for item in characters if item.root_key == TARGET_FAMILY_BASE + 0x2710
    ]
    if len(previous_candidates) != 1 or len(following_candidates) != 1:
        raise ValueError("adjacent 0x2710 family roots are not unique")
    previous = previous_candidates[0]
    following = following_candidates[0]
    target_blocks = [
        block for block in nsf.blocks if block.start <= TARGET_LOGICAL_OFFSET <= block.end
    ]
    key_bytes = TARGET_KEY.to_bytes(4, "little")
    family_needles = {link.key: link.key.to_bytes(4, "little") for link in family_links}
    external = {}
    for path, data in ((start_path, start_data), (boot_path, boot_data)):
        external[path.as_posix()] = {
            f"0x{key:08X}": [f"0x{offset:08X}" for offset in occurrences(data, needle)]
            for key, needle in family_needles.items()
        }
    exact_external_count = sum(
        len(occurrences(data, key_bytes)) for data in (start_data, boot_data)
    )
    descriptor_gap = (
        not family_roots
        and previous.root_key + 0x2710 == TARGET_FAMILY_BASE
        and TARGET_FAMILY_BASE + 0x2710 == following.root_key
    )
    target_key_occurrences_in_enemy = occurrences(enemy_data, key_bytes)
    target_key_map_offset = next(
        nsf_links_offset
        for nsf_links_offset in target_key_occurrences_in_enemy
        if nsf_links_offset < nsf.code_base
    )
    target_key_code_occurrences = [
        offset for offset in target_key_occurrences_in_enemy if offset >= nsf.code_base
    ]
    supported_base_unreachable = (
        descriptor_gap
        and contract["status"] == "PASS"
        and exact_external_count == 0
        and target_key_code_occurrences == []
    )
    return {
        "schema_version": 1,
        "audit_id": "ENEMY-ORPHAN-KEY-001",
        "inputs": {
            "enemy_nsf": {
                "path": enemy_path.as_posix(),
                "size": len(enemy_data),
                "sha256": sha256(enemy_data),
                "trailing_bytes": len(trailing),
                "invalid_block_records": invalid_blocks,
            },
            "character00": {
                "path": character_path.as_posix(),
                "size": len(character_data),
                "sha256": sha256(character_data),
                "record_count": len(characters),
                "record_size": CHARACTER_RECORD_SIZE,
                "record_base": 4,
                "trailing_bytes": CHARACTER_TRAILER_SIZE,
            },
            "start_dat": {"path": start_path.as_posix(), "sha256": sha256(start_data)},
            "boot_bin": {"path": boot_path.as_posix(), "sha256": sha256(boot_data)},
        },
        "target": {
            "message_id": "0x00E6",
            "key": f"0x{TARGET_KEY:08X}",
            "family_base": f"0x{TARGET_FAMILY_BASE:08X}",
            "key_resolves_to_block_start": f"0x{links[TARGET_KEY]:08X}",
            "message_logical_offset": f"0x{TARGET_LOGICAL_OFFSET:08X}",
            "enemy_key_occurrences": [
                f"0x{offset:08X}" for offset in target_key_occurrences_in_enemy
            ],
            "enemy_key_map_offset": f"0x{target_key_map_offset:08X}",
            "enemy_code_occurrences": [
                f"0x{offset:08X}" for offset in target_key_code_occurrences
            ],
            "containing_blocks": [
                {
                    "index": block.index,
                    "start": f"0x{block.start:08X}",
                    "end": f"0x{block.end:08X}",
                }
                for block in target_blocks
            ],
        },
        "family": {
            "links": [
                {
                    "key": f"0x{link.key:08X}",
                    "script_offset": f"0x{link.script_offset:08X}",
                }
                for link in family_links
            ],
            "character_descriptor_roots": [
                {
                    "index": item.index,
                    "name": item.name,
                    "root_key": f"0x{item.root_key:08X}",
                    "character_id": f"0x{item.character_id:08X}",
                }
                for item in family_roots
            ],
            "previous_descriptor": {
                "index": previous.index,
                "name": previous.name,
                "root_key": f"0x{previous.root_key:08X}",
                "character_id": f"0x{previous.character_id:08X}",
            },
            "following_descriptor": {
                "index": following.index,
                "name": following.name,
                "root_key": f"0x{following.root_key:08X}",
                "character_id": f"0x{following.character_id:08X}",
            },
            "descriptor_gap_pattern": descriptor_gap,
        },
        "boot_character_contract": contract,
        "external_exact_key_occurrences": external,
        "target_exact_external_occurrence_count": exact_external_count,
        "verdict": {
            "status": "BASE_ISO_UNREACHABLE_DLC_SEPARATE" if supported_base_unreachable else "OPEN",
            "reason": (
                "The base ISO loads only Character00 into resolver slot 0, performs an exact ID search, "
                "and consumes the selected descriptor's stored +0x3C root. No descriptor owns the target "
                "family, the target key occurs only in enemy.nsf's key map, and no exact external key exists."
                if supported_base_unreachable
                else "The observed descriptor-gap invariant did not hold."
            ),
            "limit": (
                "Optional DLC can load a second Character table into slot 1 and remains a separate, unsupported input scope."
            ),
            "next": (
                "Use this evidence to keep the base-ISO denominator closed and continue approved translation batches."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("enemy_nsf", type=Path)
    parser.add_argument("character00", type=Path)
    parser.add_argument("start_dat", type=Path)
    parser.add_argument("boot_bin", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = audit(
        args.enemy_nsf,
        args.enemy_nsf.read_bytes(),
        args.character00,
        args.character00.read_bytes(),
        args.start_dat,
        args.start_dat.read_bytes(),
        args.boot_bin,
        args.boot_bin.read_bytes(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["verdict"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
