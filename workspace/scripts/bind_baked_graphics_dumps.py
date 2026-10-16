#!/usr/bin/env python3
"""Bind generated baked-text replacements to every exact PPSSPP texture dump."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import defaultdict
from pathlib import Path

from PIL import Image


def pixel_key(path: Path) -> tuple[int, int, str]:
    with Image.open(path) as image:
        rgba = image.convert("RGBA")
        digest = hashlib.sha256(rgba.tobytes()).hexdigest()
        return rgba.width, rgba.height, digest


def load_generated_reports(project: Path) -> dict[str, Path]:
    replacements: dict[str, Path] = {}
    reports = [
        project / "work" / "live" / "baked_graphics_full" / "build_report.json",
        project / "work" / "live" / "baked_graphics_bulk" / "build_report.json",
    ]
    for report_path in reports:
        if not report_path.is_file():
            continue
        report = json.loads(report_path.read_text(encoding="utf-8"))
        for item in report.get("generated", []):
            asset_id = item.get("asset_id") or item.get("id")
            output = item.get("output")
            if output is None and item.get("name"):
                output = str(report_path.parent / "generated" / item["name"])
            if asset_id and output and Path(output).is_file():
                replacements[str(asset_id)] = Path(output)

    # Prefer the separately validated base-menu replacement over the rough fallback.
    base_report = project / "work" / "live" / "base_menu" / "base_menu_live_preview_report.json"
    if base_report.is_file():
        item = json.loads(base_report.read_text(encoding="utf-8"))
        output = Path(item["output"])
        if output.is_file():
            replacements["start.dat/anime00.dat/record-82/texture-0"] = output

    bulk = project / "work" / "live" / "baked_graphics_bulk" / "generated"
    explicit = {
        "start.dat/anime00.dat/record-73/texture-0": bulk / "enemy_labels_r73_t00.png",
        "start.dat/anime00.dat/record-84/texture-0": bulk / "stage_result_r84_t00.png",
        "start.dat/anime00.dat/record-84/texture-1": bulk / "difficulty_r84_t01.png",
        "start.dat/anime00.dat/record-87/texture-0": bulk / "replay_save_r87_t00.png",
        "ANIME.DAT/anime20.dat/record-14/texture-0": bulk / "protagonist_sign_anime20_r14_t00.png",
        "ANIME.DAT/anime90.dat/record-2/texture-0": bulk / "end_card_anime90_r02_t00.png",
        "ANIME.DAT/anime91.dat/record-0/texture-1": bulk / "anime91_tv_labels_r00_t01.png",
        "ANIME.DAT/anime91.dat/record-0/texture-3": bulk / "anime91_staff_end_r00_t03.png",
        "ANIME.DAT/anime94.dat/record-0/texture-0": bulk / "epilogue_anime94_r00_t00.png",
        "ANIME.DAT/anime96.dat/record-0/texture-0": bulk / "epilogue_anime94_r00_t00.png",
    }
    for page in range(6):
        output = bulk / f"staff_credits_anime90_r03_t{page:02d}.png"
        explicit[f"ANIME.DAT/anime90.dat/record-3/texture-{page}"] = output
        explicit[f"ANIME.DAT/anime92.dat/record-0/texture-{page}"] = output
        explicit[f"ANIME.DAT/anime93.dat/record-1/texture-{page}"] = output
    replacements.update({asset_id: output for asset_id, output in explicit.items()
                         if output.is_file()})
    return replacements


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--dump-dir", type=Path, required=True)
    parser.add_argument("--replacement-dir", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    project = args.project_root.resolve()
    graphics = project / "work" / "analysis" / "graphics"
    inventory_path = graphics / "txp_inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    replacements = load_generated_reports(project)

    source_by_key: dict[tuple[int, int, str], list[str]] = defaultdict(list)
    missing_sources: list[str] = []
    for entry in inventory["entries"]:
        asset_id = str(entry["asset_id"])
        if asset_id not in replacements:
            continue
        preview = graphics / str(entry["preview"])
        if not preview.is_file():
            missing_sources.append(str(preview))
            continue
        source_by_key[pixel_key(preview)].append(asset_id)

    installed: list[dict[str, object]] = []
    matched_assets: set[str] = set()
    args.replacement_dir.mkdir(parents=True, exist_ok=True)
    for dump in sorted(args.dump_dir.rglob("*.png")):
        key = pixel_key(dump)
        asset_ids = source_by_key.get(key, [])
        if not asset_ids:
            continue
        # Duplicate consumers with identical pixels share the same Korean draft.
        asset_id = asset_ids[0]
        generated = replacements[asset_id]
        target = args.replacement_dir / dump.name
        if not args.dry_run:
            shutil.copy2(generated, target)
        matched_assets.update(asset_ids)
        installed.append({
            "dump": dump.name,
            "asset_ids": asset_ids,
            "replacement": str(generated),
            "target": str(target),
        })

    report = {
        "schema_version": 1,
        "dry_run": args.dry_run,
        "inventory_total": inventory["total"],
        "translated_asset_count": len(replacements),
        "indexed_asset_count": sum(len(value) for value in source_by_key.values()),
        "dump_count": len(list(args.dump_dir.rglob("*.png"))),
        "installed_dump_count": len(installed),
        "matched_assets": sorted(matched_assets),
        "unmatched_translated_assets": sorted(set(replacements) - matched_assets),
        "missing_sources": missing_sources,
        "installed": installed,
    }
    report_path = project / "work" / "live" / "baked_graphics_full" / "bind_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({
        "installed_dump_count": len(installed),
        "matched_asset_count": len(matched_assets),
        "unmatched_translated_asset_count": len(report["unmatched_translated_assets"]),
        "report": str(report_path),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
