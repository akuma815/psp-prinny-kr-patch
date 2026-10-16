#!/usr/bin/env python3
"""Build the final Korean-patched ISO from the verified direct_run tree.

Replaces the direct_run executable/system files plus STAGE.DAT inside a copy
of the original ISO.  Every replacement stays inside the file's original
extent (verified), so no extents move; directory records only get updated
sizes.  Rewriting an unchanged STAGE.DAT is intentional and makes derived
native-HUD trees use the same reproducible entry point.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path

import build_iso_production as isolib
from build_iso_production import (
    SECTOR_SIZE,
    hash_region,
    locate_directory,
    positioned_children,
    sha256_bytes,
    write_both_endian_u32,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

BASE_TARGETS = [
    ("/PSP_GAME/SYSDIR", "BOOT.BIN", "PSP_GAME/SYSDIR/BOOT.BIN"),
    ("/PSP_GAME/SYSDIR", "EBOOT.BIN", "PSP_GAME/SYSDIR/EBOOT.BIN"),
    ("/PSP_GAME/USRDIR", "ANIME.DAT", "PSP_GAME/USRDIR/ANIME.DAT"),
    ("/PSP_GAME/USRDIR", "BG.DAT", "PSP_GAME/USRDIR/BG.DAT"),
    ("/PSP_GAME/USRDIR", "SYSTEM.DAT", "PSP_GAME/USRDIR/SYSTEM.DAT"),
]
TARGETS = BASE_TARGETS + [
    ("/PSP_GAME/USRDIR", "STAGE.DAT", "PSP_GAME/USRDIR/STAGE.DAT"),
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--original-iso",
        type=Path,
        default=PROJECT_ROOT
        / "original/Prinny - Ore ga Shujinkou de Iinsuka (Japan, Korea).iso",
    )
    parser.add_argument(
        "--build-tree",
        type=Path,
        default=PROJECT_ROOT / "work/builds/direct_run_latest",
    )
    parser.add_argument(
        "--supplemental-report",
        type=Path,
        help=(
            "optional report for a derived direct-run tree; currently used to "
            "verify the DLC extended-font SYSTEM.DAT"
        ),
    )
    parser.add_argument(
        "--clean-tree", type=Path, default=PROJECT_ROOT / "extracted"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "work/production/Prinny_ULJS00150_KR_Final.iso",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="NAME",
        help=(
            "replace only these files (BOOT.BIN/EBOOT.BIN/ANIME.DAT/BG.DAT/"
            "SYSTEM.DAT/STAGE.DAT); repeatable.  Used to build bisection diagnostics."
        ),
    )
    args = parser.parse_args()

    build_report = json.loads(
        (PROJECT_ROOT / "work/reports/direct_run_latest.json").read_text(
            encoding="utf-8"
        )
    )
    if not str(build_report["status"]).startswith("PASS"):
        raise ValueError("direct_run report is not PASS")
    changed = set(build_report["changed_files"])
    if changed != {rel for _, _, rel in BASE_TARGETS}:
        raise ValueError(f"unexpected changed-file set: {sorted(changed)}")

    supplemental_report = None
    if args.supplemental_report:
        supplemental_report = json.loads(args.supplemental_report.read_text(encoding="utf-8"))
        if not str(supplemental_report["status"]).startswith("PASS"):
            raise ValueError("supplemental direct-run report is not PASS")
        reported_root = Path(str(supplemental_report["direct_run"]["path"]))
        if reported_root.resolve() != args.build_tree.resolve():
            raise ValueError(
                f"supplemental report build tree mismatch: {reported_root} != {args.build_tree}"
            )
        system_path = args.build_tree / "PSP_GAME/USRDIR/SYSTEM.DAT"
        expected_system_hash = str(
            supplemental_report["direct_run"]["system"]["output_system_sha256"]
        )
        if sha256_file(system_path) != expected_system_hash:
            raise ValueError("derived SYSTEM.DAT does not match the supplemental report")
        base_tree = Path(str(build_report["output_root"]))
        for _, _, rel in BASE_TARGETS:
            if rel == "PSP_GAME/USRDIR/SYSTEM.DAT":
                continue
            if (args.build_tree / rel).read_bytes() != (base_tree / rel).read_bytes():
                raise ValueError(f"derived direct-run tree unexpectedly changed {rel}")

    selected = TARGETS
    if args.only:
        wanted = {name.upper() for name in args.only}
        selected = [row for row in TARGETS if row[1].upper() in wanted]
        missing = wanted - {row[1].upper() for row in selected}
        if missing:
            raise ValueError(f"unknown --only target(s): {sorted(missing)}")

    replacements = []
    for parent_path, name, rel in selected:
        payload = (args.build_tree / rel).read_bytes()
        original = (args.clean_tree / rel).read_bytes()
        extent = (len(original) + SECTOR_SIZE - 1) // SECTOR_SIZE * SECTOR_SIZE
        if len(payload) > extent:
            raise ValueError(f"{rel} exceeds its original ISO extent")
        replacements.append((parent_path, name, rel, payload, original))

    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    try:
        shutil.copyfile(args.original_iso, temporary)
        rows = []
        for parent_path, name, rel, payload, original in replacements:
            parent = locate_directory(temporary, parent_path)
            children = positioned_children(temporary, parent)
            matches = [
                item
                for item in children
                if isolib._normalized_name(item.record.name)
                == isolib._normalized_name(name)
            ]
            if len(matches) != 1:
                raise ValueError(f"ISO record does not resolve uniquely: {rel}")
            item = matches[0]
            if item.record.size != len(original):
                raise ValueError(f"{rel}: ISO size differs from clean tree")
            if hash_region(temporary, item.record.offset, item.record.size) != (
                sha256_bytes(original)
            ):
                raise ValueError(f"{rel}: ISO payload differs from clean tree")
            with temporary.open("r+b") as stream:
                stream.seek(item.record.offset)
                stream.write(payload)
                if len(payload) < item.record.size:
                    stream.write(bytes(item.record.size - len(payload)))
                write_both_endian_u32(
                    stream, item.record_offset + 10, len(payload)
                )
                stream.flush()
                os.fsync(stream.fileno())
            rows.append(
                {
                    "file": rel,
                    "offset": f"0x{item.record.offset:X}",
                    "original_size": item.record.size,
                    "new_size": len(payload),
                    "sha256": sha256_bytes(payload),
                }
            )
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()

    if output.stat().st_size != args.original_iso.stat().st_size:
        raise ValueError("final ISO size differs from the original image")
    for parent_path, name, rel, payload, _ in replacements:
        parent = locate_directory(output, parent_path)
        record = {
            isolib._normalized_name(item.record.name): item.record
            for item in positioned_children(output, parent)
        }[isolib._normalized_name(name)]
        if record.size != len(payload):
            raise ValueError(f"{rel}: directory record verification failed")
        if hash_region(output, record.offset, record.size) != sha256_bytes(payload):
            raise ValueError(f"{rel}: payload verification failed")

    report = {
        "schema_version": 1,
        "gate_id": "FINAL-KR-ISO-001",
        "status": f"PASS: all {len(replacements)} selected direct_run files replaced in place",
        "source_build": {
            "output_root": args.build_tree.resolve().as_posix(),
            "base_output_root": build_report["output_root"],
            "renderer_cache_mode": build_report.get("renderer_cache_mode"),
            "supplemental_report": (
                args.supplemental_report.resolve().as_posix()
                if args.supplemental_report
                else None
            ),
        },
        "replacements": rows,
        "output": {
            "path": output.as_posix(),
            "size": output.stat().st_size,
            "sha256": sha256_file(output),
        },
        "runtime_gate": {
            "status": "PENDING",
            "reason": "PPSSPP boot probe and user playthrough remain",
        },
    }
    report_path = output.with_suffix(output.suffix + ".report.json")
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
