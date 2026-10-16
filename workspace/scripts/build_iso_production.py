#!/usr/bin/env python3
"""Build a fixed-size production ISO by relocating the final USRDIR extents."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from build_iso_poc import (
    PVD_SECTOR,
    PVD_SIGNATURE,
    SECTOR_SIZE,
    IsoRecord,
    _normalized_name,
    _read_directory,
    parse_record,
    sha256_file,
)


@dataclass(frozen=True)
class PositionedRecord:
    record: IsoRecord
    record_offset: int


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def align(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def locate_directory(iso: Path, directory_path: str) -> IsoRecord:
    with iso.open("rb") as stream:
        stream.seek(PVD_SECTOR * SECTOR_SIZE)
        pvd = stream.read(SECTOR_SIZE)
    if len(pvd) != SECTOR_SIZE or pvd[:7] != PVD_SIGNATURE:
        raise ValueError("primary ISO9660 volume descriptor not found")
    root = parse_record(pvd[156:156 + pvd[156]])
    current = root
    for component in [part for part in directory_path.replace("\\", "/").split("/") if part]:
        matches = [
            item for item in _read_directory(iso, current)
            if item.name not in (".", "..") and _normalized_name(item.name) == _normalized_name(component)
        ]
        if len(matches) != 1 or not matches[0].is_directory:
            raise ValueError(f"ISO9660 directory does not resolve uniquely: {component}")
        current = matches[0]
    return current


def positioned_children(iso: Path, directory: IsoRecord) -> list[PositionedRecord]:
    with iso.open("rb") as stream:
        stream.seek(directory.offset)
        data = stream.read(directory.size)
    result: list[PositionedRecord] = []
    cursor = 0
    while cursor < len(data):
        length = data[cursor]
        if length == 0:
            cursor = ((cursor // SECTOR_SIZE) + 1) * SECTOR_SIZE
            continue
        raw = data[cursor:cursor + length]
        record = parse_record(raw)
        result.append(PositionedRecord(record, directory.offset + cursor))
        cursor += length
    return result


def write_both_endian_u32(stream, offset: int, value: int) -> None:
    stream.seek(offset)
    stream.write(value.to_bytes(4, "little") + value.to_bytes(4, "big"))


def hash_region(path: Path, offset: int, size: int) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        stream.seek(offset)
        remaining = size
        while remaining:
            chunk = stream.read(min(1024 * 1024, remaining))
            if not chunk:
                raise ValueError("short ISO extent read")
            digest.update(chunk)
            remaining -= len(chunk)
    return digest.hexdigest()


def read_region(path: Path, offset: int, size: int) -> bytes:
    with path.open("rb") as stream:
        stream.seek(offset)
        data = stream.read(size)
    if len(data) != size:
        raise ValueError("short ISO extent read")
    return data


def build(
    profile_path: Path,
    iso_path: Path,
    replacement_path: Path,
    output_path: Path,
    replacement_sha256_override: str | None = None,
) -> dict[str, object]:
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    expected = profile["containers"]["iso"]
    if iso_path.stat().st_size != int(expected["size"]) or sha256_file(iso_path) != expected["sha256"]:
        raise ValueError("ISO does not match the supported revision")
    replacement = replacement_path.read_bytes()
    expected_replacement_sha256 = replacement_sha256_override or expected["replacement_sha256"]
    if sha256_bytes(replacement) != expected_replacement_sha256:
        raise ValueError("production SYSTEM.DAT hash changed")
    parent = locate_directory(iso_path, expected["parent_path"])
    children = positioned_children(iso_path, parent)
    by_name = {_normalized_name(item.record.name): item for item in children}
    configured = [_normalized_name(name) for name in expected["relocated_names"]]
    selected = [by_name[name] for name in configured]
    if [item.record.name for item in sorted(selected, key=lambda item: item.record.offset)] != expected["relocated_names"]:
        raise ValueError("ISO production extent order changed")
    target = selected[0]
    if (target.record.offset, target.record.size) != (int(expected["target_offset"], 0), int(expected["target_size"])):
        raise ValueError("ISO SYSTEM.DAT extent changed")
    if hash_region(iso_path, target.record.offset, target.record.size) != expected["target_sha256"]:
        raise ValueError("ISO SYSTEM.DAT payload changed")
    later = [item for item in children if not item.record.is_directory and item.record.offset > target.record.offset]
    if {_normalized_name(item.record.name) for item in later} != set(configured[1:]):
        raise ValueError("unowned ISO file exists after SYSTEM.DAT")

    payloads = [replacement] + [read_region(iso_path, item.record.offset, item.record.size) for item in selected[1:]]
    alignment = int(expected["alignment"])
    layouts: list[tuple[PositionedRecord, int, bytes]] = []
    cursor = target.record.offset
    for index, (item, payload) in enumerate(zip(selected, payloads)):
        if index and cursor <= item.record.offset:
            cursor = item.record.offset
        else:
            cursor = align(cursor, alignment)
        layouts.append((item, cursor, payload))
        cursor += len(payload)
    if cursor > iso_path.stat().st_size:
        raise ValueError("relocated ISO extents exceed the original image")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(output_path.name + ".tmp")
    try:
        shutil.copyfile(iso_path, temporary)
        with temporary.open("r+b") as stream:
            region_start = target.record.offset
            region_end = cursor
            stream.seek(region_start)
            remaining = region_end - region_start
            zero = bytes(1024 * 1024)
            while remaining:
                chunk = min(len(zero), remaining)
                stream.write(zero[:chunk])
                remaining -= chunk
            for item, offset, payload in layouts:
                stream.seek(offset)
                stream.write(payload)
                write_both_endian_u32(stream, item.record_offset + 2, offset // SECTOR_SIZE)
                write_both_endian_u32(stream, item.record_offset + 10, len(payload))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output_path)
    finally:
        if temporary.exists():
            temporary.unlink()

    if output_path.stat().st_size != iso_path.stat().st_size:
        raise ValueError("production ISO size changed")
    output_parent = locate_directory(output_path, expected["parent_path"])
    output_by_name = {
        _normalized_name(item.record.name): item.record
        for item in positioned_children(output_path, output_parent)
    }
    layout_reports = []
    for (before, offset, payload), name in zip(layouts, configured):
        after = output_by_name[name]
        if (after.offset, after.size) != (offset, len(payload)):
            raise ValueError(f"ISO directory record verification failed: {name}")
        if hash_region(output_path, offset, len(payload)) != sha256_bytes(payload):
            raise ValueError(f"ISO payload verification failed: {name}")
        layout_reports.append({
            "name": before.record.name,
            "original_offset": f"0x{before.record.offset:X}",
            "new_offset": f"0x{offset:X}",
            "size": len(payload),
            "sha256": sha256_bytes(payload),
        })

    report = {
        "schema_version": 1,
        "gate_id": "DEMO00-PRODUCTION-ISO-001",
        "status": "PASS: fixed-size ISO9660 image rebuilt with relocated final extents",
        "input": {"size": iso_path.stat().st_size, "sha256": expected["sha256"]},
        "extents": layout_reports,
        "output": {
            "path": output_path.as_posix(),
            "size": output_path.stat().st_size,
            "sha256": sha256_file(output_path),
            "same_size_as_input": True,
            "remaining_tail_bytes": iso_path.stat().st_size - cursor,
        },
        "expected_write": {
            "directory_records": expected["relocated_names"],
            "data_region": f"0x{target.record.offset:X}..0x{cursor:X}",
            "volume_size_and_directory_tree_preserved": True,
        },
        "runtime_gate": {"status": "PENDING", "reason": "PPSSPP boot and dialogue rendering remain"},
    }
    report_path = output_path.with_suffix(output_path.suffix + ".report.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    parser.add_argument("iso", type=Path)
    parser.add_argument("replacement", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--replacement-sha256",
        help="verified hash of a derivative SYSTEM.DAT, instead of the profile's production hash",
    )
    args = parser.parse_args()
    report = build(
        args.profile, args.iso, args.replacement, args.output,
        replacement_sha256_override=args.replacement_sha256,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
