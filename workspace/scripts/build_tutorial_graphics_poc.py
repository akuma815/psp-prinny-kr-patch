#!/usr/bin/env python3
"""Build fixed-size Korean tutorial textures inside ANIME.DAT."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

import anime_assets
import inspect_nispack
import txp_assets


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def coverage_index(alpha: int, ramp: list[int]) -> int | None:
    if alpha <= 0:
        return None
    level = round(alpha * len(ramp) / 255)
    return ramp[min(max(level, 1), len(ramp)) - 1]


def fit_font(
    path: Path,
    text: str,
    initial: int,
    minimum: int,
    width: int,
    height: int,
    stroke: int,
    tracking: int = 0,
):
    for size in range(initial, minimum - 1, -1):
        font = ImageFont.truetype(str(path), size)
        box = font.getbbox(text, stroke_width=stroke)
        tracked_width = box[2] - box[0] + tracking * max(0, len(text) - 1)
        if tracked_width <= width and box[3] - box[1] <= height:
            return font, size
    raise ValueError(f"text does not fit its source sprite slot: {text}")


def draw_segment(
    indices: Image.Image,
    segment: dict[str, object],
    font_path: Path,
    font_config: dict[str, object],
    palette: dict[str, object],
) -> dict[str, object]:
    x0, y0, x1, y1 = (int(value) for value in segment["draw_bounds"])
    text = str(segment["text"])
    stroke = int(font_config["stroke"])
    initial_size = int(segment.get("font_size", font_config["size"]))
    minimum_size = int(segment.get("minimum_font_size", font_config["minimum_size"]))
    tracking = int(segment.get("tracking", 0))
    font, fitted_size = fit_font(
        font_path,
        text,
        initial_size,
        minimum_size,
        x1 - x0,
        y1 - y0,
        stroke,
        tracking,
    )
    box = font.getbbox(text, stroke_width=stroke)
    width = box[2] - box[0] + tracking * max(0, len(text) - 1)
    height = box[3] - box[1]
    canvas_size = (width + stroke * 4 + 4, height + stroke * 4 + 4)
    origin = (stroke * 2 + 2 - box[0], stroke * 2 + 2 - box[1])
    outline = Image.new("L", canvas_size, 0)
    fill = Image.new("L", canvas_size, 0)
    outline_draw = ImageDraw.Draw(outline)
    fill_draw = ImageDraw.Draw(fill)
    if tracking == 0:
        outline_draw.text(origin, text, font=font, fill=255, stroke_width=stroke, stroke_fill=255)
        fill_draw.text(origin, text, font=font, fill=255)
    else:
        cursor = float(origin[0])
        for character in text:
            position = (round(cursor), origin[1])
            outline_draw.text(position, character, font=font, fill=255, stroke_width=stroke, stroke_fill=255)
            fill_draw.text(position, character, font=font, fill=255)
            cursor += font.getlength(character) + tracking
    content_box = ImageChops.lighter(outline, fill).getbbox()
    if content_box is None:
        raise ValueError(f"font produced no pixels: {text}")
    outline = outline.crop(content_box)
    fill = fill.crop(content_box)

    align = str(segment.get("align", "center"))
    if align == "left":
        left = x0
    elif align == "right":
        left = x1 - fill.width
    elif align == "center":
        left = x0 + ((x1 - x0) - fill.width) // 2
    else:
        raise ValueError(f"unsupported alignment: {align}")
    top = y0 + ((y1 - y0) - fill.height) // 2
    left += int(segment.get("offset_x", 0))
    top += int(segment.get("offset_y", 0))
    if left < x0 or top < y0 or left + fill.width > x1 or top + fill.height > y1:
        raise ValueError(f"positioned text exceeds source sprite slot: {text}")

    pixels = indices.load()
    outline_ramp = [int(value) for value in palette["outline_alpha"]]
    fill_ramp = [int(value) for value in palette["fill_alpha"]]
    for y in range(outline.height):
        for x in range(outline.width):
            mapped = coverage_index(outline.getpixel((x, y)), outline_ramp)
            if mapped is not None:
                pixels[left + x, top + y] = mapped
    for y in range(fill.height):
        for x in range(fill.width):
            mapped = coverage_index(fill.getpixel((x, y)), fill_ramp)
            if mapped is not None:
                pixels[left + x, top + y] = mapped

    return {
        "text": text,
        "draw_bounds": segment["draw_bounds"],
        "alignment": align,
        "fitted_font_size": fitted_size,
        "tracking": tracking,
        "rendered_width": fill.width,
    }


def draw_block(
    indices: Image.Image,
    block: dict[str, object],
    font_path: Path,
    font_config: dict[str, object],
    palette: dict[str, object],
) -> dict[str, object]:
    cx0, cy0, cx1, cy1 = (int(value) for value in block["clear_bounds"])
    if not (0 <= cx0 < cx1 <= indices.width and 0 <= cy0 < cy1 <= indices.height):
        raise ValueError(f"invalid clear bounds: {block['id']}")
    original = indices.crop((cx0, cy0, cx1, cy1)).tobytes()
    ImageDraw.Draw(indices).rectangle((cx0, cy0, cx1 - 1, cy1 - 1), fill=int(palette["transparent"]))

    segments = block.get("segments")
    if segments is None:
        generated_segment = {
            "text": block["ko"],
            "draw_bounds": block["draw_bounds"],
            "align": block.get("align", "center"),
        }
        for key in ("font_size", "minimum_font_size", "offset_x", "offset_y", "tracking"):
            if key in block:
                generated_segment[key] = block[key]
        segments = [generated_segment]
    segment_reports = []
    for segment in segments:
        x0, y0, x1, y1 = (int(value) for value in segment["draw_bounds"])
        if not (cx0 <= x0 < x1 <= cx1 and cy0 <= y0 < y1 <= cy1):
            raise ValueError(f"segment escapes clear bounds: {block['id']}")
        segment_reports.append(draw_segment(indices, segment, font_path, font_config, palette))

    changed = sum(
        before != after
        for before, after in zip(original, indices.crop((cx0, cy0, cx1, cy1)).tobytes())
    )
    return {
        "id": block["id"],
        "source": block["source"],
        "ko": block["ko"],
        "clear_bounds": block["clear_bounds"],
        "segments": segment_reports,
        "changed_pixels": changed,
    }


def build(config_path: Path, archive_path: Path, font_path: Path, output_dir: Path) -> dict[str, object]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    source = archive_path.read_bytes()
    expected = config["source"]
    if sha256(source) != expected["archive_sha256"]:
        raise ValueError("ANIME.DAT does not match the configured baseline")
    if not font_path.is_file():
        raise ValueError("configured tutorial font is missing")

    entries = inspect_nispack.read_entries(archive_path)
    entry = next((item for item in entries if item.name == expected["entry_name"]), None)
    if entry is None:
        raise ValueError("configured tutorial entry is missing")
    if (entry.index, entry.offset, entry.size) != (
        int(expected["entry_index"]), int(expected["entry_offset"], 0), int(expected["entry_size"])
    ):
        raise ValueError("anime12.dat archive geometry changed")
    anime = source[entry.offset:entry.offset + entry.size]
    if sha256(anime) != expected["entry_sha256"]:
        raise ValueError("anime12.dat hash changed")

    records = anime_assets.parse_records(anime)
    record = records[int(expected["record_index"])]
    if (record.offset, record.size) != (
        int(expected["record_offset"], 0), int(expected["record_size"])
    ):
        raise ValueError("tutorial ANIME record geometry changed")

    relocation_sources: dict[int, Image.Image] = {}
    for relocation in config.get("sprite_relocations", []):
        source_texture_index = int(relocation["source_texture"])
        if source_texture_index not in relocation_sources:
            wrapped = anime_assets.texture_as_txp(anime, record, source_texture_index)
            relocation_sources[source_texture_index] = txp_assets.decode_indices(wrapped)

    patched_anime = anime
    texture_reports = []
    changed_ranges: list[tuple[int, int]] = []
    output_dir.mkdir(parents=True, exist_ok=True)
    preview_dir = output_dir / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)

    for texture_config in config["textures"]:
        texture_index = int(texture_config["texture_index"])
        current_record = anime_assets.parse_records(patched_anime)[int(expected["record_index"])]
        texture = current_record.textures[texture_index]
        if [texture.width, texture.height, texture.bits_per_pixel, texture.swizzled] != texture_config["geometry"]:
            raise ValueError(f"tutorial texture {texture_index} geometry changed")
        texture_start = current_record.offset + texture.offset
        original_payload = anime[texture_start:texture_start + texture.size]
        if sha256(original_payload) != texture_config["payload_sha256"]:
            raise ValueError(f"tutorial texture {texture_index} payload hash changed")

        wrapped = anime_assets.texture_as_txp(patched_anime, current_record, texture_index)
        indices = txp_assets.decode_indices(wrapped)
        if txp_assets.encode_indices(wrapped, indices) != wrapped:
            raise ValueError(f"tutorial texture {texture_index} identity roundtrip failed")
        original_indices = indices.copy()
        occupied: set[int] = set()
        block_reports = []
        for block in texture_config["blocks"]:
            cx0, cy0, cx1, cy1 = (int(value) for value in block["clear_bounds"])
            positions = {y * indices.width + x for y in range(cy0, cy1) for x in range(cx0, cx1)}
            if occupied.intersection(positions):
                raise ValueError(f"overlapping tutorial clear bounds: {block['id']}")
            occupied.update(positions)
            block_reports.append(draw_block(indices, block, font_path, config["font"], config["palette_indices"]))
        relocation_reports = []
        for relocation in config.get("sprite_relocations", []):
            source_texture_index = int(relocation["source_texture"])
            destination_texture_index = int(relocation["destination_texture"])
            sx0, sy0, sx1, sy1 = (int(value) for value in relocation["source_bounds"])
            destination_x, destination_y = (int(value) for value in relocation["destination_xy"])
            transparent = int(relocation.get("transparent", config["palette_indices"]["transparent"]))
            source_indices = relocation_sources[source_texture_index]
            if not (0 <= sx0 < sx1 <= source_indices.width and 0 <= sy0 < sy1 <= source_indices.height):
                raise ValueError(f"invalid sprite relocation source: {relocation['id']}")
            width, height = sx1 - sx0, sy1 - sy0
            if texture_index == source_texture_index:
                positions = {
                    y * indices.width + x
                    for y in range(sy0, sy1)
                    for x in range(sx0, sx1)
                }
                if occupied.intersection(positions):
                    raise ValueError(f"sprite relocation source overlaps a text block: {relocation['id']}")
                ImageDraw.Draw(indices).rectangle((sx0, sy0, sx1 - 1, sy1 - 1), fill=transparent)
                occupied.update(positions)
            if texture_index == destination_texture_index:
                if not (
                    0 <= destination_x < destination_x + width <= indices.width
                    and 0 <= destination_y < destination_y + height <= indices.height
                ):
                    raise ValueError(f"invalid sprite relocation destination: {relocation['id']}")
                source_crop = source_indices.crop((sx0, sy0, sx1, sy1))
                destination_pixels = indices.load()
                copied_pixels = 0
                for y in range(height):
                    for x in range(width):
                        value = source_crop.getpixel((x, y))
                        if value != transparent:
                            destination_pixels[destination_x + x, destination_y + y] = value
                            copied_pixels += 1
                occupied.update(
                    (destination_y + y) * indices.width + destination_x + x
                    for y in range(height)
                    for x in range(width)
                )
                relocation_reports.append({
                    "id": relocation["id"],
                    "source_texture": source_texture_index,
                    "source_bounds": relocation["source_bounds"],
                    "destination_texture": destination_texture_index,
                    "destination_xy": relocation["destination_xy"],
                    "copied_pixels": copied_pixels,
                })
        illegal = [
            pos for pos, (before, after) in enumerate(zip(original_indices.tobytes(), indices.tobytes()))
            if before != after and pos not in occupied
        ]
        if illegal:
            raise ValueError(f"texture {texture_index} changed outside declared rows: {illegal[0]}")

        patched_anime = anime_assets.replace_texture_indices(
            patched_anime, current_record, texture_index, indices
        )
        physical_start = entry.offset + texture_start
        physical_end = physical_start + texture.size
        changed_ranges.append((physical_start, physical_end))
        preview_wrapped = anime_assets.texture_as_txp(
            patched_anime,
            anime_assets.parse_records(patched_anime)[int(expected["record_index"])],
            texture_index,
        )
        preview_path = preview_dir / f"anime12_r00_t{texture_index:02d}_kr.png"
        txp_assets.decode_txp(preview_wrapped).save(preview_path)
        texture_reports.append({
            "texture_index": texture_index,
            "geometry": texture_config["geometry"],
            "physical_start": f"0x{physical_start:X}",
            "physical_end_exclusive": f"0x{physical_end:X}",
            "blocks": block_reports,
            "sprite_relocations": relocation_reports,
            "preview": preview_path.as_posix(),
        })

    if len(patched_anime) != len(anime):
        raise ValueError("anime12.dat size changed")
    output = bytearray(source)
    output[entry.offset:entry.offset + entry.size] = patched_anime
    output_bytes = bytes(output)
    changed_offsets = [i for i, (before, after) in enumerate(zip(source, output_bytes)) if before != after]
    if any(not any(start <= offset < end for start, end in changed_ranges) for offset in changed_offsets):
        raise ValueError("ANIME.DAT changed outside the four tutorial texture payloads")

    archive_output = output_dir / "ANIME.DAT"
    entry_output = output_dir / "anime12.dat"
    archive_output.write_bytes(output_bytes)
    entry_output.write_bytes(patched_anime)
    report = {
        "schema_version": 1,
        "gate_id": config["gate_id"],
        "status": "PASS: fixed-size tutorial textures generated; runtime pending",
        "input": {"path": archive_path.as_posix(), "size": len(source), "sha256": sha256(source)},
        "font": {"path": font_path.as_posix(), "style": "Regular", "sha256": sha256(font_path.read_bytes())},
        "target": {"entry_name": entry.name, "record_index": record.index, "textures": texture_reports},
        "output": {
            "path": archive_output.as_posix(),
            "size": len(output_bytes),
            "sha256": sha256(output_bytes),
            "same_size_as_input": len(output_bytes) == len(source),
            "changed_bytes": len(changed_offsets),
        },
        "expected_write": {
            "declared_text_rows_only": True,
            "non_target_textures_preserved": True,
            "ANIME_descriptors_and_palettes_preserved": True,
            "NISPACK_table_and_non_target_entries_preserved": True,
        },
        "runtime_gate": {"status": "PENDING", "reason": "ISO integration and PPSSPP visual review remain"},
    }
    (output_dir / "tutorial_graphics_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("archive", type=Path)
    parser.add_argument("font", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.config, args.archive, args.font, args.output_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
