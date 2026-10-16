#!/usr/bin/env python3
"""Build an unchanged-size multi-glyph Hangul font PoC for Prinny."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from PIL import Image, ImageDraw

import build_font_poc
import font_assets
import render_font_glyphs


TXP_PIXEL_OFFSET = 0x50
BYTES_PER_GLYPH = 140


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build(
    profile_path: Path,
    font_path: Path,
    font_fnt_path: Path,
    font_txp_path: Path,
    output_dir: Path,
) -> dict[str, object]:
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    source_font = font_path.read_bytes()
    if sha256(source_font) != profile["source_font"]["sha256"]:
        raise ValueError("source TTF hash does not match the font profile")
    codepoints = build_font_poc.truetype_codepoints(source_font)
    missing = [value for value in range(0xAC00, 0xD7A4) if value not in codepoints]
    if missing:
        raise ValueError(f"source TTF is missing {len(missing)} modern Hangul syllables")
    cell_fit = build_font_poc.audit_modern_hangul_cell_fit(font_path, profile)
    if cell_fit["overflow_count"]:
        raise ValueError("configured raster profile exceeds the 20x14 cell")

    font_fnt = font_fnt_path.read_bytes()
    font_txp = font_txp_path.read_bytes()
    map_count, = struct.unpack_from("<H", font_fnt)
    glyph_map = struct.unpack_from(f"<{map_count}H", font_fnt, 2)
    multi = profile["multi_poc"]
    replacements = multi["replacements"]
    if not replacements:
        raise ValueError("multi-glyph PoC requires at least one replacement")

    patched = bytearray(font_txp)
    writes: list[dict[str, object]] = []
    cells: list[Image.Image] = []
    used_glyphs: set[int] = set()
    for item in replacements:
        code = bytes.fromhex(item["temporary_cp932_hex"])
        dense_index = font_assets.dense_cp932_index(code)
        glyph_id = glyph_map[dense_index]
        if dense_index != int(item["expected_dense_index"]):
            raise ValueError("multi-PoC CP932 dense index changed")
        if glyph_id != int(item["expected_glyph_id"]):
            raise ValueError("multi-PoC glyph ID changed")
        if glyph_id in used_glyphs:
            raise ValueError("multi-PoC replacements alias the same glyph")
        used_glyphs.add(glyph_id)

        cell = build_font_poc.rasterize(
            item["generated_character"], font_path, profile
        )
        packed = build_font_poc.pack_4bpp_low_first(
            cell, int(profile["target"]["palette_levels"])
        )
        start = TXP_PIXEL_OFFSET + glyph_id * BYTES_PER_GLYPH
        end = start + BYTES_PER_GLYPH
        original = font_txp[start:end]
        if len(original) != BYTES_PER_GLYPH or original == packed:
            raise ValueError("multi-PoC target cell is invalid or unchanged")
        patched[start:end] = packed
        changed = sum(before != after for before, after in zip(original, packed))
        writes.append(
            {
                "generated_character": item["generated_character"],
                "temporary_replaced_character": item["temporary_replaced_character"],
                "cp932_hex": item["temporary_cp932_hex"].upper(),
                "dense_index": dense_index,
                "glyph_id": glyph_id,
                "font_txp_write_start": f"0x{start:X}",
                "font_txp_write_end_exclusive": f"0x{end:X}",
                "declared_write_bytes": BYTES_PER_GLYPH,
                "actually_changed_bytes": changed,
            }
        )
        cells.append(cell)

    patched_txp = bytes(patched)
    allowed = {
        index
        for write in writes
        for index in range(
            int(write["font_txp_write_start"], 0),
            int(write["font_txp_write_end_exclusive"], 0),
        )
    }
    changed_offsets = {
        index
        for index, (before, after) in enumerate(zip(font_txp, patched_txp))
        if before != after
    }
    if not changed_offsets or not changed_offsets <= allowed:
        raise ValueError("font multi-PoC changed bytes outside declared cells")
    if len(patched_txp) != len(font_txp):
        raise ValueError("font.txp size changed")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_txp = output_dir / "font.txp"
    output_fnt = output_dir / "font.fnt"
    output_txp.write_bytes(patched_txp)
    output_fnt.write_bytes(font_fnt)

    _, palette, _ = render_font_glyphs.load_font(font_fnt_path, font_txp_path)
    scale = 6
    preview = Image.new(
        "RGBA",
        (len(cells) * 20 * scale + (len(cells) - 1) * 4 + 8, 14 * scale + 34),
        (28, 32, 40, 255),
    )
    draw = ImageDraw.Draw(preview)
    codepoints = " ".join(
        f"U+{ord(item['generated_character']):04X}" for item in replacements
    )
    draw.text((4, 4), f"multi glyph PoC: {codepoints}", fill="white")
    for index, (cell, write) in enumerate(zip(cells, writes)):
        quantized = [
            min(8, round(value * 8 / 255)) for value in cell.get_flattened_data()
        ]
        rgba = Image.new("RGBA", cell.size)
        rgba.putdata([palette[value] for value in quantized])
        preview.alpha_composite(
            rgba.resize((20 * scale, 14 * scale), Image.Resampling.NEAREST),
            (4 + index * (20 * scale + 4), 24),
        )
    preview_path = output_dir / "preview.png"
    preview.save(preview_path)

    report = {
        "schema_version": 1,
        "gate_id": multi["gate_id"],
        "status": (
            f"PASS: {len(replacements)} unchanged-size glyph cells built; "
            "runtime visibility pending"
        ),
        "source_font": {
            "path": font_path.as_posix(),
            "sha256": sha256(source_font),
            "modern_hangul_syllables": 11172,
            "missing_modern_hangul_syllables": len(missing),
            "configured_cell_fit_audit": cell_fit,
        },
        "display_probe": {
            "source_sequence": multi["source_sequence"],
            "generated_sequence": multi["generated_sequence"],
            "replacements": writes,
        },
        "expected_write": {
            "declared_cells": len(writes),
            "declared_bytes": len(writes) * BYTES_PER_GLYPH,
            "actually_changed_bytes": len(changed_offsets),
            "all_changes_within_declared_cells": changed_offsets <= allowed,
        },
        "outputs": {
            "font.fnt": {
                "size": len(font_fnt),
                "sha256": sha256(font_fnt),
                "byte_identical_to_original": True,
            },
            "font.txp": {
                "size": len(patched_txp),
                "sha256": sha256(patched_txp),
                "original_sha256": sha256(font_txp),
                "same_size_as_original": len(patched_txp) == len(font_txp),
            },
            "preview": preview_path.as_posix(),
        },
        "not_proved": [
            "production-safe code allocation",
            "whole-game text coverage",
            "dialog line layout and spacing",
            "runtime visibility of all four generated cells",
        ],
    }
    (output_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    parser.add_argument("font", type=Path)
    parser.add_argument("font_fnt", type=Path)
    parser.add_argument("font_txp", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    report = build(
        args.profile, args.font, args.font_fnt, args.font_txp, args.output_dir
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
