#!/usr/bin/env python3
"""Build a file:// compatible offline gallery for baked-texture review."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--review-results",
        type=Path,
        help="Previously exported review JSON to preload into the rebuilt gallery.",
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_name(index: int, asset_id: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", asset_id).strip("._")
    return f"{index:03d}_{stem[:120]}.png"


def group_for(asset_id: str) -> str:
    lower = asset_id.lower()
    if lower.startswith("bg.dat/"):
        return "배경·화면"
    if "anime12.dat" in lower:
        return "튜토리얼"
    if lower.startswith("start.dat/"):
        return "시작·시스템 UI"
    if lower.startswith("anime.dat/"):
        return "연출·이벤트"
    return "기타"


def label_for(asset_id: str, reason: str | None) -> str:
    if reason and any("\uac00" <= char <= "\ud7a3" for char in reason):
        return reason
    leaf = asset_id.rsplit("/", 1)[-1]
    if leaf.startswith("texture-"):
        parts = asset_id.split("/")
        parent = parts[-3]
        record = parts[-2].replace("record-", "r")
        texture = leaf.replace("texture-", "t")
        return f"{parent} {record} {texture}"
    return leaf


def main() -> int:
    args = parse_args()
    root = args.project_root.resolve()
    output = (args.output_dir or root / "work/live/image_first_pass_review/gallery").resolve()
    catalog_path = root / "work/analysis/graphics/baked_text_full_catalog.json"
    manifest_path = root / "work/live/image_first_pass_review/review_manifest.json"
    template_dir = root / "workspace/review_gallery"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8-sig"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    review_path = args.review_results
    if review_path is None:
        candidates = sorted(
            (root / "work/live/image_first_pass_review").glob("prinny-image-review-*.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        review_path = candidates[0] if candidates else None
    prior_reviews: dict[str, dict[str, str]] = {}
    if review_path:
        review_data = json.loads(review_path.read_text(encoding="utf-8-sig"))
        prior_reviews = {
            entry["asset_id"]: {
                "status": entry.get("status", "pending"),
                "note": entry.get("note", ""),
            }
            for entry in review_data.get("entries", [])
        }
    targets = [entry for entry in catalog["entries"] if entry["classification"] == "target"]
    manifest_by_id = {entry["asset_id"]: entry for entry in manifest["entries"]}
    if len(targets) != manifest["target_asset_count"]:
        raise RuntimeError(f"target count mismatch: catalog={len(targets)} manifest={manifest['target_asset_count']}")

    output.mkdir(parents=True, exist_ok=True)
    original_dir = output / "assets/original"
    translated_dir = output / "assets/translated"
    original_dir.mkdir(parents=True, exist_ok=True)
    translated_dir.mkdir(parents=True, exist_ok=True)
    for stale in [*original_dir.glob("*.png"), *translated_dir.glob("*.png")]:
        stale.unlink()

    first_by_hash: dict[str, str] = {}
    items: list[dict[str, object]] = []
    for index, target in enumerate(targets, start=1):
        asset_id = target["asset_id"]
        bound = manifest_by_id.get(asset_id)
        if not bound:
            raise RuntimeError(f"missing manifest entry: {asset_id}")
        original = root / "work/analysis/graphics" / target["preview"]
        translated = Path(bound["replacement"])
        if not translated.is_absolute():
            translated = root / translated
        if not original.is_file():
            raise FileNotFoundError(original)
        if not translated.is_file():
            raise FileNotFoundError(translated)

        filename = safe_name(index, asset_id)
        original_copy = original_dir / filename
        translated_copy = translated_dir / filename
        shutil.copy2(original, original_copy)
        shutil.copy2(translated, translated_copy)
        with Image.open(original_copy) as original_image, Image.open(translated_copy) as translated_image:
            if original_image.size != translated_image.size:
                raise RuntimeError(f"dimension mismatch: {asset_id}: {original_image.size} != {translated_image.size}")
            width, height = original_image.size
        replacement_hash = sha256(translated_copy)
        duplicate_of = first_by_hash.get(replacement_hash)
        first_by_hash.setdefault(replacement_hash, asset_id)
        items.append({
            "asset_id": asset_id,
            "label": label_for(asset_id, target.get("reason")),
            "group": group_for(asset_id),
            "bind_status": bound["status"],
            "width": width,
            "height": height,
            "original": f"assets/original/{filename}",
            "translated": f"assets/translated/{filename}",
            "replacement_sha256": replacement_hash,
            "duplicate_of": duplicate_of,
            "initial_review": prior_reviews.get(
                asset_id, {"status": "pending", "note": ""}
            ),
        })

    data = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            key: manifest[key] for key in (
                "inventory_total", "target_asset_count", "covered_asset_count",
                "missing_asset_count", "unique_replacement_count",
                "installed_or_aliased_asset_count", "staged_until_dump_asset_count",
            )
        },
        "items": items,
    }
    for name in ("index.html", "styles.css", "app.js"):
        shutil.copy2(template_dir / name, output / name)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    (output / "data.js").write_text(f"window.REVIEW_DATA={payload};\n", encoding="utf-8")
    (output / "gallery_manifest.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(output / "index.html"),
        "items": len(items),
        "preloaded_reviews": len(prior_reviews),
        "review_results": str(review_path) if review_path else None,
        "original_pngs": len(list(original_dir.glob("*.png"))),
        "translated_pngs": len(list(translated_dir.glob("*.png"))),
        "unique_replacements": len(first_by_hash),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
