#!/usr/bin/env python3
"""Build the PPSSPP replacement texture for the two world direction signs."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


TEXTURE_NAME = "09bba150f04e998665714c1a.png"
TEXT_REGIONS = {
    # Full Japanese glyph bounds including the outer white/black fringe.
    # They stop before the red/green arrow artwork begins.
    "left": (27, 3, 110, 39),
    "right": (122, 3, 208, 39),
}
LABELS = {
    "left": {"text": "마왕성", "center": (65, 25), "font_size": 22, "rotation": 180},
    "right": {"text": "튜토리얼", "center": (159, 25), "font_size": 18, "rotation": 180},
}
# Normalize the two literals after loading the table.  Unicode escapes keep
# Windows console/code-page handling from corrupting deterministic builds.
LABELS["left"]["text"] = "".join(chr(code) for code in (0xB9C8, 0xC655, 0xC131))
LABELS["right"]["text"] = "".join(chr(code) for code in (0xD29C, 0xD1A0, 0xB9AC, 0xC5BC))
LABELS["left"]["mirror_x"] = True
LABELS["right"]["mirror_x"] = True
LABELS["right"]["center"] = (164, 25)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _diffuse_inpaint(rgba: np.ndarray, mask: np.ndarray) -> np.ndarray:
    pixels = rgba.astype(np.float32)
    known = ~mask
    pending = mask.copy()
    height, width = mask.shape

    while pending.any():
        sums = np.zeros_like(pixels)
        counts = np.zeros((height, width), dtype=np.float32)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                dst_y0 = max(0, -dy)
                dst_y1 = min(height, height - dy)
                dst_x0 = max(0, -dx)
                dst_x1 = min(width, width - dx)
                src_y0 = dst_y0 + dy
                src_y1 = dst_y1 + dy
                src_x0 = dst_x0 + dx
                src_x1 = dst_x1 + dx
                neighbor_known = known[src_y0:src_y1, src_x0:src_x1]
                sums[dst_y0:dst_y1, dst_x0:dst_x1] += (
                    pixels[src_y0:src_y1, src_x0:src_x1] * neighbor_known[..., None]
                )
                counts[dst_y0:dst_y1, dst_x0:dst_x1] += neighbor_known

        fillable = pending & (counts > 0)
        if not fillable.any():
            raise RuntimeError("Inpaint mask contains no reachable boundary pixels")
        pixels[fillable] = sums[fillable] / counts[fillable, None]
        known[fillable] = True
        pending[fillable] = False

    result = np.clip(np.rint(pixels), 0, 255).astype(np.uint8)
    result[..., 3] = rgba[..., 3]
    return result


def remove_original_labels(source: Image.Image) -> tuple[Image.Image, dict[str, int]]:
    rgba = np.array(source.convert("RGBA"))
    restored = rgba.copy()
    stats: dict[str, int] = {}

    for index, (name, (x0, y0, x1, y1)) in enumerate(TEXT_REGIONS.items()):
        region = rgba[y0:y1, x0:x1]
        rgb = region[..., :3].astype(np.int16)
        chroma = rgb.max(axis=2) - rgb.min(axis=2)
        luminance = rgb.mean(axis=2)
        opaque = region[..., 3] > 0
        # Brown board pixels have clear chroma.  Neutral Japanese face/outline
        # pixels are never used as clean-plate samples.
        wood = opaque & (chroma >= 38) & (luminance >= 55) & (luminance <= 210)
        samples = rgb[wood]
        if len(samples) < 16:
            raise RuntimeError(f"insufficient clean wood samples for {name}")
        global_base = np.median(samples, axis=0)

        row_bases = []
        for row in range(region.shape[0]):
            row_samples = rgb[row][wood[row]]
            row_bases.append(
                np.median(row_samples, axis=0) if len(row_samples) >= 4 else global_base
            )
        row_bases = np.asarray(row_bases, dtype=np.float32)
        padded = np.pad(row_bases, ((2, 2), (0, 0)), mode="edge")
        row_bases = sum(padded[offset : offset + len(row_bases)] for offset in range(5)) / 5.0

        rng = np.random.default_rng(0x5052494E + index)
        noise = rng.normal(0.0, 4.0, size=region.shape[:2]).astype(np.float32)
        for _ in range(2):
            noise = (
                noise
                + np.roll(noise, 1, axis=0)
                + np.roll(noise, -1, axis=0)
                + np.roll(noise, 1, axis=1)
                + np.roll(noise, -1, axis=1)
            ) / 5.0
        tint = np.stack((noise, noise * 0.82, noise * 0.55), axis=2)
        clean_rgb = np.clip(np.rint(row_bases[:, None, :] + tint), 0, 255).astype(np.uint8)
        # Replace only the old neutral-colour glyph and its antialias fringe.
        # Filling the whole rectangle removes the Japanese reliably, but leaves
        # a visible rectangular clean-plate seam on the wooden sign.  A broad
        # four-pixel dilation catches the tinted white/black fringe while
        # preserving the surrounding original grain and board silhouette.
        glyph = opaque & (chroma <= 24)
        glyph[(36 - y0) :, :] = False
        expanded = glyph.copy()
        for _ in range(4):
            padded_mask = np.pad(expanded, 1, mode="constant", constant_values=False)
            expanded = np.logical_or.reduce(
                [
                    padded_mask[dy : dy + expanded.shape[0], dx : dx + expanded.shape[1]]
                    for dy in range(3)
                    for dx in range(3)
                ]
            )
        managed = expanded & opaque
        target = restored[y0:y1, x0:x1]
        target[managed, :3] = clean_rgb[managed]
        stats[name] = int(managed.sum())

    return Image.fromarray(restored, "RGBA"), stats


def draw_label(
    image: Image.Image,
    text: str,
    center: tuple[int, int],
    font_path: Path,
    font_size: int,
    rotation: int = 0,
    mirror_x: bool = False,
) -> None:
    scale = 4
    layer = Image.new("RGBA", (image.width * scale, image.height * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    font = ImageFont.truetype(str(font_path), font_size * scale)
    box = draw.textbbox((0, 0), text, font=font, stroke_width=3 * scale)
    width = box[2] - box[0]
    height = box[3] - box[1]
    x = center[0] * scale - width // 2 - box[0]
    y = center[1] * scale - height // 2 - box[1]

    # Thin black outer keyline, white outline, black face; this matches the
    # high-contrast Japanese sign lettering while remaining readable at PSP size.
    draw.text(
        (x, y),
        text,
        font=font,
        fill=(18, 13, 12, 255),
        stroke_width=3 * scale,
        stroke_fill=(28, 22, 20, 220),
    )
    draw.text(
        (x, y),
        text,
        font=font,
        fill=(18, 13, 12, 255),
        stroke_width=2 * scale,
        stroke_fill=(246, 244, 232, 255),
    )
    if rotation == 180:
        # The sign mesh rotates the original lettering by 180 degrees at run
        # time.  Pre-rotate only the new label; board and arrow stay untouched.
        bounds = (x + box[0], y + box[1], x + box[2], y + box[3])
        transformed = layer.crop(bounds).transpose(Image.Transpose.ROTATE_180)
        if mirror_x:
            transformed = transformed.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        clear = Image.new("RGBA", (bounds[2] - bounds[0], bounds[3] - bounds[1]))
        layer.paste(clear, bounds)
        layer.alpha_composite(transformed, dest=(bounds[0], bounds[1]))
    elif rotation != 0:
        raise ValueError(f"unsupported label rotation: {rotation}")
    elif mirror_x:
        bounds = (x + box[0], y + box[1], x + box[2], y + box[3])
        transformed = layer.crop(bounds).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        clear = Image.new("RGBA", (bounds[2] - bounds[0], bounds[3] - bounds[1]))
        layer.paste(clear, bounds)
        layer.alpha_composite(transformed, dest=(bounds[0], bounds[1]))
    layer = layer.resize(image.size, Image.Resampling.LANCZOS)
    image.alpha_composite(layer)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--font", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--install", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    if args.source.name != TEXTURE_NAME:
        raise SystemExit(f"unexpected source filename: {args.source.name}")
    if not args.source.is_file() or not args.font.is_file():
        raise SystemExit("source texture or font is missing")

    source = Image.open(args.source).convert("RGBA")
    if source.size != (256, 128):
        raise SystemExit(f"unexpected source size: {source.size}")

    output, mask_stats = remove_original_labels(source)
    for label in LABELS.values():
        draw_label(
            output,
            label["text"],
            label["center"],
            args.font,
            font_size=label["font_size"],
            rotation=label["rotation"],
            mirror_x=label["mirror_x"],
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.save(args.output)
    if args.install:
        args.install.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(args.output, args.install)

    report = {
        "status": "PASS",
        "requires_iso_rebuild": False,
        "source": str(args.source.resolve()),
        "source_sha256": sha256(args.source),
        "font": str(args.font.resolve()),
        "font_sha256": sha256(args.font),
        "output": str(args.output.resolve()),
        "output_sha256": sha256(args.output),
        "install": str(args.install.resolve()) if args.install else None,
        "dimensions": list(output.size),
        "labels": LABELS,
        "text_regions": TEXT_REGIONS,
        "inpaint_pixels": mask_stats,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
