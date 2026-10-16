#!/usr/bin/env python3
"""Build a contact sheet of brown, opaque components from PPSSPP texture dumps."""

from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def connected_components(mask: np.ndarray) -> list[tuple[int, int, int, int, int]]:
    height, width = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    components: list[tuple[int, int, int, int, int]] = []
    for start_y, start_x in zip(*np.nonzero(mask & ~visited), strict=True):
        if visited[start_y, start_x]:
            continue
        queue = deque([(int(start_x), int(start_y))])
        visited[start_y, start_x] = True
        min_x = max_x = int(start_x)
        min_y = max_y = int(start_y)
        area = 0
        while queue:
            x, y = queue.popleft()
            area += 1
            min_x = min(min_x, x)
            max_x = max(max_x, x)
            min_y = min(min_y, y)
            max_y = max(max_y, y)
            for next_y in range(max(0, y - 1), min(height, y + 2)):
                for next_x in range(max(0, x - 1), min(width, x + 2)):
                    if mask[next_y, next_x] and not visited[next_y, next_x]:
                        visited[next_y, next_x] = True
                        queue.append((next_x, next_y))
        components.append((min_x, min_y, max_x + 1, max_y + 1, area))
    return components


def brown_score(rgba: np.ndarray) -> float:
    alpha = rgba[..., 3] > 24
    if not alpha.any():
        return 0.0
    rgb = rgba[..., :3]
    brown = (
        alpha
        & (rgb[..., 0] >= 55)
        & (rgb[..., 0] <= 235)
        & (rgb[..., 1] >= 25)
        & (rgb[..., 1] <= 185)
        & (rgb[..., 2] <= 135)
        & (rgb[..., 0] >= rgb[..., 1] + 12)
        & (rgb[..., 1] >= rgb[..., 2] - 8)
    )
    return float(brown.sum()) / float(alpha.sum())


def unique_prefix_files(input_directory: Path) -> list[Path]:
    groups: dict[str, Path] = {}
    for path in sorted(input_directory.glob("*.png")):
        prefix = path.stem[:16]
        current = groups.get(prefix)
        if current is None or path.stat().st_mtime > current.stat().st_mtime:
            groups[prefix] = path
    return [groups[key] for key in sorted(groups)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_directory", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--maximum", type=int, default=160)
    parser.add_argument("--columns", type=int, default=5)
    parser.add_argument("--cell-width", type=int, default=240)
    parser.add_argument("--cell-height", type=int, default=190)
    args = parser.parse_args()

    candidates: list[tuple[float, Path, tuple[int, int, int, int], Image.Image]] = []
    for path in unique_prefix_files(args.input_directory):
        with Image.open(path) as source:
            rgba_image = source.convert("RGBA")
            rgba = np.asarray(rgba_image)
            alpha = rgba[..., 3]
            for min_x, min_y, max_x, max_y, area in connected_components(alpha > 24):
                width = max_x - min_x
                height = max_y - min_y
                if area < 180 or width < 24 or height < 16:
                    continue
                if width > 360 or height > 300:
                    continue
                aspect = width / height
                if not 0.65 <= aspect <= 4.5:
                    continue
                crop_array = rgba[min_y:max_y, min_x:max_x]
                score = brown_score(crop_array)
                if score < 0.25:
                    continue
                crop = rgba_image.crop((min_x, min_y, max_x, max_y)).copy()
                candidates.append(
                    (score, path, (min_x, min_y, max_x, max_y), crop)
                )

    candidates.sort(
        key=lambda item: (
            -item[0],
            -item[3].width * item[3].height,
            item[1].name,
        )
    )
    candidates = candidates[: args.maximum]

    rows = max(1, (len(candidates) + args.columns - 1) // args.columns)
    sheet = Image.new(
        "RGB",
        (args.columns * args.cell_width, rows * args.cell_height),
        (30, 30, 30),
    )
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, (score, path, box, crop) in enumerate(candidates):
        column = index % args.columns
        row = index // args.columns
        origin_x = column * args.cell_width
        origin_y = row * args.cell_height
        available_width = args.cell_width - 8
        available_height = args.cell_height - 36
        scale = min(
            available_width / crop.width,
            available_height / crop.height,
            4.0,
        )
        preview = crop.resize(
            (
                max(1, round(crop.width * scale)),
                max(1, round(crop.height * scale)),
            ),
            Image.Resampling.NEAREST,
        )
        checker = Image.new("RGBA", preview.size, (55, 55, 55, 255))
        checker.alpha_composite(preview)
        paste_x = origin_x + (args.cell_width - preview.width) // 2
        paste_y = origin_y + 2
        sheet.paste(checker.convert("RGB"), (paste_x, paste_y))
        label = (
            f"{path.stem[:16]} {box[0]},{box[1]}-{box[2]},{box[3]} "
            f"{score:.2f}"
        )
        draw.text(
            (origin_x + 4, origin_y + args.cell_height - 28),
            label,
            fill=(255, 255, 255),
            font=font,
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output)
    print(f"PASS candidates={len(candidates)} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
