#!/usr/bin/env python3
"""Inspect and render the indexed TXP textures observed in Prinny (PSP)."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


HEADER = struct.Struct("<8H")
FORMAT_INDEX4 = 0x0010
FORMAT_INDEX8 = 0x0100


@dataclass(frozen=True)
class TxpInfo:
    width: int
    height: int
    pixel_format: int
    unknown_06: int
    palette_width: int
    palette_height: int
    swizzled: int
    flags: int
    palette_offset: int
    palette_bytes: int
    pixel_offset: int
    pixel_bytes: int

    @property
    def palette_count(self) -> int:
        return self.palette_width * self.palette_height

    @property
    def row_bytes(self) -> int:
        if self.pixel_format == FORMAT_INDEX4:
            return (self.width + 1) // 2
        if self.pixel_format == FORMAT_INDEX8:
            return self.width
        raise ValueError(f"unsupported TXP pixel format: 0x{self.pixel_format:04X}")


def parse_txp(data: bytes) -> TxpInfo:
    if len(data) < HEADER.size:
        raise ValueError("TXP header is truncated")
    width, height, pixel_format, unknown_06, pal_w, pal_h, swizzled, flags = HEADER.unpack_from(data)
    if not width or not height or not pal_w or not pal_h:
        raise ValueError("TXP dimensions and palette dimensions must be nonzero")
    if pixel_format not in (FORMAT_INDEX4, FORMAT_INDEX8):
        raise ValueError(f"unsupported TXP pixel format: 0x{pixel_format:04X}")
    if swizzled not in (0, 1):
        raise ValueError(f"unsupported TXP swizzle flag: {swizzled}")
    palette_bytes = pal_w * pal_h * 4
    pixel_offset = HEADER.size + palette_bytes
    row_bytes = (width + 1) // 2 if pixel_format == FORMAT_INDEX4 else width
    expected_pixels = row_bytes * height
    if pixel_offset > len(data) or len(data) - pixel_offset != expected_pixels:
        raise ValueError(
            f"TXP payload mismatch: expected {expected_pixels}, "
            f"got {max(0, len(data) - pixel_offset)}"
        )
    # Some 4bpp assets carry up to sixteen 16-color CLUT banks.  The texture
    # indices still select 0..15; the active bank is consumer state.
    if pixel_format == FORMAT_INDEX4 and pal_w * pal_h > 256:
        raise ValueError("4bpp TXP palette contains more than 256 colors")
    if pixel_format == FORMAT_INDEX8 and pal_w * pal_h > 256:
        raise ValueError("8bpp TXP palette contains more than 256 colors")
    if swizzled and (row_bytes % 16 or height % 8):
        raise ValueError("swizzled TXP dimensions do not align to 16-byte x 8-row blocks")
    return TxpInfo(
        width, height, pixel_format, unknown_06, pal_w, pal_h, swizzled, flags,
        HEADER.size, palette_bytes, pixel_offset, expected_pixels,
    )


def unswizzle(data: bytes, row_bytes: int, height: int) -> bytes:
    """Convert PSP 16-byte by 8-row block order to linear rows."""
    if len(data) != row_bytes * height:
        raise ValueError("swizzled payload size does not match dimensions")
    if row_bytes % 16 or height % 8:
        raise ValueError("swizzled payload dimensions are not block aligned")
    output = bytearray(len(data))
    blocks_per_row = row_bytes // 16
    for y in range(height):
        for x in range(row_bytes):
            block = (y // 8) * blocks_per_row + (x // 16)
            source = block * 128 + (y % 8) * 16 + (x % 16)
            output[y * row_bytes + x] = data[source]
    return bytes(output)


def swizzle(data: bytes, row_bytes: int, height: int) -> bytes:
    """Convert linear rows to PSP 16-byte by 8-row block order."""
    if len(data) != row_bytes * height:
        raise ValueError("linear payload size does not match dimensions")
    if row_bytes % 16 or height % 8:
        raise ValueError("linear payload dimensions are not block aligned")
    output = bytearray(len(data))
    blocks_per_row = row_bytes // 16
    for y in range(height):
        for x in range(row_bytes):
            block = (y // 8) * blocks_per_row + (x // 16)
            target = block * 128 + (y % 8) * 16 + (x % 16)
            output[target] = data[y * row_bytes + x]
    return bytes(output)


def decode_txp(data: bytes) -> Image.Image:
    info = parse_txp(data)
    palette = [
        tuple(data[info.palette_offset + i * 4:info.palette_offset + (i + 1) * 4])
        for i in range(info.palette_count)
    ]
    raw = data[info.pixel_offset:]
    if info.swizzled:
        raw = unswizzle(raw, info.row_bytes, info.height)
    image = Image.new("RGBA", (info.width, info.height))
    pixels = image.load()
    if info.pixel_format == FORMAT_INDEX8:
        for y in range(info.height):
            row = raw[y * info.row_bytes:(y + 1) * info.row_bytes]
            for x, index in enumerate(row):
                pixels[x, y] = palette[index]
    else:
        for y in range(info.height):
            row = raw[y * info.row_bytes:(y + 1) * info.row_bytes]
            for byte_x, value in enumerate(row):
                # PSP indexed-4 stores the left pixel in the low nibble.
                for sub_x, index in enumerate((value & 0x0F, value >> 4)):
                    x = byte_x * 2 + sub_x
                    if x < info.width:
                        pixels[x, y] = palette[index]
    return image


def decode_indices(data: bytes) -> Image.Image:
    """Decode a TXP into an L-mode image whose values are palette indices."""
    info = parse_txp(data)
    raw = data[info.pixel_offset:]
    if info.swizzled:
        raw = unswizzle(raw, info.row_bytes, info.height)
    indices = bytearray(info.width * info.height)
    if info.pixel_format == FORMAT_INDEX8:
        for y in range(info.height):
            start = y * info.row_bytes
            indices[y * info.width:(y + 1) * info.width] = raw[start:start + info.width]
    else:
        for y in range(info.height):
            row = raw[y * info.row_bytes:(y + 1) * info.row_bytes]
            for byte_x, value in enumerate(row):
                x = byte_x * 2
                indices[y * info.width + x] = value & 0x0F
                if x + 1 < info.width:
                    indices[y * info.width + x + 1] = value >> 4
    return Image.frombytes("L", (info.width, info.height), bytes(indices))


def encode_indices(original: bytes, indices: Image.Image) -> bytes:
    """Replace only the pixel indices while preserving the original TXP header and CLUT."""
    info = parse_txp(original)
    if indices.mode != "L" or indices.size != (info.width, info.height):
        raise ValueError("index image must be L mode with the original TXP dimensions")
    source = indices.tobytes()
    maximum = 15 if info.pixel_format == FORMAT_INDEX4 else 255
    if source and max(source) > maximum:
        raise ValueError(f"index image contains a value above {maximum}")
    if info.pixel_format == FORMAT_INDEX8:
        linear = source
    else:
        linear_buffer = bytearray(info.row_bytes * info.height)
        for y in range(info.height):
            for x in range(0, info.width, 2):
                low = source[y * info.width + x]
                high = source[y * info.width + x + 1] if x + 1 < info.width else 0
                linear_buffer[y * info.row_bytes + x // 2] = low | (high << 4)
        linear = bytes(linear_buffer)
    payload = swizzle(linear, info.row_bytes, info.height) if info.swizzled else linear
    output = original[:info.pixel_offset] + payload
    parse_txp(output)
    return output


def inventory_record(source: str, index: int, name: str, offset: int, data: bytes) -> dict[str, object]:
    info = parse_txp(data)
    return {
        "asset_id": f"{source}/{name}",
        "source": source,
        "index": index,
        "name": name,
        "offset": offset,
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        **asdict(info),
        "pixel_format": f"0x{info.pixel_format:04X}",
        "palette_banks": info.palette_count // (16 if info.pixel_format == FORMAT_INDEX4 else 256),
        "roundtrip": "byte-identical parse/preserve",
        "state": "not_reviewed",
    }


def make_contact_sheet(
    assets: list[tuple[str, bytes]], output: Path, *, thumb_width: int = 256, columns: int = 4
) -> None:
    label_height = 22
    thumbs: list[tuple[str, Image.Image]] = []
    max_height = 1
    for name, data in assets:
        image = decode_txp(data)
        scale = min(1.0, thumb_width / image.width)
        size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
        thumb = image.resize(size, Image.Resampling.NEAREST)
        max_height = max(max_height, thumb.height)
        thumbs.append((name, thumb))
    rows = (len(thumbs) + columns - 1) // columns
    cell_height = max_height + label_height
    sheet = Image.new("RGBA", (thumb_width * columns, cell_height * rows), (34, 37, 43, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for i, (name, thumb) in enumerate(thumbs):
        x = (i % columns) * thumb_width
        y = (i // columns) * cell_height
        checker = Image.new("RGBA", thumb.size, (96, 96, 96, 255))
        checker.alpha_composite(thumb)
        sheet.alpha_composite(checker, (x + (thumb_width - thumb.width) // 2, y + label_height))
        draw.text((x + 4, y + 4), name, fill=(255, 255, 255, 255), font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("txp", type=Path, nargs="*")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--contact-sheet", type=Path)
    parser.add_argument("--inventory", type=Path)
    args = parser.parse_args()
    if not args.txp:
        parser.error("at least one TXP path is required")
    assets = [(path.name, path.read_bytes()) for path in args.txp]
    for name, data in assets:
        parse_txp(data)
        print(f"OK: {name}")
    if args.output:
        if len(assets) != 1:
            parser.error("--output requires exactly one TXP")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        decode_txp(assets[0][1]).save(args.output)
    if args.contact_sheet:
        make_contact_sheet(assets, args.contact_sheet)
    if args.inventory:
        records = [inventory_record("file", i, name, 0, data) for i, (name, data) in enumerate(assets)]
        args.inventory.parent.mkdir(parents=True, exist_ok=True)
        args.inventory.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
