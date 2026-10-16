#!/usr/bin/env python3
"""Build a runtime control ISO: relocated containers with the original start.lzs."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

import build_iso_production
from inspect_nispack import ENTRY, SIGNATURE, read_entries


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build(
    profile_path: Path,
    production_system_path: Path,
    original_lzs_path: Path,
    original_iso_path: Path,
    output_dir: Path,
) -> dict[str, object]:
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    expected = profile["containers"]
    system = bytearray(production_system_path.read_bytes())
    if sha256(system) != expected["iso"]["replacement_sha256"]:
        raise ValueError("production SYSTEM.DAT hash changed")
    original_lzs = original_lzs_path.read_bytes()
    if sha256(original_lzs) != expected["SYSTEM.DAT"]["replacement_source_sha256"]:
        raise ValueError("original start.lzs hash changed")
    entries = read_entries(production_system_path)
    target = next(entry for entry in entries if entry.name == "start.lzs")
    following = min(entry.offset for entry in entries if entry.offset > target.offset)
    if len(original_lzs) > following - target.offset:
        raise ValueError("original start.lzs does not fit the control extent")
    system[target.offset:following] = original_lzs + bytes(following - target.offset - len(original_lzs))
    record = len(SIGNATURE) + 4 + target.index * ENTRY.size
    struct.pack_into("<I", system, record + 36, len(original_lzs))

    output_dir.mkdir(parents=True, exist_ok=True)
    system_path = output_dir / "SYSTEM.DAT"
    system_path.write_bytes(system)
    reread = next(entry for entry in read_entries(system_path) if entry.name == "start.lzs")
    if reread.size != len(original_lzs) or system[reread.offset:reread.offset + reread.size] != original_lzs:
        raise ValueError("control SYSTEM.DAT re-read failed")
    system_hash = sha256(bytes(system))
    iso_path = output_dir / "Prinny_ULJS00150_container_control.iso"
    iso_report = build_iso_production.build(
        profile_path,
        original_iso_path,
        system_path,
        iso_path,
        replacement_sha256_override=system_hash,
    )
    report = {
        "schema_version": 1,
        "gate_id": "DEMO00-CONTAINER-CONTROL-001",
        "status": "PASS: relocated SYSTEM/ISO control built with original start.lzs",
        "SYSTEM.DAT": {"size": len(system), "sha256": system_hash},
        "start.lzs": {"size": len(original_lzs), "sha256": sha256(original_lzs)},
        "iso": iso_report["output"],
        "purpose": "separate container relocation from expanded start/font runtime behavior",
    }
    (output_dir / "control_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    parser.add_argument("production_system", type=Path)
    parser.add_argument("original_lzs", type=Path)
    parser.add_argument("original_iso", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    report = build(
        args.profile, args.production_system, args.original_lzs, args.original_iso, args.output_dir
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
