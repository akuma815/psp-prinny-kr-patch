#!/usr/bin/env python3
"""Build the fixed-size Korean title/menu graphics PoC inside start.dat."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

import anime_assets
import inspect_start_dat
import txp_assets


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fit_font(font_path: Path, text: str, size: int, width: int, height: int, stroke: int):
    while size >= 6:
        font = ImageFont.truetype(str(font_path), size)
        box = font.getbbox(text, stroke_width=stroke)
        if box[2] - box[0] <= width and box[3] - box[1] <= height:
            return font
        size -= 1
    raise ValueError(f"text does not fit its declared bounds: {text}")


def _coverage_index(alpha: int, indices: list[int]) -> int | None:
    """Map 8-bit coverage to a consumer-safe local CLUT ramp."""
    if alpha <= 0:
        return None
    level = round(alpha * len(indices) / 255)
    if level <= 0:
        return None
    return indices[min(level, len(indices)) - 1]


def _normalize_mask(mask: Image.Image, box: tuple[int, int]) -> Image.Image:
    scale = min(box[0] / mask.width, box[1] / mask.height)
    resized = mask.resize(
        (max(1, round(mask.width * scale)), max(1, round(mask.height * scale))),
        Image.Resampling.LANCZOS,
    )
    normalized = Image.new("L", box, 0)
    normalized.paste(resized, ((box[0] - resized.width) // 2, (box[1] - resized.height) // 2))
    return normalized


def _alignment_anchor_y(mask: Image.Image, anchor: str) -> int:
    pixels = mask.load()
    seen: set[tuple[int, int]] = set()
    components: list[list[tuple[int, int]]] = []
    for y in range(mask.height):
        for x in range(mask.width):
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
                        if (0 <= point[0] < mask.width and 0 <= point[1] < mask.height
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


def _draw_block(
    indices: Image.Image,
    block: dict[str, object],
    regular_font_path: Path,
    bold_font_path: Path,
    palette: dict[str, int],
) -> int:
    x0, y0, x1, y1 = [int(value) for value in block["bounds"]]
    if not (0 <= x0 < x1 <= indices.width and 0 <= y0 < y1 <= indices.height):
        raise ValueError(f"invalid block bounds: {block['id']}")
    cx0, cy0, cx1, cy1 = [int(value) for value in block.get("clear_bounds", block["bounds"])]
    if not (0 <= cx0 < cx1 <= indices.width and 0 <= cy0 < cy1 <= indices.height):
        raise ValueError(f"invalid clear bounds: {block['id']}")
    before = indices.crop((cx0, cy0, cx1, cy1)).tobytes()
    ImageDraw.Draw(indices).rectangle((cx0, cy0, cx1 - 1, cy1 - 1), fill=palette["transparent"])
    text = str(block["translation"])
    if text:
        stroke = int(block.get("stroke", 0))
        font_path = bold_font_path if block.get("font_style") == "bold" else regular_font_path
        normalize_box = tuple(int(value) for value in block.get("normalize_box", []))
        if normalize_box and (len(normalize_box) != 2 or min(normalize_box) <= 0):
            raise ValueError(f"invalid normalize_box: {block['id']}")
        font = (
            ImageFont.truetype(str(font_path), int(block["font_size"]))
            if normalize_box
            else _fit_font(font_path, text, int(block["font_size"]), x1 - x0, y1 - y0, stroke)
        )
        bbox = font.getbbox(text, stroke_width=stroke)
        width, height = bbox[2] - bbox[0], bbox[3] - bbox[1]
        canvas = Image.new("L", (width + stroke * 4 + 4, height + stroke * 4 + 4), 0)
        origin = (stroke * 2 + 2 - bbox[0], stroke * 2 + 2 - bbox[1])
        outline = Image.new("L", canvas.size, 0)
        if stroke:
            ImageDraw.Draw(outline).text(
                origin, text, font=font, fill=255, stroke_width=stroke, stroke_fill=255
            )
        fill = Image.new("L", canvas.size, 0)
        ImageDraw.Draw(fill).text(origin, text, font=font, fill=255)
        content_box = ImageChops.lighter(outline, fill).getbbox()
        if content_box is None:
            raise ValueError(f"font produced no pixels: {block['id']}")
        outline = outline.crop(content_box)
        fill = fill.crop(content_box)
        if normalize_box:
            outline = _normalize_mask(outline, normalize_box)
            fill = _normalize_mask(fill, normalize_box)
        angle = float(block.get("angle", 0))
        if angle:
            outline = outline.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
            fill = fill.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
        if outline.width > x1 - x0 or outline.height > y1 - y0:
            raise ValueError(f"rotated text exceeds declared bounds: {block['id']}")
        left = x0 + ((x1 - x0) - fill.width) // 2 + int(block.get("offset_x", 0))
        if "alignment_anchor" in block and "anchor_target_y" in block:
            top = int(block["anchor_target_y"]) - _alignment_anchor_y(
                outline, str(block["alignment_anchor"])
            )
        else:
            top = y0 + ((y1 - y0) - fill.height) // 2 + int(block.get("offset_y", 0))
        if block.get("allow_overflow"):
            if left < 0 or top < 0 or left + fill.width > indices.width or top + fill.height > indices.height:
                raise ValueError(f"positioned text exceeds texture bounds: {block['id']}")
        elif left < x0 or top < y0 or left + fill.width > x1 or top + fill.height > y1:
            raise ValueError(f"positioned text exceeds declared bounds: {block['id']}")
        pixels = indices.load()
        outline_index = int(block.get("outline_index", palette["outline"]))
        fill_index = int(block.get("fill_index", palette["white_opaque"]))
        outline_alpha_indices = [int(value) for value in block.get("outline_alpha_indices", [])]
        fill_alpha_indices = [int(value) for value in block.get("fill_alpha_indices", [])]
        if stroke:
            for y in range(outline.height):
                for x in range(outline.width):
                    alpha = outline.getpixel((x, y))
                    if outline_alpha_indices:
                        mapped = _coverage_index(alpha, outline_alpha_indices)
                        if mapped is not None:
                            pixels[left + x, top + y] = mapped
                    elif alpha >= int(block.get("outline_threshold", 96)):
                        pixels[left + x, top + y] = outline_index
        for y in range(fill.height):
            for x in range(fill.width):
                alpha = fill.getpixel((x, y))
                if fill_alpha_indices:
                    mapped = _coverage_index(alpha, fill_alpha_indices)
                    if mapped is not None:
                        pixels[left + x, top + y] = mapped
                elif alpha >= (int(block.get("binary_threshold", 96)) if block.get("binary", False) else 1):
                    pixels[left + x, top + y] = fill_index
    after = indices.crop((cx0, cy0, cx1, cy1)).tobytes()
    return sum(left != right for left, right in zip(before, after))


def build(
    config_path: Path,
    start_path: Path,
    font_path: Path,
    output_dir: Path,
    bold_font_path: Path | None = None,
) -> dict[str, object]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if bold_font_path is None:
        bold_font_path = font_path.with_name("HancomMalangMalang-Bold.ttf")
    if not bold_font_path.is_file():
        raise ValueError("configured bold title font is missing")
    expected = config["source"]
    source = start_path.read_bytes()
    if sha256(source) != expected["start_sha256"]:
        raise ValueError("start.dat does not match the configured production baseline")
    _, entries = inspect_start_dat.read_entries(start_path)
    entry = next((item for item in entries if item.name == expected["entry_name"]), None)
    if entry is None:
        raise ValueError("configured ANIME entry is missing")
    anime = source[entry.data_start:entry.data_end]
    if sha256(anime) != expected["entry_sha256"]:
        raise ValueError("anime00.dat hash changed")
    record = anime_assets.parse_records(anime)[int(expected["record_index"])]
    texture_index = int(expected["texture_index"])
    texture = record.textures[texture_index]
    if (record.offset, record.size) != (int(expected["record_offset"], 0), int(expected["record_size"])):
        raise ValueError("title ANIME record geometry changed")
    if (texture.width, texture.height, texture.bits_per_pixel, texture.swizzled) != (
        int(expected["width"]), int(expected["height"]),
        int(expected["bits_per_pixel"]), int(expected["swizzled"]),
    ):
        raise ValueError("title texture geometry changed")
    texture_start = record.offset + texture.offset
    original_texture = anime[texture_start:texture_start + texture.size]
    if sha256(original_texture) != expected["texture_sha256"]:
        raise ValueError("title texture payload hash changed")
    wrapped = anime_assets.texture_as_txp(anime, record, texture_index)
    indices = txp_assets.decode_indices(wrapped)
    if txp_assets.encode_indices(wrapped, indices) != wrapped:
        raise ValueError("title texture identity roundtrip failed")
    original_indices = indices.copy()
    block_reports = []
    for block in config["blocks"]:
        changed = _draw_block(
            indices, block, font_path, bold_font_path, config["palette_indices"]
        )
        block_reports.append({
            "block_id": block["id"], "original": block["original"],
            "translation": block["translation"], "bounds": block["bounds"],
            "clear_bounds": block.get("clear_bounds", block["bounds"]),
            "font_style": block.get("font_style", "regular"),
            "font_size": int(block["font_size"]),
            "stroke": int(block.get("stroke", 0)),
            "angle": float(block.get("angle", 0)),
            "fill_index": int(block.get("fill_index", config["palette_indices"]["white_opaque"])),
            "fill_alpha_indices": block.get("fill_alpha_indices", []),
            "outline_alpha_indices": block.get("outline_alpha_indices", []),
            "normalize_box": block.get("normalize_box"),
            "offset_x": int(block.get("offset_x", 0)),
            "offset_y": int(block.get("offset_y", 0)),
            "changed_pixels": changed,
        })
    allowed = set()
    for block in config["blocks"]:
        x0, y0, x1, y1 = block.get("clear_bounds", block["bounds"])
        allowed.update(y * indices.width + x for y in range(y0, y1) for x in range(x0, x1))
    illegal = [
        position for position, (left, right) in enumerate(zip(original_indices.tobytes(), indices.tobytes()))
        if left != right and position not in allowed
    ]
    if illegal:
        raise ValueError(f"pixel changed outside declared masks: {illegal[0]}")
    patched_anime = anime_assets.replace_texture_indices(anime, record, texture_index, indices)
    if len(patched_anime) != len(anime):
        raise ValueError("anime00.dat size changed")
    patched = bytearray(source)
    patched[entry.data_start:entry.data_end] = patched_anime
    output = bytes(patched)
    changed_bytes = [i for i, (left, right) in enumerate(zip(source, output)) if left != right]
    physical_start = entry.data_start + texture_start
    physical_end = physical_start + texture.size
    if any(not physical_start <= offset < physical_end for offset in changed_bytes):
        raise ValueError("start.dat changed outside the title texture payload")
    output_dir.mkdir(parents=True, exist_ok=True)
    start_output = output_dir / "start.dat"
    anime_output = output_dir / "anime00.dat"
    preview_output = output_dir / "title_texture_kr.png"
    diff_output = output_dir / "title_texture_diff.png"
    start_output.write_bytes(output)
    anime_output.write_bytes(patched_anime)
    preview_wrapped = anime_assets.texture_as_txp(patched_anime, record, texture_index)
    txp_assets.decode_txp(preview_wrapped).save(preview_output)
    diff = Image.new("RGBA", indices.size, (0, 0, 0, 0))
    diff_pixels = diff.load()
    for position, (left, right) in enumerate(zip(original_indices.tobytes(), indices.tobytes())):
        if left != right:
            diff_pixels[position % indices.width, position // indices.width] = (255, 0, 255, 255)
    diff.save(diff_output)
    report = {
        "schema_version": 1,
        "gate_id": config["gate_id"],
        "status": "PASS: fixed-size title/menu texture generated; runtime pending",
        "input": {"path": start_path.as_posix(), "size": len(source), "sha256": sha256(source)},
        "fonts": {
            "regular": {"path": font_path.as_posix(), "sha256": sha256(font_path.read_bytes())},
            "bold": {"path": bold_font_path.as_posix(), "sha256": sha256(bold_font_path.read_bytes())},
        },
        "target": {
            "entry_name": entry.name, "record_index": record.index,
            "texture_index": texture_index, "width": texture.width, "height": texture.height,
            "bits_per_pixel": texture.bits_per_pixel, "swizzled": texture.swizzled,
            "physical_start": f"0x{physical_start:X}", "physical_end_exclusive": f"0x{physical_end:X}",
        },
        "blocks": block_reports,
        "output": {
            "path": start_output.as_posix(), "size": len(output), "sha256": sha256(output),
            "same_size_as_input": len(output) == len(source), "changed_bytes": len(changed_bytes),
            "preview": preview_output.as_posix(), "diff_mask": diff_output.as_posix(),
        },
        "expected_write": {
            "pixel_masks_only": True, "non_target_pixels_preserved": True,
            "ANIME_descriptors_and_palettes_preserved": True,
            "start_index_and_non_target_entries_preserved": True,
        },
        "runtime_gate": {"status": "PENDING", "reason": "LZS, SYSTEM.DAT, ISO and PPSSPP remain"},
    }
    (output_dir / "title_graphics_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("start", type=Path)
    parser.add_argument("font", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--bold-font", type=Path)
    args = parser.parse_args()
    print(json.dumps(
        build(args.config, args.start, args.font, args.output_dir, args.bold_font),
        ensure_ascii=False, indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
