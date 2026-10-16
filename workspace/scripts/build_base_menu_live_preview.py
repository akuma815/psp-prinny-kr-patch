#!/usr/bin/env python3
"""Build the PPSSPP replacement texture for the base-area shop menu atlas."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


TEXTURE_NAME = "091591e09a963304c67a3ca6.png"
TEXTURE_ALIASES = (
    TEXTURE_NAME,
    "091591e09a96330453b50c70.png",
    "091591e09a9633045a907f4a.png",
)

# Each Japanese string is stored twice: once on its wooden sign and once in a
# transparent selection/list slot.  Rectangles are texture-pixel bounds and do
# not include screws, arrows, or the small state icon at the bottom left.
BOARD_LABELS = [
    ("음악 상점", (42, 9, 111, 41)),
    ("럭키 교수", (167, 9, 281, 41)),
    ("야반도주점", (328, 9, 425, 41)),
    ("기록 상점", (41, 59, 111, 91)),
    ("리플레이 상점", (167, 59, 281, 91)),
    ("시공의 나그네", (16, 108, 135, 142)),
    ("저장 상점", (177, 108, 268, 142)),
    ("난이도 설정", (11, 158, 141, 192)),
    ("튜토리얼", (165, 158, 284, 192)),
]

LIST_LABELS = [
    ("야반도주점", (356, 144, 463, 166)),
    ("럭키 교수", (347, 167, 487, 189)),
    ("리플레이 상점", (360, 188, 467, 211)),
    ("저장 상점", (373, 210, 461, 232)),
    ("튜토리얼", (345, 233, 499, 255)),
    ("기록 상점", (0, 200, 60, 222)),
    ("음악 상점", (60, 200, 120, 222)),
    ("난이도 설정", (120, 200, 248, 222)),
    ("시공의 나그네", (0, 222, 203, 244)),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dilate(mask: np.ndarray, iterations: int) -> np.ndarray:
    expanded = mask.copy()
    for _ in range(iterations):
        padded = np.pad(expanded, 1, mode="constant", constant_values=False)
        expanded = np.logical_or.reduce(
            [
                padded[dy : dy + expanded.shape[0], dx : dx + expanded.shape[1]]
                for dy in range(3)
                for dx in range(3)
            ]
        )
    return expanded


def diffuse_inpaint(rgba: np.ndarray, mask: np.ndarray) -> np.ndarray:
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
                dy0, dy1 = max(0, -dy), min(height, height - dy)
                dx0, dx1 = max(0, -dx), min(width, width - dx)
                sy0, sy1 = dy0 + dy, dy1 + dy
                sx0, sx1 = dx0 + dx, dx1 + dx
                neighbor_known = known[sy0:sy1, sx0:sx1]
                sums[dy0:dy1, dx0:dx1] += pixels[sy0:sy1, sx0:sx1] * neighbor_known[..., None]
                counts[dy0:dy1, dx0:dx1] += neighbor_known
        fillable = pending & (counts > 0)
        if not fillable.any():
            raise RuntimeError("inpaint mask has no reachable boundary")
        pixels[fillable] = sums[fillable] / counts[fillable, None]
        known[fillable] = True
        pending[fillable] = False
    result = np.clip(np.rint(pixels), 0, 255).astype(np.uint8)
    result[..., 3] = rgba[..., 3]
    return result


def remove_board_japanese(source: Image.Image) -> tuple[Image.Image, int]:
    rgba = np.asarray(source.convert("RGBA")).copy()
    mask = np.zeros(rgba.shape[:2], dtype=bool)
    rgb = rgba[..., :3].astype(np.int16)
    chroma = rgb.max(axis=2) - rgb.min(axis=2)
    luminance = rgb.mean(axis=2)
    neutral_glyph = (chroma <= 28) & ((luminance >= 130) | (luminance <= 72)) & (rgba[..., 3] > 0)
    for _, (x0, y0, x1, y1) in BOARD_LABELS:
        local = neutral_glyph[y0:y1, x0:x1]
        mask[y0:y1, x0:x1] |= dilate(local, 2)
    return Image.fromarray(diffuse_inpaint(rgba, mask), "RGBA"), int(mask.sum())


def fit_font(draw: ImageDraw.ImageDraw, text: str, font_path: Path, rect: tuple[int, int, int, int], maximum: int, stroke: int) -> ImageFont.FreeTypeFont:
    x0, y0, x1, y1 = rect
    for size in range(maximum, 8, -1):
        font = ImageFont.truetype(str(font_path), size)
        box = draw.textbbox((0, 0), text, font=font, stroke_width=stroke)
        if box[2] - box[0] <= x1 - x0 and box[3] - box[1] <= y1 - y0:
            return font
    raise RuntimeError(f"label does not fit: {text}")


def draw_centered(draw: ImageDraw.ImageDraw, text: str, rect: tuple[int, int, int, int], font_path: Path, maximum: int, stroke: int) -> dict[str, object]:
    font = fit_font(draw, text, font_path, rect, maximum, stroke)
    box = draw.textbbox((0, 0), text, font=font, stroke_width=stroke)
    width, height = box[2] - box[0], box[3] - box[1]
    x0, y0, x1, y1 = rect
    x = (x0 + x1 - width) // 2 - box[0]
    y = (y0 + y1 - height) // 2 - box[1]
    draw.text((x, y), text, font=font, fill=(248, 246, 238, 255), stroke_width=stroke, stroke_fill=(35, 24, 28, 255))
    return {"text": text, "rect": list(rect), "font_size": font.size, "draw_xy": [x, y]}


def merge_texture_aliases(install_dir: Path) -> dict[str, object]:
    """Preserve the existing texture pack and add every base-menu hash alias."""
    ini_path = install_dir / "textures.ini"
    aliases: dict[str, str] = {}
    if ini_path.is_file():
        section = ""
        for raw in ini_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line.startswith("[") and line.endswith("]"):
                section = line.lower()
                continue
            if section == "[hashes]" and "=" in line:
                key, value = (part.strip() for part in line.split("=", 1))
                if key and value:
                    aliases[key] = value

    canonical = Path(TEXTURE_NAME).name
    for alias in TEXTURE_ALIASES:
        aliases[Path(alias).stem] = canonical

    lines = [
        "[options]",
        "version = 1",
        "hash = quick",
        "ignoreAddress = false",
        "",
        "[hashes]",
    ]
    lines.extend(f"{key} = {aliases[key]}" for key in sorted(aliases))
    ini_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "path": str(ini_path.resolve()),
        "total_alias_count": len(aliases),
        "base_menu_aliases": [Path(alias).stem for alias in TEXTURE_ALIASES],
        "sha256": sha256(ini_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--font", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--install-dir",
        type=Path,
        help="PPSSPP texture-pack directory; installs every known palette-hash alias",
    )
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    if args.source.name != TEXTURE_NAME or not args.source.is_file() or not args.font.is_file():
        raise SystemExit("unexpected or missing source texture/font")
    source = Image.open(args.source).convert("RGBA")
    if source.size != (512, 256):
        raise SystemExit(f"unexpected source size: {source.size}")

    output, inpaint_pixels = remove_board_japanese(source)
    # List variants live on transparent atlas space; clear their complete old
    # slots so no Japanese outline or shadow survives.
    for _, (x0, y0, x1, y1) in LIST_LABELS:
        output.paste((0, 0, 0, 0), (x0, y0, x1, y1))

    draw = ImageDraw.Draw(output)
    rendered = {"board": [], "list": []}
    for text, rect in BOARD_LABELS:
        rendered["board"].append(draw_centered(draw, text, rect, args.font, 20, 2))
    for text, rect in LIST_LABELS:
        rendered["list"].append(draw_centered(draw, text, rect, args.font, 18, 1))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.save(args.output)
    installed: list[str] = []
    texture_ini = None
    if args.install_dir:
        args.install_dir.mkdir(parents=True, exist_ok=True)
        for alias in TEXTURE_ALIASES:
            destination = args.install_dir / alias
            shutil.copy2(args.output, destination)
            installed.append(str(destination.resolve()))
        texture_ini = merge_texture_aliases(args.install_dir)

    report = {
        "status": "PASS: base menu PPSSPP replacement texture generated",
        "requires_iso_rebuild": False,
        "source": str(args.source.resolve()),
        "source_sha256": sha256(args.source),
        "font": str(args.font.resolve()),
        "font_sha256": sha256(args.font),
        "output": str(args.output.resolve()),
        "output_sha256": sha256(args.output),
        "texture_aliases": list(TEXTURE_ALIASES),
        "textures_ini": texture_ini,
        "installed": installed,
        "dimensions": list(output.size),
        "inpaint_pixels": inpaint_pixels,
        "rendered": rendered,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
