#!/usr/bin/env python3
"""Audit fixed-size glyph reuse after replacing the complete Demo00 source corpus."""

from __future__ import annotations

import argparse
import json
import struct
from collections import defaultdict
from pathlib import Path

import audit_cp932_allocation as allocation
import audit_cp932_usage
import font_assets
import inspect_start_dat
import music_shop


def audit(
    profile_path: Path,
    production_profile_path: Path,
    artifact_path: Path,
    start_path: Path,
    boot_path: Path,
    assets_path: Path,
    supplemental_artifact_paths: tuple[Path, ...] = (),
    scan_overrides: dict[str, Path] | None = None,
) -> dict[str, object]:
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    production = json.loads(production_profile_path.read_text(encoding="utf-8"))
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    start = start_path.read_bytes()
    boot = boot_path.read_bytes()
    font_fnt = (assets_path / "font.fnt").read_bytes()
    allocation.verify_input("start.dat", start, profile)
    allocation.verify_input("BOOT.BIN", boot, profile)
    allocation.verify_input("font.fnt", font_fnt, profile)

    music = music_shop.parse((assets_path / "MusicShop.dat").read_bytes())
    texts = [value for record in music.records for value in (record.short_name.text, record.display_name.text)]
    texts += audit_cp932_usage.parse_prinny_names((assets_path / "PrinnyName.dat").read_bytes())
    structured_non_demo = {
        unit for text in texts for unit in audit_cp932_usage.cp932_units(text)
    }

    _, entries = inspect_start_dat.read_entries(start_path)
    by_name = {entry.name: entry for entry in entries}
    source_data = {"BOOT.BIN": boot}
    for name in profile["candidate_start_entries"]:
        entry = by_name[name]
        source_data[f"start.dat/{name}"] = start[entry.data_start:entry.data_end]
    # A scan override substitutes a member's bytes for the heuristic scan only,
    # e.g. a copy of PictureBook.dat with its fully translated slots zeroed so
    # that source glyphs no longer displayed anywhere stop being reserved.
    # Glyphs shared with any other scanned source remain reserved.
    for name, override_path in (scan_overrides or {}).items():
        key = f"start.dat/{name}"
        if key not in source_data:
            raise ValueError(f"scan override target is not scanned: {name}")
        override = override_path.read_bytes()
        if len(override) != len(source_data[key]):
            raise ValueError(f"scan override size mismatch for {name}")
        source_data[key] = override
    heuristic: set[bytes] = set()
    for source_name, data in source_data.items():
        scanner = profile["boot_scanner"] if source_name == "BOOT.BIN" else profile["scanner"]
        runs = allocation.candidate_runs(
            data,
            minimum_strong_japanese=scanner["minimum_strong_japanese"],
            minimum_strong_ratio=scanner["minimum_strong_ratio"],
            maximum_run_bytes=scanner["maximum_run_bytes"],
            require_nul_boundaries=scanner.get("require_nul_boundaries", False),
            exclude_utf8_japanese=scanner.get("exclude_utf8_japanese", False),
        )
        heuristic.update(unit for run in runs for unit in allocation.units_from_raw(run["raw"]))

    target_characters = {
        character
        for entry in artifact["entries"]
        if entry["translation"]["status"] == "complete"
        for text in (entry["translation"]["speaker"], *entry["translation"]["lines"])
        for character in text
    }
    supplemental_artifacts = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in supplemental_artifact_paths
    ]
    target_characters.update(
        character
        for supplemental in supplemental_artifacts
        for entry in supplemental["entries"]
        for character in entry["translation"]
    )
    hangul = sorted(character for character in target_characters if 0xAC00 <= ord(character) <= 0xD7A3)
    target_non_hangul = {
        character.encode("cp932") for character in target_characters if character not in hangul
    }
    ascii_policy = {bytes((value,)) for value in range(0x20, 0x7F)}
    # Reserve the whole CP932 0x81 symbol/punctuation row.  Data-driven screens
    # draw symbols (e.g. the record list's ′/″ time separators and full-width
    # ？ placeholders) that are neither Japanese text runs nor translation
    # characters, so reclaiming their glyphs corrupts those screens.
    symbol_row = {
        bytes((0x81, trail))
        for trail in range(0x40, 0xFD)
        if trail != 0x7F
    }
    reserved = (
        structured_non_demo | heuristic | target_non_hangul | ascii_policy | symbol_row
    )

    count, = struct.unpack_from("<H", font_fnt)
    glyph_map = struct.unpack_from(f"<{count}H", font_fnt, 2)
    engine_map = allocation.engine_code_map(glyph_map)
    codes_by_glyph: dict[int, set[bytes]] = defaultdict(set)
    for code, glyph in engine_map.items():
        if glyph:
            codes_by_glyph[glyph].add(code)
    reclaimable = sorted(
        glyph for glyph, codes in codes_by_glyph.items() if codes.isdisjoint(reserved)
    )
    required = (
        len(hangul)
        if supplemental_artifacts
        else int(production["expected"]["hangul_syllables"])
    )
    return {
        "schema_version": 1,
        "gate_id": "DEMO00-FIXED-FONT-RECLAIM-001",
        "status": "PASS" if len(reclaimable) >= required else "FAIL",
        "scope": (
            "base ISO Demo00 plus supplemental runtime UI; MusicShop, PrinnyName, "
            "heuristic tables, BOOT source CP932, target non-Hangul, and ASCII preserved"
            if supplemental_artifacts
            else "base ISO Demo00 fully replaced; MusicShop, PrinnyName, heuristic tables, BOOT, target non-Hangul, and ASCII preserved"
        ),
        "demand": {"hangul_syllables": len(hangul)},
        "reservation": {
            "structured_non_demo_codes": len(structured_non_demo),
            "heuristic_codes": len(heuristic),
            "target_non_hangul_codes": len(target_non_hangul),
            "ascii_policy_codes": len(ascii_policy),
            "symbol_row_codes": len(symbol_row),
            "union_codes": len(reserved),
        },
        "supply": {
            "reclaimable_glyphs": len(reclaimable),
            "required_glyphs": required,
            "surplus": len(reclaimable) - required,
            "selected_glyph_ids": reclaimable[:required],
            "candidate_glyph_ids": reclaimable,
        },
        "limitations": [
            "heuristic reservation is conservative evidence, not a complete renderer trace",
            "DLC and untranslated non-Demo00 consumers remain outside this base-ISO scope",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("allocation_profile", type=Path)
    parser.add_argument("production_profile", type=Path)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("start_dat", type=Path)
    parser.add_argument("boot_bin", type=Path)
    parser.add_argument("assets", type=Path)
    parser.add_argument(
        "--supplemental-artifact",
        action="append",
        default=[],
        type=Path,
        help="add translations from a simple entries[].translation artifact to glyph demand",
    )
    parser.add_argument(
        "--scan-override",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="use PATH's bytes for start.dat member NAME during the heuristic scan",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    overrides: dict[str, Path] = {}
    for item in args.scan_override:
        name, _, path = item.partition("=")
        if not path:
            raise SystemExit(f"invalid --scan-override: {item}")
        overrides[name] = Path(path)
    report = audit(
        args.allocation_profile, args.production_profile, args.artifact, args.start_dat,
        args.boot_bin, args.assets, tuple(args.supplemental_artifact), overrides
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
