#!/usr/bin/env python3
"""Rank GM3 textures against translated PPSSPP texture references."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

import gm3_assets
import inspect_nispack


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage_dat", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--reference", action="append", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=12)
    args = parser.parse_args()

    archive = args.stage_dat.read_bytes()
    candidates: dict[str, tuple[np.ndarray, list[str]]] = {}
    owners: dict[str, list[str]] = defaultdict(list)
    for entry in inspect_nispack.read_entries(args.stage_dat):
        if not entry.name.lower().endswith(".gm3"):
            continue
        payload = archive[entry.offset:entry.offset + entry.size]
        parsed = gm3_assets.parse(payload)
        for texture in parsed.textures:
            image = gm3_assets.decode_texture(payload, texture)
            key = gm3_assets.sha256(image.tobytes())
            owner = f"{entry.name}/texture-{texture.index}"
            owners[key].append(owner)
            if key not in candidates:
                candidates[key] = (np.asarray(image, dtype=np.int16), owners[key])

    results = []
    for reference_path in args.reference:
        reference_image = Image.open(reference_path).convert("RGBA")
        reference = np.asarray(reference_image, dtype=np.int16)
        ref_mask = reference[:, :, 3] != 0
        rows = []
        for key, (candidate, _) in candidates.items():
            if candidate.shape != reference.shape:
                continue
            exact = np.all(candidate == reference, axis=2)
            alpha_exact = candidate[:, :, 3] == reference[:, :, 3]
            candidate_mask = candidate[:, :, 3] != 0
            union = np.count_nonzero(candidate_mask | ref_mask)
            intersection = np.count_nonzero(candidate_mask & ref_mask)
            rows.append({
                "rgba_sha256": key,
                "owners": owners[key],
                "exact_pixel_ratio": float(np.mean(exact)),
                "alpha_exact_ratio": float(np.mean(alpha_exact)),
                "alpha_mask_iou": float(intersection / union) if union else 1.0,
                "mean_absolute_rgba_error": float(np.mean(np.abs(candidate - reference))),
            })
        rows.sort(
            key=lambda row: (
                row["exact_pixel_ratio"],
                row["alpha_mask_iou"],
                -row["mean_absolute_rgba_error"],
            ),
            reverse=True,
        )
        results.append({
            "reference": reference_path.resolve().as_posix(),
            "size": list(reference_image.size),
            "candidate_count": len(rows),
            "top": rows[:args.limit],
        })

    report = {
        "schema_version": 1,
        "status": "PASS: GM3 runtime-reference similarity ranking generated",
        "unique_gm3_textures": len(candidates),
        "references": results,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(report["status"])
    for result in results:
        print(Path(result["reference"]).name, result["size"])
        for row in result["top"][:3]:
            print(
                f"  exact={row['exact_pixel_ratio']:.6f} "
                f"alpha_iou={row['alpha_mask_iou']:.6f} "
                f"mae={row['mean_absolute_rgba_error']:.3f} "
                f"owner={row['owners'][0]}"
            )
    print(f"report={args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
