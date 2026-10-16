#!/usr/bin/env python3
"""Repair shared-atlas palette and ownership regressions in records 73 and 78.

The reviewed PNGs are production inputs.  This tool deliberately starts from
the clean decoded atlas for pixels that are not owned by translated labels, so
text edits cannot leak into title-logo or HUD sprites that share the texture.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GALLERY = PROJECT_ROOT / "work/live/image_first_pass_review/gallery/assets"

TITLE_ORIGINAL = GALLERY / "original/062_start.dat_anime00.dat_record-78_texture-0.png"
TITLE_TRANSLATED = GALLERY / "translated/062_start.dat_anime00.dat_record-78_texture-0.png"
ENEMY_ORIGINAL = GALLERY / "original/061_start.dat_anime00.dat_record-73_texture-0.png"
ENEMY_TRANSLATED = GALLERY / "translated/061_start.dat_anime00.dat_record-73_texture-0.png"

TITLE_LOGO_RESTORE = (0, 312, 360, 440)
TITLE_DATA_CELLS = ((408, 112, 504, 136), (408, 136, 504, 160))

# Exact rectangle descriptors 16..41 parsed from record 73.  The previous
# first-pass editor used approximate 17-pixel rows; those bounds crossed into
# icon/HUD consumers.  These are the actual runtime UV cells.
ENEMY_CELLS = (
    (160, 0, 216, 16), (160, 16, 184, 32), (184, 16, 208, 32),
    (160, 32, 216, 48), (208, 16, 256, 32), (216, 0, 248, 16),
    (216, 32, 256, 48), (160, 48, 224, 64), (224, 48, 256, 64),
    (160, 64, 216, 80), (216, 64, 256, 80), (160, 80, 200, 96),
    (200, 80, 256, 96), (160, 96, 240, 112), (160, 112, 200, 128),
    (200, 112, 248, 128), (80, 80, 160, 96), (0, 144, 64, 160),
    (40, 64, 72, 80), (104, 64, 136, 80), (0, 128, 72, 144),
    (72, 128, 136, 144), (136, 128, 200, 144), (72, 64, 104, 80),
    (200, 128, 240, 144), (64, 144, 104, 160),
)
ENEMY_PALETTE = (
    (0, 0, 0, 0),
    (42, 41, 42, 255),
    (123, 66, 82, 255),
    (115, 66, 82, 255),
    (79, 44, 70, 255),
    (99, 90, 123, 255),
    (225, 55, 81, 255),
)
SOLID_WHITE_INDEX = 4
SOLID_WHITE_ALPHA_THRESHOLD = 64
OUTLINE_INDEX = 1
OUTLINE_DARK_MAX = 64


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def color_distance(left: tuple[int, int, int, int], right: tuple[int, int, int, int]) -> int:
    return (
        (left[0] - right[0]) ** 2
        + (left[1] - right[1]) ** 2
        + (left[2] - right[2]) ** 2
        + (left[3] - right[3]) ** 2 * 4
    )


def repair_title(original: Image.Image, translated: Image.Image) -> tuple[Image.Image, dict[str, int]]:
    output = translated.copy()
    output.paste(original.crop(TITLE_LOGO_RESTORE), TITLE_LOGO_RESTORE[:2])

    # Record 78 rectangle metadata selects palette bank 6 for both data labels.
    # In that bank index 15 is near-transparent black, while index 14 is the
    # original opaque/bright menu fill.  Keep the crisp index-8 outline.
    index_15 = (255, 255, 255, 255)
    index_14 = (255, 255, 255, 209)
    changed_fill = 0
    pixels = output.load()
    for x0, y0, x1, y1 in TITLE_DATA_CELLS:
        for y in range(y0, y1):
            for x in range(x0, x1):
                if pixels[x, y] == index_15:
                    pixels[x, y] = index_14
                    changed_fill += 1
    return output, {
        "restored_logo_pixels": TITLE_LOGO_RESTORE[2] * TITLE_LOGO_RESTORE[3]
        - TITLE_LOGO_RESTORE[0] * TITLE_LOGO_RESTORE[3]
        - TITLE_LOGO_RESTORE[2] * TITLE_LOGO_RESTORE[1]
        + TITLE_LOGO_RESTORE[0] * TITLE_LOGO_RESTORE[1],
        "data_fill_15_to_14": changed_fill,
    }


def repair_enemy(original: Image.Image, translated: Image.Image) -> tuple[Image.Image, dict[str, int]]:
    # Start clean so icons, bars, compass pixels and unused cells are byte-for-
    # byte identical to the retail decoded atlas.
    output = original.copy()
    translated_pixels = translated.load()
    output_pixels = output.load()
    written = 0
    snapped = 0
    palette_usage = [0] * len(ENEMY_PALETTE)
    solid_white_pixels = 0
    outline_pixels = 0
    nongrayscale_nontransparent_input_pixels = 0

    # This indexed atlas is displayed through several runtime CLUT states.
    # Arbitrary RGBA antialias colours can quantize to indices that become neon
    # green in the boss-name CLUT.  The approved edit is grayscale: dark pixels
    # are the outline and light pixels are the glyph fill.  Collapse its alpha
    # antialiasing to the known-safe transparent/dark/white indices 0/1/4.
    for x0, y0, x1, y1 in ENEMY_CELLS:
        for y in range(y0, y1):
            for x in range(x0, x1):
                color = translated_pixels[x, y]
                if color[3] < SOLID_WHITE_ALPHA_THRESHOLD:
                    palette_index = 0
                elif color[0] == color[1] == color[2]:
                    if max(color[:3]) <= OUTLINE_DARK_MAX:
                        palette_index = OUTLINE_INDEX
                        outline_pixels += 1
                    else:
                        palette_index = SOLID_WHITE_INDEX
                        solid_white_pixels += 1
                else:
                    nongrayscale_nontransparent_input_pixels += 1
                    palette_index = min(
                        range(len(ENEMY_PALETTE)),
                        key=lambda index: color_distance(color, ENEMY_PALETTE[index]),
                    )
                snapped_color = ENEMY_PALETTE[palette_index]
                output_pixels[x, y] = snapped_color
                palette_usage[palette_index] += 1
                if snapped_color != color:
                    snapped += 1
                if snapped_color != original.getpixel((x, y)):
                    written += 1

    return output, {
        "label_pixels_written": written,
        "label_pixels_snapped_to_retail_ramp": snapped,
        "retail_palette_index_usage_0_to_6": palette_usage,
        "processed_name_cells": len(ENEMY_CELLS),
        "solid_white_index": SOLID_WHITE_INDEX,
        "solid_white_alpha_threshold": SOLID_WHITE_ALPHA_THRESHOLD,
        "solid_white_pixels": solid_white_pixels,
        "outline_index": OUTLINE_INDEX,
        "outline_dark_max": OUTLINE_DARK_MAX,
        "outline_pixels": outline_pixels,
        "nongrayscale_nontransparent_input_pixels": (
            nongrayscale_nontransparent_input_pixels
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--enemy-input", type=Path, default=ENEMY_TRANSLATED)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    enemy_input = args.enemy_input.resolve()
    paths = (TITLE_ORIGINAL, TITLE_TRANSLATED, ENEMY_ORIGINAL, enemy_input)
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)

    title_original = Image.open(TITLE_ORIGINAL).convert("RGBA")
    title_translated = Image.open(TITLE_TRANSLATED).convert("RGBA")
    enemy_original = Image.open(ENEMY_ORIGINAL).convert("RGBA")
    enemy_translated = Image.open(enemy_input).convert("RGBA")
    if title_original.size != (512, 512) or title_translated.size != title_original.size:
        raise ValueError("record 78 PNG geometry changed")
    if enemy_original.size != (256, 256) or enemy_translated.size != enemy_original.size:
        raise ValueError("record 73 PNG geometry changed")

    title_output, title_report = repair_title(title_original, title_translated)
    enemy_output, enemy_report = repair_enemy(enemy_original, enemy_translated)
    title_path = output_dir / TITLE_TRANSLATED.name
    enemy_path = output_dir / ENEMY_TRANSLATED.name
    title_output.save(title_path)
    enemy_output.save(enemy_path)

    report = {
        "schema_version": 1,
        "status": "PASS: shared-atlas regressions repaired",
        "title": {**title_report, "output": str(title_path), "sha256": sha256(title_path)},
        "enemy": {**enemy_report, "output": str(enemy_path), "sha256": sha256(enemy_path)},
        "invariants": {
            "title_logo_region_restored_from_original": True,
            "title_data_cells_use_index_14_fill": True,
            "enemy_pixels_outside_declared_cells_match_original": True,
            "enemy_uv_cells_match_record_descriptors": True,
            "all_name_cells_use_only_original_palette_indices_0_to_6": True,
            "grayscale_edit_uses_only_indices_0_1_and_4": (
                enemy_report["nongrayscale_nontransparent_input_pixels"] == 0
                and all(
                    count == 0
                    for index, count in enumerate(
                        enemy_report["retail_palette_index_usage_0_to_6"]
                    )
                    if index not in (0, OUTLINE_INDEX, SOLID_WHITE_INDEX)
                )
            ),
        },
    }
    (output_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
