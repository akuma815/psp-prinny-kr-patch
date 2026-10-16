#!/usr/bin/env python3
"""Render selected CP932 glyphs from Prinny's font.fnt/font.txp pair."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from PIL import Image, ImageDraw

import font_assets


def load_font(font_fnt: Path, font_txp: Path) -> tuple[tuple[int, ...], list[tuple[int, int, int, int]], bytes]:
    fnt = font_fnt.read_bytes()
    count, = struct.unpack_from("<H", fnt)
    mapping = struct.unpack_from(f"<{count}H", fnt, 2)
    txp = font_txp.read_bytes()
    palette_width, palette_height = struct.unpack_from("<HH", txp, 8)
    palette_count = palette_width * palette_height
    palette = [tuple(txp[0x10 + i * 4:0x14 + i * 4]) for i in range(palette_count)]
    pixels = txp[0x10 + palette_count * 4:]
    return mapping, palette, pixels  # type: ignore[return-value]


def render_glyph(
    glyph_id: int,
    palette: list[tuple[int, int, int, int]],
    pixels: bytes,
    high_nibble_first: bool,
) -> Image.Image:
    width, height, stride = 20, 14, 10
    start = glyph_id * width * height // 2
    raw = pixels[start:start + stride * height]
    if len(raw) != stride * height:
        raise ValueError(f"glyph {glyph_id} is outside the texture")
    image = Image.new("RGBA", (width, height))
    for y in range(height):
        for byte_x, value in enumerate(raw[y * stride:(y + 1) * stride]):
            pair = (value >> 4, value & 0x0F) if high_nibble_first else (value & 0x0F, value >> 4)
            image.putpixel((byte_x * 2, y), palette[pair[0]])
            image.putpixel((byte_x * 2 + 1, y), palette[pair[1]])
    return image


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("font_fnt", type=Path)
    parser.add_argument("font_txp", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--text", default="Aあア国プリニー")
    parser.add_argument("--scale", type=int, default=6)
    parser.add_argument("--high-nibble-first", action="store_true")
    args = parser.parse_args()

    mapping, palette, pixels = load_font(args.font_fnt, args.font_txp)
    label_height = 18
    cell_width = 20 * args.scale + 8
    canvas = Image.new("RGBA", (cell_width * len(args.text), 14 * args.scale + label_height), (28, 32, 40, 255))
    draw = ImageDraw.Draw(canvas)
    for index, char in enumerate(args.text):
        encoded = char.encode("cp932")
        dense_index = font_assets.dense_cp932_index(encoded)
        glyph_id = mapping[dense_index]
        glyph = render_glyph(glyph_id, palette, pixels, args.high_nibble_first)
        glyph = glyph.resize((20 * args.scale, 14 * args.scale), Image.Resampling.NEAREST)
        x = index * cell_width + 4
        canvas.alpha_composite(glyph, (x, label_height))
        draw.text((x, 2), f"U+{ord(char):04X}/{glyph_id}", fill=(255, 255, 255, 255))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(args.output)
    print(f"OK: wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
