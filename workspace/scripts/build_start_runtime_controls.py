#!/usr/bin/env python3
"""Build runtime-control ISOs that isolate expanded start.dat font behavior."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

import build_iso_production
import build_system_production
from compress_nis_lzs import compress
from inspect_start_dat import read_entries


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build(
    mode: str,
    profile_path: Path,
    production_start_path: Path,
    original_fnt_path: Path,
    original_txp_path: Path,
    original_system_path: Path,
    original_iso_path: Path,
    output_dir: Path,
) -> dict[str, object]:
    start = bytearray(production_start_path.read_bytes())
    entries = {entry.name: entry for entry in read_entries(production_start_path)[1]}
    font_fnt = entries["font.fnt"]
    font_txp = entries["font.txp"]
    original_fnt = original_fnt_path.read_bytes()
    original_txp = original_txp_path.read_bytes()
    if mode == "original-font-padded":
        if len(original_fnt) != font_fnt.span or len(original_txp) > font_txp.span:
            raise ValueError("original font assets do not fit control spans")
        start[font_fnt.data_start:font_fnt.data_end] = original_fnt
        start[font_txp.data_start:font_txp.data_end] = original_txp + bytes(font_txp.span - len(original_txp))
    elif mode == "original-height":
        original_height, = struct.unpack_from("<H", original_txp, 2)
        struct.pack_into("<H", start, font_txp.data_start + 2, original_height)
    else:
        raise ValueError(f"unknown runtime control mode: {mode}")

    output_dir.mkdir(parents=True, exist_ok=True)
    start_path = output_dir / "start.dat"
    start_path.write_bytes(start)
    packed, stats = compress(bytes(start))
    lzs_path = output_dir / "start.lzs"
    lzs_path.write_bytes(packed)
    system_report = build_system_production.build(
        profile_path, original_system_path, lzs_path, start_path, output_dir
    )
    system_path = output_dir / "SYSTEM.DAT"
    system_hash = system_report["output"]["sha256"]
    iso_path = output_dir / f"Prinny_ULJS00150_{mode}.iso"
    iso_report = build_iso_production.build(
        profile_path,
        original_iso_path,
        system_path,
        iso_path,
        replacement_sha256_override=system_hash,
    )
    report = {
        "schema_version": 1,
        "gate_id": f"DEMO00-START-CONTROL-{mode.upper()}",
        "mode": mode,
        "start.dat": {"size": len(start), "sha256": sha256(bytes(start))},
        "start.lzs": {"size": len(packed), "sha256": sha256(packed), "tokens": stats},
        "SYSTEM.DAT": system_report["output"],
        "iso": iso_report["output"],
    }
    (output_dir / "control_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("original-font-padded", "original-height"))
    parser.add_argument("profile", type=Path)
    parser.add_argument("production_start", type=Path)
    parser.add_argument("original_fnt", type=Path)
    parser.add_argument("original_txp", type=Path)
    parser.add_argument("original_system", type=Path)
    parser.add_argument("original_iso", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    report = build(
        args.mode, args.profile, args.production_start, args.original_fnt, args.original_txp,
        args.original_system, args.original_iso, args.output_dir
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
