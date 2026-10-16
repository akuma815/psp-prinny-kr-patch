#!/usr/bin/env python3
"""Merge generated BOOT UI slots and font assets into a derivative Prinny ISO."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import compress_nis_lzs
import decompress_nis_lzs
from build_iso_poc import locate_iso9660_path
from build_translated_images_iso import (
    extract_iso_targets,
    nispack_payload,
    parse_nispack,
    read_start_entries,
    rebuild_iso,
    replace_nispack_variable,
    replace_start_fixed,
)


BOOT_PATH = "/PSP_GAME/SYSDIR/BOOT.BIN;1"
EBOOT_PATH = "/PSP_GAME/SYSDIR/EBOOT.BIN;1"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_extent(path: Path, offset: int, size: int) -> bytes:
    with path.open("rb") as stream:
        stream.seek(offset)
        data = stream.read(size)
    if len(data) != size:
        raise ValueError("short ISO extent read")
    return data


def slot_rows(artifact: dict[str, object]) -> list[dict[str, int | str]]:
    rows: list[dict[str, int | str]] = []
    for entry in artifact["entries"]:
        offset = int(entry["offset"], 0)
        source_size = len(entry["source"].encode("cp932"))
        slot_size = (source_size + 4) // 4 * 4
        rows.append({
            "offset": offset,
            "offset_hex": f"0x{offset:07X}",
            "size": slot_size,
        })
    return rows


def merge_slots(
    current: bytes,
    generated: bytes,
    rows: list[dict[str, int | str]],
) -> bytes:
    if len(current) < len(generated):
        raise ValueError("ISO executable is shorter than the generated executable")
    output = bytearray(current)
    for row in rows:
        offset = int(row["offset"])
        size = int(row["size"])
        if offset + size > len(generated):
            raise ValueError("generated executable does not contain a configured slot")
        output[offset:offset + size] = generated[offset:offset + size]
    return bytes(output)


def build(
    baseline_iso: Path,
    artifact_path: Path,
    generated_dir: Path,
    output_iso: Path,
    report_path: Path,
) -> dict[str, object]:
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    rows = slot_rows(artifact)
    generated_boot = (generated_dir / "BOOT.BIN").read_bytes()
    generated_font_fnt = (generated_dir / "font.fnt").read_bytes()
    generated_font_txp = (generated_dir / "font.txp").read_bytes()

    boot_record = locate_iso9660_path(baseline_iso, BOOT_PATH)
    eboot_record = locate_iso9660_path(baseline_iso, EBOOT_PATH)
    current_boot = read_extent(baseline_iso, boot_record.offset, boot_record.size)
    current_eboot = read_extent(baseline_iso, eboot_record.offset, eboot_record.size)
    merged_boot = merge_slots(current_boot, generated_boot, rows)
    merged_eboot = merge_slots(current_eboot, generated_boot, rows)

    containers = extract_iso_targets(baseline_iso)
    system_entries = parse_nispack(containers["SYSTEM.DAT"])
    start_entry = next(
        (entry for entry in system_entries if entry["name"] == "start.lzs"),
        None,
    )
    if start_entry is None:
        raise ValueError("SYSTEM.DAT has no start.lzs")
    start_lzs = nispack_payload(containers["SYSTEM.DAT"], start_entry)
    start_dat, extension = decompress_nis_lzs.decompress(start_lzs)
    if extension != "dat":
        raise ValueError(f"unexpected start.lzs extension: {extension}")
    _, start_entries = read_start_entries(start_dat)
    start_by_name = {entry.name: entry for entry in start_entries}
    for name, replacement in (
        ("font.fnt", generated_font_fnt),
        ("font.txp", generated_font_txp),
    ):
        if name not in start_by_name:
            raise ValueError(f"start.dat is missing {name}")
        if len(replacement) != start_by_name[name].span:
            raise ValueError(f"{name} size changed")
    patched_start = replace_start_fixed(
        start_dat,
        {
            "font.fnt": generated_font_fnt,
            "font.txp": generated_font_txp,
        },
    )
    patched_lzs, lzs_stats = compress_nis_lzs.compress(
        patched_start,
        extension="dat",
        flag=0xD5,
    )
    restored, restored_extension = decompress_nis_lzs.decompress(patched_lzs)
    if restored != patched_start or restored_extension != "dat":
        raise ValueError("patched start.lzs failed self-roundtrip")
    patched_system = replace_nispack_variable(
        containers["SYSTEM.DAT"],
        {"start.lzs": patched_lzs},
    )

    replacements = dict(containers)
    replacements["SYSTEM.DAT"] = patched_system
    iso_reports = rebuild_iso(baseline_iso, replacements, output_iso)

    with output_iso.open("r+b") as stream:
        stream.seek(boot_record.offset)
        stream.write(merged_boot)
        stream.seek(eboot_record.offset)
        stream.write(merged_eboot)
        stream.flush()
        os.fsync(stream.fileno())

    for record, expected in (
        (boot_record, merged_boot),
        (eboot_record, merged_eboot),
    ):
        if read_extent(output_iso, record.offset, record.size) != expected:
            raise ValueError("merged executable did not round-trip")
    if output_iso.stat().st_size != baseline_iso.stat().st_size:
        raise ValueError("output ISO size changed")

    report = {
        "schema_version": 1,
        "status": "PASS: BOOT UI slots and font assets merged into derivative ISO",
        "baseline": {
            "path": str(baseline_iso),
            "size": baseline_iso.stat().st_size,
            "sha256": sha256_file(baseline_iso),
        },
        "boot_ui": {
            "artifact": str(artifact_path),
            "slot_count": len(rows),
            "slots": rows,
            "generated_boot_sha256": sha256(generated_boot),
            "baseline_boot_sha256": sha256(current_boot),
            "merged_boot_sha256": sha256(merged_boot),
            "baseline_code_outside_slots_preserved": True,
        },
        "font": {
            "font_fnt_sha256": sha256(generated_font_fnt),
            "font_txp_sha256": sha256(generated_font_txp),
            "fixed_sizes_preserved": True,
        },
        "start_lzs": {
            "before_size": len(start_lzs),
            "after_size": len(patched_lzs),
            "self_roundtrip": True,
            "tokens": lzs_stats,
        },
        "containers": iso_reports,
        "output": {
            "path": str(output_iso),
            "size": output_iso.stat().st_size,
            "sha256": sha256_file(output_iso),
        },
        "runtime_gate": {
            "status": "PENDING",
            "checks": [
                "small tutorial sign reads 튜토리얼",
                "clear and best times render as HH:MM:SS-style numeric groups",
                "stage and boss death counts end in 마리",
                "dialogue typewriter and punctuation fixes remain intact",
            ],
        },
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline_iso", type=Path)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("generated_dir", type=Path)
    parser.add_argument("output_iso", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    report = build(
        args.baseline_iso,
        args.artifact,
        args.generated_dir,
        args.output_iso,
        args.report,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
