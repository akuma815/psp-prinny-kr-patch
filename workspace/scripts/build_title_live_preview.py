#!/usr/bin/env python3
"""Build PPSSPP replacement textures for rapid title UV tuning."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


TITLE_IDS = {
    "gfx/title/subtitle",
    "gfx/title/name-0",
    "gfx/title/name-1",
    "gfx/title/name-2",
    "gfx/title/name-3",
}


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def _render_text(
    text: str,
    font: ImageFont.FreeTypeFont,
    stroke: int,
    angle: float,
    outline_alpha: int,
    normalize_box: tuple[int, int] | None,
    outline_color: tuple[int, int, int],
) -> Image.Image:
    bbox = font.getbbox(text, stroke_width=stroke)
    width = bbox[2] - bbox[0] + stroke * 4 + 4
    height = bbox[3] - bbox[1] + stroke * 4 + 4
    origin = (stroke * 2 + 2 - bbox[0], stroke * 2 + 2 - bbox[1])
    outline = Image.new("L", (width, height), 0)
    if stroke:
        ImageDraw.Draw(outline).text(
            origin,
            text,
            font=font,
            fill=255,
            stroke_width=stroke,
            stroke_fill=255,
        )
    fill = Image.new("L", (width, height), 0)
    ImageDraw.Draw(fill).text(origin, text, font=font, fill=255)
    content = ImageChops.lighter(outline, fill).getbbox()
    if content is None:
        raise ValueError(f"font produced no pixels: {text}")
    outline = outline.crop(content)
    fill = fill.crop(content)
    rgba = Image.new("RGBA", outline.size, (0, 0, 0, 0))
    if stroke:
        outline_layer = Image.new("RGBA", outline.size, (*outline_color, 0))
        outline_layer.putalpha(outline.point(lambda value: round(value * outline_alpha / 255)))
        rgba.alpha_composite(outline_layer)
    fill_layer = Image.new("RGBA", fill.size, (255, 255, 255, 0))
    fill_layer.putalpha(fill)
    rgba.alpha_composite(fill_layer)
    if normalize_box is not None:
        box_width, box_height = normalize_box
        scale = min(box_width / rgba.width, box_height / rgba.height)
        resized = rgba.resize(
            (max(1, round(rgba.width * scale)), max(1, round(rgba.height * scale))),
            Image.Resampling.LANCZOS,
        )
        normalized = Image.new("RGBA", normalize_box, (0, 0, 0, 0))
        normalized.alpha_composite(
            resized,
            ((box_width - resized.width) // 2, (box_height - resized.height) // 2),
        )
        rgba = normalized
    if angle:
        rgba = rgba.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    return rgba


def _render_calibration() -> Image.Image:
    """Identical cross/box source lets the runtime slot transform be measured."""
    side = 24
    image = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((1, 1, side - 2, side - 2), outline=(255, 255, 255, 255), width=2)
    draw.line((side // 2, 1, side // 2, side - 2), fill=(255, 255, 255, 255), width=1)
    draw.line((1, side // 2, side - 2, side // 2), fill=(255, 255, 255, 255), width=1)
    return image


def _alignment_anchor_y(image: Image.Image, anchor: str) -> int:
    """Return the top pixel of ㅍ or of the rightmost ㅣ component."""
    alpha = image.getchannel("A")
    pixels = alpha.load()
    seen: set[tuple[int, int]] = set()
    components: list[list[tuple[int, int]]] = []
    for y in range(alpha.height):
        for x in range(alpha.width):
            if pixels[x, y] < 32 or (x, y) in seen:
                continue
            stack = [(x, y)]
            seen.add((x, y))
            component: list[tuple[int, int]] = []
            while stack:
                px, py = stack.pop()
                component.append((px, py))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        point = (px + dx, py + dy)
                        if (0 <= point[0] < alpha.width and 0 <= point[1] < alpha.height
                                and point not in seen and pixels[point[0], point[1]] >= 32):
                            seen.add(point)
                            stack.append(point)
            if len(component) >= 6:
                components.append(component)
    if not components:
        raise ValueError("alignment anchor has no connected component")
    if anchor == "top-of-ㅍ":
        component = max(components, key=len)
    elif anchor == "top-of-ㅣ":
        component = max(components, key=lambda points: sum(x for x, _ in points) / len(points))
    else:
        raise ValueError(f"unsupported alignment anchor: {anchor}")
    return min(y for _, y in component)


def _patch_image(
    source: Image.Image,
    blocks: list[dict[str, object]],
    regular_font: Path,
    bold_font: Path,
    calibration: bool,
) -> Image.Image:
    image = source.convert("RGBA")
    for block in blocks:
        if block["id"] not in TITLE_IDS:
            continue
        x0, y0, x1, y1 = [int(value) for value in block["bounds"]]
        cx0, cy0, cx1, cy1 = [
            int(value) for value in block.get("clear_bounds", block["bounds"])
        ]
        ImageDraw.Draw(image).rectangle((cx0, cy0, cx1 - 1, cy1 - 1), fill=(0, 0, 0, 0))
        text = str(block["translation"])
        if not text:
            continue
        if calibration and block["id"].startswith("gfx/title/name-"):
            rendered = _render_calibration()
        else:
            font_path = bold_font if block.get("font_style") == "bold" else regular_font
            rendered = _render_text(
                text,
                _font(font_path, int(block["font_size"])),
                int(block.get("stroke", 0)),
                float(block.get("angle", 0)),
                int(block.get("live_outline_alpha", 96)),
                tuple(int(value) for value in block["normalize_box"])
                if "normalize_box" in block
                else None,
                tuple(int(value) for value in block.get("live_outline_color", [255, 255, 255])),
            )
        left = x0 + ((x1 - x0) - rendered.width) // 2 + int(block.get("offset_x", 0))
        if "alignment_anchor" in block and "anchor_target_y" in block:
            top = int(block["anchor_target_y"]) - _alignment_anchor_y(
                rendered, str(block["alignment_anchor"])
            )
        else:
            top = y0 + ((y1 - y0) - rendered.height) // 2 + int(block.get("offset_y", 0))
        image.alpha_composite(rendered, (left, top))
    return image


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("dump_dir", type=Path)
    parser.add_argument("replacement_dir", type=Path)
    parser.add_argument("regular_font", type=Path)
    parser.add_argument("bold_font", type=Path)
    parser.add_argument("--texture-suffix", required=True)
    parser.add_argument("--calibration", action="store_true")
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    sources = sorted(args.dump_dir.glob(f"*{args.texture_suffix}.png"))
    if not sources:
        raise SystemExit(f"no PPSSPP dumps end with {args.texture_suffix}.png")
    args.replacement_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for source_path in sources:
        source = Image.open(source_path)
        if source.size != (512, 512):
            continue
        output_path = args.replacement_dir / source_path.name
        _patch_image(
            source,
            config["blocks"],
            args.regular_font,
            args.bold_font,
            args.calibration,
        ).save(output_path)
        outputs.append(output_path.as_posix())
    if not outputs:
        raise SystemExit("matching dumps were not 512x512")
    report = {
        "status": "PASS: PPSSPP live replacement textures generated",
        "mode": "calibration" if args.calibration else "title-preview",
        "texture_suffix": args.texture_suffix,
        "outputs": outputs,
        "requires_iso_rebuild": False,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
