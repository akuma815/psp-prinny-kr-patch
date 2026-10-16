#!/usr/bin/env python3
"""Audit Demo00 translation population without treating filler patterns as exclusions."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

import demo00
import nsf_links
import nsf_messages


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_declared_nsf(data: bytes) -> tuple[nsf_links.Nsf, bytes, int]:
    if len(data) < nsf_links.HEADER_SIZE:
        raise ValueError("NSF is too short")
    code_size, = struct.unpack_from("<I", data, 4)
    key_count, = struct.unpack_from("<I", data, 8)
    block_count, = struct.unpack_from("<I", data, 0x10)
    code_base = nsf_links.HEADER_SIZE + (key_count + block_count) * 8
    declared_end = code_base + code_size
    if declared_end > len(data):
        raise ValueError("NSF declared code exceeds the file")
    key_map_end = nsf_links.HEADER_SIZE + key_count * 8
    links = tuple(
        nsf_links.Link(*nsf_links.PAIR.unpack_from(data, nsf_links.HEADER_SIZE + i * 8))
        for i in range(key_count)
    )
    raw_blocks = [
        nsf_links.PAIR.unpack_from(data, key_map_end + index * 8)
        for index in range(block_count)
    ]
    valid_blocks = tuple(
        nsf_links.Block(index, start, end)
        for index, (start, end) in enumerate(raw_blocks)
        if start <= end < code_size
    )
    invalid_blocks = block_count - len(valid_blocks)
    return (
        nsf_links.Nsf(links, valid_blocks, code_base, data[code_base:declared_end]),
        data[declared_end:],
        invalid_blocks,
    )


def is_repeated_kuni(record: demo00.Record) -> bool:
    combined = record.speaker + "".join(record.lines)
    return bool(combined) and set(combined) == {"国"}


def expected_template_ids() -> set[int]:
    ids = {
        0x0064 + (layout - 1) * 0x0A + tier
        for layout in range(1, 17)
        for tier in range(3)
    }
    ids.add(0x0104)
    return ids


def _containing_blocks(nsf: nsf_links.Nsf, offset: int) -> list[dict[str, int]]:
    return [
        {"index": block.index, "start": block.start, "end": block.end}
        for block in nsf.blocks
        if block.start <= offset <= block.end
    ]


def audit(
    demo_path: Path,
    demo_data: bytes,
    nsf_paths: list[Path],
    boot_path: Path,
    boot_data: bytes,
    orphan_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    table = demo00.parse(demo_data)
    candidates = [record for record in table.records if is_repeated_kuni(record)]
    candidate_ids = {record.record_id for record in candidates}
    if candidate_ids != expected_template_ids():
        raise ValueError("repeated-kuni population no longer matches the observed ID grid")

    matrix = {
        (record.control_2, record.speaker_control): record.record_id
        for record in candidates
    }
    expected_matrix = {
        (layout, style)
        for layout in range(1, 17)
        for style in (200, 201, 202)
    } | {(17, 0)}
    if set(matrix) != expected_matrix:
        raise ValueError("repeated-kuni controls no longer form the observed layout matrix")

    references_by_id: dict[int, list[dict[str, Any]]] = {
        record_id: [] for record_id in candidate_ids
    }
    nsf_reports = []
    for path in sorted(nsf_paths, key=lambda item: item.name.lower()):
        data = path.read_bytes()
        nsf, trailing, invalid_blocks = parse_declared_nsf(data)
        references = nsf_messages.scan(nsf, table)
        candidate_references = [
            reference
            for reference in references
            if reference.status == "demo00" and reference.message_id in candidate_ids
        ]
        for reference in candidate_references:
            references_by_id[reference.message_id].append({  # type: ignore[index]
                "nsf": path.as_posix(),
                "reference_id": f"{path.stem}/{reference.logical_offset:08X}",
                "logical_offset": f"0x{reference.logical_offset:08X}",
                "file_offset": f"0x{reference.file_offset:08X}",
                "opcode": f"42 {reference.opcode:02X}",
                "raw_hex": reference.raw.hex(),
                "containing_blocks": _containing_blocks(nsf, reference.logical_offset),
                "runtime_reachability": "unverified",
            })
        nsf_reports.append({
            "path": path.as_posix(),
            "size": len(data),
            "sha256": sha256(data),
            "declared_code_size": len(nsf.code),
            "trailing_bytes": len(trailing),
            "declared_block_count": struct.unpack_from("<I", data, 0x10)[0],
            "invalid_block_records": invalid_blocks,
            "message_candidates": len(references),
            "repeated_kuni_references": len(candidate_references),
        })

    base_scope_closed = bool(
        orphan_evidence
        and orphan_evidence.get("verdict", {}).get("status")
        == "BASE_ISO_UNREACHABLE_DLC_SEPARATE"
    )
    records = []
    referenced = 0
    for record in candidates:
        references = references_by_id[record.record_id]
        if references:
            referenced += 1
        packed_u16 = struct.pack("<H", record.record_id)
        packed_u32 = struct.pack("<I", record.record_id)
        records.append({
            "entry_id": f"demo00/{record.record_id:04X}",
            "record_id": record.record_id,
            "layout_variant": record.control_2,
            "speaker_box_style": record.speaker_control,
            "speaker_length": len(record.speaker),
            "line_lengths": [len(line) for line in record.lines],
            "references": references,
            "boot_literal_occurrences": {
                "u16_le_unaligned": boot_data.count(packed_u16),
                "u32_le_unaligned": boot_data.count(packed_u32),
                "interpretation": "candidate only; byte occurrence is not a proven reference",
            },
            "population_state": "excluded_base_iso" if base_scope_closed else "unresolved",
            "translation_action": (
                "exclude from the base-ISO translation denominator; reopen only for separately supplied DLC"
                if base_scope_closed
                else "hold; do not translate or exclude without consumer evidence"
            ),
        })

    return {
        "schema_version": 1,
        "audit_id": "DEMO00-POPULATION-001",
        "scope": {
            "disc_id": "ULJS00150",
            "disc_version": "1.01",
            "demo00": {
                "path": demo_path.as_posix(),
                "size": len(demo_data),
                "sha256": sha256(demo_data),
                "declared_records": len(table.records),
            },
            "boot": {
                "path": boot_path.as_posix(),
                "size": len(boot_data),
                "sha256": sha256(boot_data),
            },
            "nsf_files": nsf_reports,
        },
        "observed_pattern": {
            "character": "国",
            "record_count": len(candidates),
            "id_rule": "0x0064 + (layout-1)*0x0A + tier for layout 1..16/tier 0..2; plus 0x0104",
            "control_matrix": "layout 1..16 x speaker style 200/201/202, plus layout 17/style 0",
            "interpretation": "strong internal layout-template candidate, not an exclusion proof",
        },
        "population": {
            "resolved_translation_targets": len(table.records) - len(candidates),
            "evidence_based_exclusions": len(candidates) if base_scope_closed else 0,
            "unresolved": 0 if base_scope_closed else len(candidates),
            "unresolved_with_nsf_candidate_reference": 0 if base_scope_closed else referenced,
            "unresolved_without_nsf_candidate_reference": 0 if base_scope_closed else len(candidates) - referenced,
            "completion_denominator_closed": base_scope_closed,
            "scope": "base ISO only; optional DLC is a separate population",
        },
        "records": records,
        "verdict": {
            "status": (
                "PASS: base-ISO denominator closed with 49 evidence-based exclusions"
                if base_scope_closed
                else "PARTIAL: 49 layout-template candidates remain unresolved"
            ),
            "reason": (
                "The sole static candidate, enemy.nsf Demo00 0x00E6, belongs to a descriptor-less key family that the base Character00 resolver cannot select; the other 48 records have no NSF candidate."
                if base_scope_closed
                else "enemy.nsf contains a structurally valid 42 02 candidate for Demo00 0x00E6; repetition and zero references elsewhere cannot prove exclusion"
            ),
            "next": (
                "Continue approved translation batches; audit DLC independently if a lawful EDAT input is added."
                if base_scope_closed
                else "trace 0x00E6 at runtime or prove its containing enemy.nsf block is unreachable in the supported game scope"
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("demo00", type=Path)
    parser.add_argument("boot", type=Path)
    parser.add_argument("nsf_dir", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--orphan-evidence", type=Path)
    args = parser.parse_args()
    report = audit(
        args.demo00,
        args.demo00.read_bytes(),
        list(args.nsf_dir.glob("*.nsf")),
        args.boot,
        args.boot.read_bytes(),
        json.loads(args.orphan_evidence.read_text(encoding="utf-8"))
        if args.orphan_evidence
        else None,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["population"], ensure_ascii=False, indent=2))
    print(report["verdict"]["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
