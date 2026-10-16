#!/usr/bin/env python3
"""Build the unchanged-size Hancom MalangMalang dialog-font visibility PoC."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import font_assets
import render_font_glyphs


TXP_PIXEL_OFFSET = 0x50
BYTES_PER_GLYPH = 140


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def truetype_codepoints(data: bytes) -> set[int]:
    """Return codepoints with nonzero glyph IDs from Unicode cmap format 4/12."""
    if len(data) < 12:
        raise ValueError("source TTF is truncated")
    num_tables, = struct.unpack_from(">H", data, 4)
    cmap_offset = None
    cmap_length = None
    for index in range(num_tables):
        offset = 12 + index * 16
        tag, _, table_offset, table_length = struct.unpack_from(">4sIII", data, offset)
        if tag == b"cmap":
            cmap_offset, cmap_length = table_offset, table_length
            break
    if cmap_offset is None or cmap_offset + cmap_length > len(data):
        raise ValueError("source TTF has no valid cmap table")
    _, subtable_count = struct.unpack_from(">HH", data, cmap_offset)
    mappings: set[int] = set()
    seen_offsets: set[int] = set()
    for index in range(subtable_count):
        record = cmap_offset + 4 + index * 8
        platform, encoding, relative = struct.unpack_from(">HHI", data, record)
        if platform not in (0, 3) or (platform == 3 and encoding not in (1, 10)):
            continue
        subtable = cmap_offset + relative
        if subtable in seen_offsets:
            continue
        seen_offsets.add(subtable)
        format_id, = struct.unpack_from(">H", data, subtable)
        if format_id == 4:
            length, = struct.unpack_from(">H", data, subtable + 2)
            end = subtable + length
            seg_count_x2, = struct.unpack_from(">H", data, subtable + 6)
            seg_count = seg_count_x2 // 2
            end_codes = subtable + 14
            start_codes = end_codes + seg_count * 2 + 2
            deltas = start_codes + seg_count * 2
            ranges = deltas + seg_count * 2
            if end > len(data) or ranges + seg_count * 2 > end:
                raise ValueError("source TTF cmap format 4 is truncated")
            for segment in range(seg_count):
                stop, = struct.unpack_from(">H", data, end_codes + segment * 2)
                start, = struct.unpack_from(">H", data, start_codes + segment * 2)
                delta, = struct.unpack_from(">h", data, deltas + segment * 2)
                range_offset, = struct.unpack_from(">H", data, ranges + segment * 2)
                for codepoint in range(start, min(stop, 0xFFFE) + 1):
                    if range_offset == 0:
                        glyph_id = (codepoint + delta) & 0xFFFF
                    else:
                        glyph_address = (
                            ranges + segment * 2 + range_offset
                            + (codepoint - start) * 2
                        )
                        if glyph_address + 2 > end:
                            continue
                        glyph_id, = struct.unpack_from(">H", data, glyph_address)
                        if glyph_id:
                            glyph_id = (glyph_id + delta) & 0xFFFF
                    if glyph_id:
                        mappings.add(codepoint)
        elif format_id == 12:
            length, = struct.unpack_from(">I", data, subtable + 4)
            groups, = struct.unpack_from(">I", data, subtable + 12)
            end = subtable + length
            if end > len(data) or subtable + 16 + groups * 12 > end:
                raise ValueError("source TTF cmap format 12 is truncated")
            for group in range(groups):
                start, stop, glyph = struct.unpack_from(
                    ">III", data, subtable + 16 + group * 12
                )
                first = start if glyph else start + 1
                mappings.update(range(first, stop + 1))
    if not mappings:
        raise ValueError("source TTF has no supported Unicode cmap")
    return mappings


def rasterize(character: str, font_path: Path, profile: dict[str, object]) -> Image.Image:
    target = profile["target"]
    raster = profile["raster"]
    width = int(target["cell_width"])
    height = int(target["cell_height"])
    font = ImageFont.truetype(str(font_path), int(raster["font_size"]))
    bbox = font.getbbox(character)
    if bbox is None:
        raise ValueError(f"source font has no bounds for {character!r}")
    glyph = Image.new("L", (bbox[2] - bbox[0], bbox[3] - bbox[1]), 0)
    ImageDraw.Draw(glyph).text((-bbox[0], -bbox[1]), character, font=font, fill=255)
    scaled_width = max(1, round(glyph.width * float(raster["horizontal_scale"])))
    glyph = glyph.resize((scaled_width, glyph.height), Image.Resampling.LANCZOS)
    if glyph.width > width or glyph.height > height:
        raise ValueError(
            f"rasterized glyph {glyph.size} exceeds target cell {(width, height)}"
        )
    cell = Image.new("L", (width, height), 0)
    x = (width - glyph.width) // 2
    y = (height - glyph.height) // 2
    cell.paste(glyph, (x, y))
    if not cell.getbbox():
        raise ValueError("rasterized glyph is empty")
    return cell


def audit_modern_hangul_cell_fit(
    font_path: Path, profile: dict[str, object]
) -> dict[str, object]:
    """Audit source-font bounds after the configured horizontal scale."""
    target = profile["target"]
    raster = profile["raster"]
    cell_width = int(target["cell_width"])
    cell_height = int(target["cell_height"])
    horizontal_scale = float(raster["horizontal_scale"])
    font = ImageFont.truetype(str(font_path), int(raster["font_size"]))
    maximum_width = 0
    maximum_height = 0
    maximum_width_codepoint = 0
    maximum_height_codepoint = 0
    overflow: list[dict[str, object]] = []
    for codepoint in range(0xAC00, 0xD7A4):
        character = chr(codepoint)
        bbox = font.getbbox(character)
        if bbox is None:
            overflow.append({"codepoint": f"U+{codepoint:04X}", "reason": "no bounds"})
            continue
        width = max(1, round((bbox[2] - bbox[0]) * horizontal_scale))
        height = bbox[3] - bbox[1]
        if width > maximum_width:
            maximum_width = width
            maximum_width_codepoint = codepoint
        if height > maximum_height:
            maximum_height = height
            maximum_height_codepoint = codepoint
        if width > cell_width or height > cell_height:
            overflow.append(
                {
                    "codepoint": f"U+{codepoint:04X}",
                    "character": character,
                    "scaled_bounds": [width, height],
                }
            )
    return {
        "checked_syllables": 11172,
        "cell_size": [cell_width, cell_height],
        "maximum_scaled_width": maximum_width,
        "maximum_scaled_width_codepoint": f"U+{maximum_width_codepoint:04X}",
        "maximum_height": maximum_height,
        "maximum_height_codepoint": f"U+{maximum_height_codepoint:04X}",
        "overflow_count": len(overflow),
        "overflow_examples": overflow[:16],
    }


def pack_4bpp_low_first(cell: Image.Image, levels: int) -> bytes:
    if cell.size != (20, 14):
        raise ValueError("PoC packer only supports the confirmed 20x14 cell")
    indexes = [
        min(levels, round(value * levels / 255))
        for value in cell.get_flattened_data()
    ]
    output = bytearray()
    for offset in range(0, len(indexes), 2):
        output.append(indexes[offset] | indexes[offset + 1] << 4)
    return bytes(output)


def build(
    profile_path: Path,
    font_path: Path,
    font_fnt_path: Path,
    font_txp_path: Path,
    output_dir: Path,
) -> dict[str, object]:
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    source_font = font_path.read_bytes()
    expected_font_hash = profile["source_font"]["sha256"]
    if _sha256(source_font) != expected_font_hash:
        raise ValueError("source TTF hash does not match the font profile")
    codepoints = truetype_codepoints(source_font)
    missing_hangul = [
        codepoint for codepoint in range(0xAC00, 0xD7A4)
        if codepoint not in codepoints
    ]
    if missing_hangul:
        raise ValueError(
            f"source TTF is missing {len(missing_hangul)} modern Hangul syllables"
        )
    cell_fit = audit_modern_hangul_cell_fit(font_path, profile)
    if cell_fit["overflow_count"]:
        raise ValueError(
            "configured raster profile exceeds the 20x14 cell for "
            f"{cell_fit['overflow_count']} modern Hangul syllables"
        )

    font_fnt = font_fnt_path.read_bytes()
    font_txp = font_txp_path.read_bytes()
    map_count, = struct.unpack_from("<H", font_fnt)
    glyph_map = struct.unpack_from(f"<{map_count}H", font_fnt, 2)
    poc = profile["poc"]
    code = bytes.fromhex(poc["temporary_cp932_hex"])
    dense_index = font_assets.dense_cp932_index(code)
    glyph_id = glyph_map[dense_index]
    if dense_index != int(poc["expected_dense_index"]):
        raise ValueError("PoC CP932 dense index changed")
    if glyph_id != int(poc["expected_glyph_id"]):
        raise ValueError("PoC glyph ID changed")

    cell = rasterize(poc["source_character"], font_path, profile)
    packed = pack_4bpp_low_first(cell, int(profile["target"]["palette_levels"]))
    if len(packed) != BYTES_PER_GLYPH:
        raise ValueError("packed PoC glyph is not 140 bytes")
    write_start = TXP_PIXEL_OFFSET + glyph_id * BYTES_PER_GLYPH
    write_end = write_start + BYTES_PER_GLYPH
    original_cell = font_txp[write_start:write_end]
    if len(original_cell) != BYTES_PER_GLYPH:
        raise ValueError("PoC target glyph is outside font.txp")
    if packed == original_cell:
        raise ValueError("PoC glyph produced no change")

    patched_txp = bytearray(font_txp)
    patched_txp[write_start:write_end] = packed
    patched_txp = bytes(patched_txp)
    changed = [index for index, pair in enumerate(zip(font_txp, patched_txp)) if pair[0] != pair[1]]
    if not changed or min(changed) < write_start or max(changed) >= write_end:
        raise ValueError("font PoC changed bytes outside the declared glyph cell")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_txp = output_dir / "font.txp"
    output_fnt = output_dir / "font.fnt"
    output_txp.write_bytes(patched_txp)
    output_fnt.write_bytes(font_fnt)

    mapping, palette, original_pixels = render_font_glyphs.load_font(
        font_fnt_path, font_txp_path
    )
    original_image = render_font_glyphs.render_glyph(
        glyph_id, palette, original_pixels, False
    )
    preview = Image.new("RGBA", (20 * 8 * 2 + 24, 14 * 8 + 28), (28, 32, 40, 255))
    draw = ImageDraw.Draw(preview)
    draw.text((4, 4), f"original U+30D7 / glyph {glyph_id}", fill="white")
    draw.text((20 * 8 + 16, 4), "PoC U+AC00 / Hancom", fill="white")
    preview.alpha_composite(
        original_image.resize((160, 112), Image.Resampling.NEAREST), (4, 24)
    )
    generated_rgba = Image.new("RGBA", cell.size)
    txp_palette = palette
    quantized = [
        min(8, round(value * 8 / 255))
        for value in cell.get_flattened_data()
    ]
    generated_rgba.putdata([txp_palette[value] for value in quantized])
    preview.alpha_composite(
        generated_rgba.resize((160, 112), Image.Resampling.NEAREST), (176, 24)
    )
    preview_path = output_dir / "preview.png"
    preview.save(preview_path)

    report = {
        "schema_version": 1,
        "gate_id": poc["gate_id"],
        "status": "asset built; runtime visibility not yet observed",
        "source_font": {
            "path": font_path.as_posix(),
            "sha256": _sha256(source_font),
            "family": profile["source_font"]["family"],
            "style": profile["source_font"]["style"],
            "license_status": profile["source_font"]["license_status"],
            "license_evidence": profile["source_font"]["license_evidence"],
            "modern_hangul_syllables": 11172,
            "missing_modern_hangul_syllables": len(missing_hangul),
            "configured_cell_fit_audit": cell_fit,
        },
        "replacement": {
            "generated_character": poc["source_character"],
            "temporary_replaced_character": poc["temporary_replaced_character"],
            "cp932_hex": poc["temporary_cp932_hex"],
            "dense_index": dense_index,
            "glyph_id": glyph_id,
            "font_txp_write_start": f"0x{write_start:X}",
            "font_txp_write_end_exclusive": f"0x{write_end:X}",
            "declared_write_bytes": BYTES_PER_GLYPH,
            "actually_changed_bytes": len(changed),
        },
        "outputs": {
            "font.fnt": {
                "size": len(font_fnt),
                "sha256": _sha256(font_fnt),
                "byte_identical_to_original": True,
            },
            "font.txp": {
                "size": len(patched_txp),
                "sha256": _sha256(patched_txp),
                "original_sha256": _sha256(font_txp),
                "same_size_as_original": len(patched_txp) == len(font_txp),
            },
            "preview": preview_path.as_posix(),
        },
        "criteria": {
            "pass": (
                "A readable 가 replaces プ in the PPSSPP main dialog renderer, "
                "neighboring glyphs remain intact, and dialog exit/re-entry is stable."
            ),
            "fail": "The target dialog still shows プ, a wrong glyph, corruption, or a crash.",
            "inconclusive": "The tested screen does not exercise a プ rendered by the confirmed dialog path.",
        },
        "not_proved": [
            "safe production code allocation",
            "full Hangul repertoire capacity",
            "other UI/font renderers",
            "standalone TTF redistribution (excluded from patch scope)",
        ],
    }
    report_path = output_dir / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    parser.add_argument("font", type=Path)
    parser.add_argument("font_fnt", type=Path)
    parser.add_argument("font_txp", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    report = build(args.profile, args.font, args.font_fnt, args.font_txp, args.output_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
