#!/usr/bin/env python3
"""Classify Prinny NSF message references by the BOOT message-table owner."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

import demo00
import nsf_links
import nsf_messages


ELF_BASE = 0x08804000
ELF_FILE_OFFSET = 84
SLOT_SETTER = 0x08862B54
SLOT_CLEARER = 0x08862B84
DEFAULT_SET_CALL = 0x0888B864
DDEM_SET_CALL = 0x088CF28C
DDEM_CLEAR_CALL = 0x088CF504
DEMO00_NAME_VA = 0x088F76B8
DDEM_TAG_VA = 0x088F7B50
DLC_PATH_VA = 0x088EFCEC


def _offset(va: int) -> int:
    return ELF_FILE_OFFSET + va - ELF_BASE


def _u32(boot: bytes, va: int) -> int:
    return struct.unpack_from("<I", boot, _offset(va))[0]


def _cstring(boot: bytes, va: int) -> str:
    start = _offset(va)
    end = boot.index(0, start)
    return boot[start:end].decode("ascii")


def validate_boot_owner_path(boot: bytes) -> dict[str, object]:
    """Validate fixed-revision instruction and string fingerprints."""
    expected_words = {
        SLOT_SETTER: 0x3C0308A3,       # lui v1, 0x08A3
        SLOT_SETTER + 8: 0x2463A15C,   # addiu v1, v1, 0xA15C
        SLOT_SETTER + 12: 0x94A60000,  # lhu a2, 0(a1)
        SLOT_SETTER + 20: 0x24A40004,  # addiu a0, a1, 4
        SLOT_SETTER + 24: 0xA4660000,  # sh a2, 0(v1)
        DEFAULT_SET_CALL: 0x0E218AD5,  # jal SLOT_SETTER
        DEFAULT_SET_CALL + 4: 0x00002021,  # move a0, zero (slot 0)
        DDEM_SET_CALL - 4: 0x24040001,  # addiu a0, zero, 1
        DDEM_SET_CALL: 0x0E218AD5,     # jal SLOT_SETTER
        DDEM_CLEAR_CALL: 0x0E218AE1,   # jal SLOT_CLEARER
        DDEM_CLEAR_CALL + 4: 0x24040001,  # addiu a0, zero, 1
    }
    mismatches = [
        f"0x{va:08X}: expected 0x{expected:08X}, got 0x{_u32(boot, va):08X}"
        for va, expected in expected_words.items()
        if _u32(boot, va) != expected
    ]
    if mismatches:
        raise ValueError("BOOT owner-path fingerprint mismatch: " + "; ".join(mismatches))
    default_name = _cstring(boot, DEMO00_NAME_VA)
    tag = _cstring(boot, DDEM_TAG_VA)
    path = _cstring(boot, DLC_PATH_VA)
    if default_name != "Demo00.dat":
        raise ValueError(f"expected Demo00.dat name, got {default_name!r}")
    if tag != "DDEM":
        raise ValueError(f"expected DDEM tag, got {tag!r}")
    if path != "ms0:/PSP/GAME/%s/DL%04d.EDAT":
        raise ValueError(f"unexpected DLC path template {path!r}")
    return {
        "slot_count": 2,
        "slot_0": default_name,
        "slot_1": tag,
        "slot_1_container": path,
        "slot_1_set_call": f"0x{DDEM_SET_CALL:08X}",
        "slot_1_clear_call": f"0x{DDEM_CLEAR_CALL:08X}",
    }


def analyze(boot: bytes, nsf_data: bytes, demo_data: bytes) -> dict[str, object]:
    owner = validate_boot_owner_path(boot)
    nsf = nsf_links.parse_nsf(nsf_data)
    table = demo00.parse(demo_data)
    references = nsf_messages.scan(nsf, table)
    second_slot = [
        reference for reference in references
        if reference.status == "unresolved"
        and reference.opcode == 1
        and reference.message_id is not None
        and reference.raw[3] == 4
    ]
    other_unresolved = [
        reference for reference in references
        if reference.status == "unresolved" and reference not in second_slot
    ]
    return {
        "schema_version": 1,
        "supported_revision": "ULJS00150 1.01",
        "owner_path": owner,
        "counts": {
            "ddem_candidates": len(second_slot),
            "other_unresolved_patterns": len(other_unresolved),
        },
        "ddem_candidates": [
            {
                "logical_offset": f"0x{reference.logical_offset:08X}",
                "file_offset": f"0x{reference.file_offset:08X}",
                "message_id": reference.message_id,
                "message_id_hex": f"0x{reference.message_id:04X}",
                "raw_hex": reference.raw.hex(),
            }
            for reference in second_slot
        ],
        "other_unresolved_patterns": [
            {
                "logical_offset": f"0x{reference.logical_offset:08X}",
                "opcode": f"42 {reference.opcode:02X}",
                "message_id": reference.message_id,
                "raw_hex": reference.raw.hex(),
            }
            for reference in other_unresolved
        ],
        "scope": (
            "DDEM is loaded from an optional Memory Stick EDAT container, not from the base ISO. "
            "The 52 candidates are owned by slot 1 if executed; block-local execution proof is tracked separately."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("boot", type=Path)
    parser.add_argument("nsf", type=Path)
    parser.add_argument("demo00", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = analyze(
        args.boot.read_bytes(), args.nsf.read_bytes(), args.demo00.read_bytes()
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
