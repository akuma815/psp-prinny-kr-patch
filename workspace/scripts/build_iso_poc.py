#!/usr/bin/env python3
"""Build a PSP font PoC ISO by replacing one verified same-size ISO9660 file."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path


SECTOR_SIZE = 2048
PVD_SECTOR = 16
PVD_SIGNATURE = b"\x01CD001\x01"


@dataclass(frozen=True)
class IsoRecord:
    name: str
    extent_lba: int
    size: int
    flags: int

    @property
    def offset(self) -> int:
        return self.extent_lba * SECTOR_SIZE

    @property
    def is_directory(self) -> bool:
        return bool(self.flags & 0x02)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _both_endian_u32(raw: bytes, label: str) -> int:
    if len(raw) != 8:
        raise ValueError(f"truncated ISO9660 {label}")
    little = int.from_bytes(raw[:4], "little")
    big = int.from_bytes(raw[4:], "big")
    if little != big:
        raise ValueError(f"ISO9660 {label} endian copies disagree")
    return little


def parse_record(raw: bytes) -> IsoRecord:
    if len(raw) < 34 or raw[0] != len(raw):
        raise ValueError("invalid ISO9660 directory record length")
    extent = _both_endian_u32(raw[2:10], "extent")
    size = _both_endian_u32(raw[10:18], "data length")
    name_length = raw[32]
    if 33 + name_length > len(raw):
        raise ValueError("truncated ISO9660 file identifier")
    name_raw = raw[33:33 + name_length]
    if name_raw == b"\x00":
        name = "."
    elif name_raw == b"\x01":
        name = ".."
    else:
        name = name_raw.decode("ascii", errors="strict")
    return IsoRecord(name, extent, size, raw[25])


def _read_directory(iso: Path, record: IsoRecord) -> list[IsoRecord]:
    if not record.is_directory:
        raise ValueError(f"not an ISO9660 directory: {record.name}")
    with iso.open("rb") as stream:
        stream.seek(record.offset)
        data = stream.read(record.size)
    if len(data) != record.size:
        raise ValueError(f"short ISO9660 directory read: {record.name}")

    records: list[IsoRecord] = []
    cursor = 0
    while cursor < len(data):
        length = data[cursor]
        if length == 0:
            cursor = ((cursor // SECTOR_SIZE) + 1) * SECTOR_SIZE
            continue
        end = cursor + length
        if end > len(data):
            raise ValueError(f"directory record crosses declared extent: {record.name}")
        records.append(parse_record(data[cursor:end]))
        cursor = end
    return records


def _normalized_name(name: str) -> str:
    return name.upper().removesuffix(";1")


def locate_iso9660_path(iso: Path, target_path: str) -> IsoRecord:
    with iso.open("rb") as stream:
        stream.seek(PVD_SECTOR * SECTOR_SIZE)
        pvd = stream.read(SECTOR_SIZE)
    if len(pvd) != SECTOR_SIZE or pvd[:7] != PVD_SIGNATURE:
        raise ValueError("primary ISO9660 volume descriptor not found")
    root_length = pvd[156]
    root = parse_record(pvd[156:156 + root_length])

    components = [part for part in target_path.replace("\\", "/").split("/") if part]
    if not components:
        raise ValueError("empty ISO9660 target path")
    current = root
    for index, component in enumerate(components):
        matches = [
            item
            for item in _read_directory(iso, current)
            if item.name not in (".", "..")
            and _normalized_name(item.name) == _normalized_name(component)
        ]
        if len(matches) != 1:
            raise ValueError(f"ISO9660 component must resolve exactly once: {component}")
        current = matches[0]
        if index + 1 < len(components) and not current.is_directory:
            raise ValueError(f"intermediate ISO9660 component is not a directory: {component}")
    if current.is_directory:
        raise ValueError("ISO9660 target path resolves to a directory")
    return current


def _audit_diff(original: Path, output: Path, start: int, end: int) -> int:
    changed = 0
    cursor = 0
    with original.open("rb") as before_stream, output.open("rb") as after_stream:
        while True:
            before = before_stream.read(1024 * 1024)
            after = after_stream.read(1024 * 1024)
            if not before and not after:
                break
            if len(before) != len(after):
                raise ValueError("ISO output size differs from input")
            if before != after:
                for relative, (left, right) in enumerate(zip(before, after)):
                    if left == right:
                        continue
                    absolute = cursor + relative
                    if not start <= absolute < end:
                        raise ValueError(f"ISO changed outside target extent at 0x{absolute:X}")
                    changed += 1
            cursor += len(before)
    return changed


def build(
    profile_path: Path,
    iso_path: Path,
    replacement_path: Path,
    output_path: Path,
) -> dict[str, object]:
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    poc = profile.get("multi_poc", profile.get("poc"))
    if not poc:
        raise ValueError("font profile has no poc or multi_poc section")
    expected = poc["iso"]
    replacement = replacement_path.read_bytes()

    if iso_path.stat().st_size != int(expected["archive_size"]):
        raise ValueError("original ISO size does not match the font PoC profile")
    if sha256_file(iso_path) != expected["archive_sha256"]:
        raise ValueError("original ISO hash does not match the font PoC profile")
    if sha256_bytes(replacement) != expected["replacement_sha256"]:
        raise ValueError("replacement SYSTEM.DAT hash does not match the font PoC profile")

    record = locate_iso9660_path(iso_path, expected["target_path"])
    configured = (int(expected["target_offset"], 0), int(expected["target_size"]))
    if (record.offset, record.size) != configured:
        raise ValueError("ISO9660 target extent changed")
    if len(replacement) != record.size:
        raise ValueError("replacement SYSTEM.DAT must have exactly the original ISO extent size")
    with iso_path.open("rb") as stream:
        stream.seek(record.offset)
        original_target = stream.read(record.size)
    if sha256_bytes(original_target) != expected["target_sha256"]:
        raise ValueError("SYSTEM.DAT inside ISO differs from the configured baseline")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(output_path.name + ".tmp")
    try:
        shutil.copyfile(iso_path, temporary)
        with temporary.open("r+b") as stream:
            stream.seek(record.offset)
            stream.write(replacement)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output_path)
    finally:
        if temporary.exists():
            temporary.unlink()

    if output_path.stat().st_size != iso_path.stat().st_size:
        raise ValueError("built ISO size changed")
    output_record = locate_iso9660_path(output_path, expected["target_path"])
    if output_record != record:
        raise ValueError("ISO9660 target directory record changed")
    with output_path.open("rb") as stream:
        stream.seek(output_record.offset)
        written = stream.read(output_record.size)
    if written != replacement:
        raise ValueError("built ISO does not contain the replacement SYSTEM.DAT")
    changed = _audit_diff(iso_path, output_path, record.offset, record.offset + record.size)
    expected_changed = sum(left != right for left, right in zip(original_target, replacement))
    if changed != expected_changed:
        raise ValueError("ISO changed-byte count differs from the SYSTEM.DAT diff")

    report = {
        "schema_version": 1,
        "gate_id": "POC-ISO-INJECT-001",
        "status": "PASS: same-size ISO9660 extent replacement",
        "input": {
            "path": iso_path.as_posix(),
            "size": iso_path.stat().st_size,
            "sha256": expected["archive_sha256"],
        },
        "replacement": {
            "path": replacement_path.as_posix(),
            "iso9660_path": expected["target_path"],
            "offset": f"0x{record.offset:X}",
            "lba": record.extent_lba,
            "size": record.size,
            "sha256": sha256_bytes(replacement),
        },
        "output": {
            "path": output_path.as_posix(),
            "size": output_path.stat().st_size,
            "sha256": sha256_file(output_path),
            "same_size_as_input": output_path.stat().st_size == iso_path.stat().st_size,
            "changed_bytes": changed,
        },
        "expected_write": {
            "owner": expected["target_path"],
            "start": f"0x{record.offset:X}",
            "end_exclusive": f"0x{record.offset + record.size:X}",
            "directory_record_preserved": True,
            "all_changes_inside_target_extent": True,
        },
        "not_proved": [
            "PPSSPP boot and runtime asset consumption",
            "Hangul glyph visibility in the confirmed dialogue renderer",
            "physical PSP compatibility",
        ],
    }
    report_path = output_path.with_suffix(output_path.suffix + ".report.json")
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    parser.add_argument("iso", type=Path)
    parser.add_argument("replacement", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = build(args.profile, args.iso, args.replacement, args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
