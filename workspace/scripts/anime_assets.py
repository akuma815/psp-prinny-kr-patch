#!/usr/bin/env python3
"""Parse and render the texture sections observed inside Prinny ANIME.DAT entries."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from PIL import Image

import txp_assets


OUTER_HEADER = struct.Struct("<I12x")
PALETTE_DESC = struct.Struct("<II")
TEXTURE_DESC = struct.Struct("<IHH4B")


@dataclass(frozen=True)
class Palette:
    offset: int
    color_count: int


@dataclass(frozen=True)
class Texture:
    offset: int
    width: int
    height: int
    bits_per_pixel: int
    clut_width: int
    clut_height: int
    swizzled: int

    @property
    def size(self) -> int:
        return self.width * self.height * self.bits_per_pixel // 8


@dataclass(frozen=True)
class Record:
    index: int
    offset: int
    size: int
    palettes: tuple[Palette, ...]
    textures: tuple[Texture, ...]


def parse_records(data: bytes) -> tuple[Record, ...]:
    if len(data) < OUTER_HEADER.size:
        raise ValueError("ANIME entry header is truncated")
    count, = OUTER_HEADER.unpack_from(data)
    offset = OUTER_HEADER.size
    records = []
    for index in range(count):
        if offset + 0x30 > len(data):
            raise ValueError(f"ANIME record {index} header is truncated")
        size, = struct.unpack_from("<I", data, offset)
        if size < 0x30 or offset + size > len(data):
            raise ValueError(f"ANIME record {index} has invalid size {size}")
        sub = data[offset:offset + size]
        palette_desc, texture_desc, texture_desc_end = struct.unpack_from("<III", sub, 0x24)
        if not (0 <= palette_desc <= texture_desc <= texture_desc_end <= size):
            raise ValueError(f"ANIME record {index} has invalid descriptor bounds")
        if (texture_desc - palette_desc) % PALETTE_DESC.size:
            raise ValueError(f"ANIME record {index} palette descriptors are misaligned")
        if (texture_desc_end - texture_desc) % TEXTURE_DESC.size:
            raise ValueError(f"ANIME record {index} texture descriptors are misaligned")
        palettes = tuple(
            Palette(*PALETTE_DESC.unpack_from(sub, pos))
            for pos in range(palette_desc, texture_desc, PALETTE_DESC.size)
        )
        textures = tuple(
            Texture(*TEXTURE_DESC.unpack_from(sub, pos))
            for pos in range(texture_desc, texture_desc_end, TEXTURE_DESC.size)
        )
        if not palettes or not textures:
            raise ValueError(f"ANIME record {index} has no palette or texture")
        for palette_index, palette in enumerate(palettes):
            end = palettes[palette_index + 1].offset if palette_index + 1 < len(palettes) else textures[0].offset
            if palette.offset + palette.color_count * 4 != end:
                raise ValueError(f"ANIME record {index} palette {palette_index} span mismatch")
        for texture_index, texture in enumerate(textures):
            if texture.bits_per_pixel not in (4, 8):
                raise ValueError(f"ANIME record {index} texture {texture_index} has unsupported bpp")
            if texture.clut_width != 16 or texture.clut_height != 16:
                raise ValueError(f"ANIME record {index} texture {texture_index} has unknown CLUT shape")
            if texture.swizzled not in (0, 1):
                raise ValueError(f"ANIME record {index} texture {texture_index} has unknown swizzle flag")
            end = textures[texture_index + 1].offset if texture_index + 1 < len(textures) else size
            if texture.offset + texture.size != end:
                raise ValueError(f"ANIME record {index} texture {texture_index} span mismatch")
        records.append(Record(index, offset, size, palettes, textures))
        offset += size
    if offset != len(data):
        raise ValueError(f"ANIME entry has {len(data) - offset} unclaimed trailing bytes")
    return tuple(records)


def palette_for_texture(record: Record, texture_index: int, required: int) -> Palette:
    preferred = record.palettes[min(texture_index, len(record.palettes) - 1)]
    if preferred.color_count >= required:
        return preferred
    for palette in record.palettes:
        if palette.color_count >= required:
            return palette
    raise ValueError(f"no palette supplies {required} colors")


def decode_texture(data: bytes, record: Record, texture_index: int) -> Image.Image:
    texture = record.textures[texture_index]
    required = 16 if texture.bits_per_pixel == 4 else 256
    palette = palette_for_texture(record, texture_index, required)
    base = record.offset
    palette_raw = data[base + palette.offset:base + palette.offset + required * 4]
    pixels = data[base + texture.offset:base + texture.offset + texture.size]
    pixel_format = txp_assets.FORMAT_INDEX4 if texture.bits_per_pixel == 4 else txp_assets.FORMAT_INDEX8
    header = txp_assets.HEADER.pack(
        texture.width, texture.height, pixel_format, 0, required, 1,
        texture.swizzled, 1,
    )
    return txp_assets.decode_txp(header + palette_raw + pixels)


def texture_as_txp(data: bytes, record: Record, texture_index: int) -> bytes:
    """Wrap one ANIME texture and its selected CLUT in the equivalent TXP header."""
    texture = record.textures[texture_index]
    required = 16 if texture.bits_per_pixel == 4 else 256
    palette = palette_for_texture(record, texture_index, required)
    base = record.offset
    palette_raw = data[base + palette.offset:base + palette.offset + required * 4]
    pixels = data[base + texture.offset:base + texture.offset + texture.size]
    pixel_format = txp_assets.FORMAT_INDEX4 if texture.bits_per_pixel == 4 else txp_assets.FORMAT_INDEX8
    header = txp_assets.HEADER.pack(
        texture.width, texture.height, pixel_format, 0, required, 1,
        texture.swizzled, 1,
    )
    return header + palette_raw + pixels


def replace_texture_indices(
    data: bytes, record: Record, texture_index: int, indices: Image.Image
) -> bytes:
    """Replace only one ANIME texture pixel payload, preserving all descriptors and palettes."""
    texture = record.textures[texture_index]
    wrapped = texture_as_txp(data, record, texture_index)
    encoded = txp_assets.encode_indices(wrapped, indices)
    info = txp_assets.parse_txp(encoded)
    replacement = encoded[info.pixel_offset:]
    if len(replacement) != texture.size:
        raise ValueError("encoded ANIME texture size changed")
    start = record.offset + texture.offset
    output = bytearray(data)
    output[start:start + texture.size] = replacement
    return bytes(output)
