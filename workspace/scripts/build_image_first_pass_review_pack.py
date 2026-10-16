#!/usr/bin/env python3
"""Build one review manifest/contact sheet for every classified baked-text asset."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from bind_baked_graphics_dumps import load_generated_reports


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tutorial_outputs(project: Path) -> dict[str, Path]:
    root = project / "work" / "live" / "tutorial_graphics" / "generated" / "previews"
    return {
        f"ANIME.DAT/anime12.dat/record-0/texture-{index}":
            root / f"anime12_r00_t{index:02d}_kr.png"
        for index in range(4)
    }


def title_output(project: Path) -> dict[str, Path]:
    path = project / "work" / "production" / "title_graphics_v7_final" / "title_texture_kr.png"
    return {"start.dat/anime00.dat/record-78/texture-0": path}


def fit_preview(path: Path, max_width: int = 300, max_height: int = 180) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
    return image


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True, type=Path)
    args = parser.parse_args()
    project = args.project_root.resolve()
    out = project / "work" / "live" / "image_first_pass_review"
    out.mkdir(parents=True, exist_ok=True)

    catalog_path = project / "work" / "analysis" / "graphics" / "baked_text_full_catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    targets = {
        item["asset_id"]: item
        for item in catalog["entries"]
        if item["classification"] == "target"
    }

    replacements = load_generated_reports(project)
    replacements.update(tutorial_outputs(project))
    replacements.update(title_output(project))

    bind_path = project / "work" / "live" / "baked_graphics_full" / "bind_report.json"
    bind = json.loads(bind_path.read_text(encoding="utf-8")) if bind_path.is_file() else {}
    installed_assets = set(bind.get("matched_assets", []))
    installed_assets.update(tutorial_outputs(project))
    installed_assets.update(title_output(project))

    entries = []
    missing = []
    for asset_id, target in sorted(targets.items()):
        replacement = replacements.get(asset_id)
        if replacement is None or not replacement.is_file():
            missing.append(asset_id)
            continue
        entries.append({
            "asset_id": asset_id,
            "reason": target["reason"],
            "replacement": str(replacement),
            "sha256": sha256(replacement),
            "status": "installed_or_aliased" if asset_id in installed_assets else "staged_until_dump",
        })

    unique_paths: list[Path] = []
    seen = set()
    for item in entries:
        path = Path(item["replacement"])
        digest = item["sha256"]
        if digest not in seen:
            seen.add(digest)
            unique_paths.append(path)

    cell_width, cell_height = 330, 225
    columns = 4
    rows = (len(unique_paths) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * cell_width, rows * cell_height), (31, 34, 39))
    draw = ImageDraw.Draw(sheet)
    label_font = ImageFont.load_default()
    for index, path in enumerate(unique_paths):
        preview = fit_preview(path)
        x = (index % columns) * cell_width
        y = (index // columns) * cell_height
        px = x + (cell_width - preview.width) // 2
        py = y + 25 + (180 - preview.height) // 2
        sheet.paste(preview.convert("RGB"), (px, py))
        draw.text((x + 8, y + 7), path.name[:48], fill=(240, 240, 240), font=label_font)
    sheet_path = out / "all_first_pass_contact_sheet.png"
    sheet.save(sheet_path)

    report = {
        "schema_version": 1,
        "iso_built": False,
        "inventory_total": catalog["denominator"],
        "target_asset_count": len(targets),
        "covered_asset_count": len(entries),
        "missing_asset_count": len(missing),
        "unique_replacement_count": len(unique_paths),
        "installed_or_aliased_asset_count": sum(
            item["status"] == "installed_or_aliased" for item in entries
        ),
        "staged_until_dump_asset_count": sum(
            item["status"] == "staged_until_dump" for item in entries
        ),
        "contact_sheet": str(sheet_path),
        "missing": missing,
        "entries": entries,
    }
    report_path = out / "review_manifest.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "targets": len(targets),
        "covered": len(entries),
        "missing": len(missing),
        "unique_replacements": len(unique_paths),
        "contact_sheet": str(sheet_path),
        "manifest": str(report_path),
    }, ensure_ascii=False))
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
