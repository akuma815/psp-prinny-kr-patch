#!/usr/bin/env python3
"""Build PPSSPP replacements for the in-stage tutorial sign atlas.

The stage draw call uses a 256x256 CLUT4 atlas containing characters, UI
icons, the wooden sign, and a separate two-line Japanese label.  Only the
label rectangle is modified; every pixel outside it must remain identical to
the corresponding PPSSPP dump.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


TEXTURE_PREFIX = "08de41e0"
CONTENT_HASH = "b6e0db29"
TEXTURE_SIZE = (256, 256)
LABEL_BOUNDS = (211, 179, 256, 210)
LINE_BOUNDS = (
    (211, 179, 256, 195),
    (211, 194, 256, 210),
)
LABEL_LINES = ("튜토", "리얼")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def draw_centered(
    draw: ImageDraw.ImageDraw,
    text: str,
    bounds: tuple[int, int, int, int],
    font: ImageFont.FreeTypeFont,
) -> dict[str, object]:
    x0, y0, x1, y1 = bounds
    box = draw.textbbox((0, 0), text, font=font, stroke_width=1)
    width = box[2] - box[0]
    height = box[3] - box[1]
    x = (x0 + x1 - width) // 2 - box[0]
    y = (y0 + y1 - height) // 2 - box[1]
    draw.text(
        (x, y),
        text,
        font=font,
        fill=(246, 246, 244, 255),
        stroke_width=1,
        stroke_fill=(39, 35, 43, 255),
    )
    return {
        "text": text,
        "bounds": list(bounds),
        "draw_xy": [x, y],
        "bbox": list(box),
        "font_size": font.size,
    }


def build_one(source_path: Path, output_path: Path, font_path: Path) -> dict[str, object]:
    source = Image.open(source_path).convert("RGBA")
    if source.size != TEXTURE_SIZE:
        raise ValueError(f"unexpected texture size: {source_path} {source.size}")

    output = source.copy()
    output.paste((0, 0, 0, 0), LABEL_BOUNDS)
    draw = ImageDraw.Draw(output)
    font = ImageFont.truetype(str(font_path), 12)
    rendered = [
        draw_centered(draw, text, bounds, font)
        for text, bounds in zip(LABEL_LINES, LINE_BOUNDS, strict=True)
    ]

    source_bytes = source.tobytes()
    output_bytes = output.tobytes()
    width, _ = TEXTURE_SIZE
    x0, y0, x1, y1 = LABEL_BOUNDS
    changed_inside = 0
    changed_outside = 0
    for pixel_index in range(width * TEXTURE_SIZE[1]):
        offset = pixel_index * 4
        if source_bytes[offset : offset + 4] == output_bytes[offset : offset + 4]:
            continue
        x = pixel_index % width
        y = pixel_index // width
        if x0 <= x < x1 and y0 <= y < y1:
            changed_inside += 1
        else:
            changed_outside += 1
    if changed_outside:
        raise RuntimeError(
            f"protected pixels changed outside {LABEL_BOUNDS}: {changed_outside}"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.save(output_path)
    return {
        "source": str(source_path.resolve()),
        "output": str(output_path.resolve()),
        "source_sha256": sha256(source_path),
        "output_sha256": sha256(output_path),
        "changed_pixels_inside": changed_inside,
        "changed_pixels_outside": changed_outside,
        "rendered": rendered,
    }


def merge_texture_aliases(install_dir: Path, texture_names: list[str]) -> dict[str, object]:
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

    for name in texture_names:
        aliases[Path(name).stem] = name

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
        "sha256": sha256(ini_path),
        "total_alias_count": len(aliases),
        "stage_tutorial_aliases": [Path(name).stem for name in texture_names],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--font", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--install-dir", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    if not args.font.is_file():
        raise SystemExit(f"font not found: {args.font}")
    pattern = f"{TEXTURE_PREFIX}*{CONTENT_HASH}.png"
    sources = sorted(args.source_dir.glob(pattern))
    if not sources:
        raise SystemExit(f"no runtime dump matched: {args.source_dir / pattern}")

    results: list[dict[str, object]] = []
    installed: list[str] = []
    for source_path in sources:
        output_path = args.output_dir / source_path.name
        results.append(build_one(source_path, output_path, args.font))
        if args.install_dir:
            args.install_dir.mkdir(parents=True, exist_ok=True)
            destination = args.install_dir / source_path.name
            shutil.copy2(output_path, destination)
            installed.append(str(destination.resolve()))

    texture_ini = None
    if args.install_dir:
        texture_ini = merge_texture_aliases(
            args.install_dir, [source.name for source in sources]
        )

    report = {
        "status": "PASS: exact stage tutorial sign runtime atlases generated",
        "texture_identity": {
            "address_observed": "0x5976a553",
            "content_hash": CONTENT_HASH,
            "observed_hashfile": "08de41e05976a553b6e0db29.png",
            "size": list(TEXTURE_SIZE),
            "format": "CLUT4 runtime dump converted to RGBA PNG by PPSSPP",
        },
        "label_bounds": list(LABEL_BOUNDS),
        "label_lines": list(LABEL_LINES),
        "variant_count": len(results),
        "variants": results,
        "installed": installed,
        "textures_ini": texture_ini,
        "iso_built": False,
        "runtime_verification": "PENDING",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
