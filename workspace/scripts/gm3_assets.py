#!/usr/bin/env python3
"""Parse and losslessly replace indexed textures in Prinny GM3 stage assets."""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass

from PIL import Image

import txp_assets


GM3_HEADER = struct.Struct("<III")
TEXTURE_HEADER = struct.Struct("<IHHHBBHH")


@dataclass(frozen=True)
class Texture:
    index: int
    offset: int
    size: int
    width: int
    height: int
    palette_count: int
    log2_width: int
    log2_height: int
    swizzled: int
    flags: int

    @property
    def palette_offset(self) -> int:
        return self.offset + TEXTURE_HEADER.size

    @property
    def pixel_offset(self) -> int:
        return self.palette_offset + self.palette_count * 4

    @property
    def bits_per_pixel(self) -> int:
        return 4 if self.palette_count == 16 else 8

    @property
    def row_bytes(self) -> int:
        return self.width * self.bits_per_pixel // 8

    @property
    def pixel_size(self) -> int:
        return self.row_bytes * self.height


@dataclass(frozen=True)
class GM3:
    version: int
    table_count: int
    texture_count: int
    unknown: int
    header_extra: tuple[int, ...]
    model_offset: int
    model_offsets: tuple[int, ...]
    texture_offsets: tuple[int, ...]
    textures: tuple[Texture, ...]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse(data: bytes) -> GM3:
    if len(data) < GM3_HEADER.size + 8:
        raise ValueError("GM3 header is truncated")
    version, table_count, unknown = GM3_HEADER.unpack_from(data)
    if version not in (1, 2, 3):
        raise ValueError(f"unsupported GM3 version: {version}")
    if table_count <= 0 or table_count > 256:
        raise ValueError(f"implausible GM3 table count: {table_count}")
    extra_count = version - 1
    table_offset = GM3_HEADER.size + extra_count * 4
    table_size = (table_count + 1) * 4
    table_end = table_offset + table_size
    if table_end > len(data):
        raise ValueError("GM3 offset table is truncated")
    header_extra = (
        struct.unpack_from(f"<{extra_count}I", data, GM3_HEADER.size)
        if extra_count
        else ()
    )
    offsets = struct.unpack_from(f"<{table_count + 1}I", data, table_offset)
    model_offsets = offsets[:version]
    table_texture_offsets = offsets[version:]
    texture_count = table_count
    model_offset = model_offsets[0]
    if model_offset < table_end:
        raise ValueError("GM3 model offset overlaps its header")
    if tuple(sorted(offsets)) != offsets or len(set(offsets)) != len(offsets):
        raise ValueError("GM3 offsets are not strictly increasing")
    if not table_texture_offsets or table_texture_offsets[-1] >= len(data):
        raise ValueError("GM3 final texture starts outside the file")

    textures = []
    texture_offsets = []
    offset = table_texture_offsets[0]
    for index in range(texture_count):
        texture_offsets.append(offset)
        if offset + TEXTURE_HEADER.size > len(data):
            raise ValueError(f"GM3 texture {index} header is truncated")
        fields = TEXTURE_HEADER.unpack_from(data, offset)
        size, width, height, palette_count, log2_width, log2_height, swizzled, flags = fields
        next_offset = offset + size
        if index + 1 < len(table_texture_offsets):
            expected_next = table_texture_offsets[index + 1]
            if next_offset != expected_next:
                raise ValueError(
                    f"GM3 texture {index} span mismatch: "
                    f"0x{next_offset:X} != 0x{expected_next:X}"
                )
        elif index + 1 == texture_count and next_offset != len(data):
            raise ValueError(
                f"GM3 final texture ends at 0x{next_offset:X}, file ends at 0x{len(data):X}"
            )
        if width <= 0 or height <= 0:
            raise ValueError(f"GM3 texture {index} has empty dimensions")
        if width != 1 << log2_width or height != 1 << log2_height:
            raise ValueError(f"GM3 texture {index} log2 dimensions disagree")
        if palette_count not in (16, 256):
            raise ValueError(f"GM3 texture {index} has unsupported palette size")
        if swizzled not in (0, 1):
            raise ValueError(f"GM3 texture {index} has unknown swizzle flag")
        bits_per_pixel = 4 if palette_count == 16 else 8
        expected_size = (
            TEXTURE_HEADER.size
            + palette_count * 4
            + width * height * bits_per_pixel // 8
        )
        if size != expected_size:
            raise ValueError(
                f"GM3 texture {index} size mismatch: 0x{size:X} != 0x{expected_size:X}"
            )
        textures.append(Texture(index, offset, *fields))
        offset = next_offset
    return GM3(
        version,
        table_count,
        texture_count,
        unknown,
        tuple(header_extra),
        model_offset,
        tuple(model_offsets),
        tuple(texture_offsets),
        tuple(textures),
    )


def palette(data: bytes, texture: Texture) -> tuple[tuple[int, int, int, int], ...]:
    start = texture.palette_offset
    return tuple(
        tuple(data[start + index * 4:start + (index + 1) * 4])
        for index in range(texture.palette_count)
    )


def decode_indices(data: bytes, texture: Texture) -> Image.Image:
    raw = data[texture.pixel_offset:texture.pixel_offset + texture.pixel_size]
    if len(raw) != texture.pixel_size:
        raise ValueError(f"GM3 texture {texture.index} pixel payload is truncated")
    if texture.swizzled:
        raw = txp_assets.unswizzle(raw, texture.row_bytes, texture.height)
    if texture.bits_per_pixel == 8:
        indices = raw
    else:
        unpacked = bytearray(texture.width * texture.height)
        for y in range(texture.height):
            row = raw[y * texture.row_bytes:(y + 1) * texture.row_bytes]
            for byte_x, value in enumerate(row):
                x = byte_x * 2
                unpacked[y * texture.width + x] = value & 0x0F
                unpacked[y * texture.width + x + 1] = value >> 4
        indices = bytes(unpacked)
    return Image.frombytes("L", (texture.width, texture.height), indices)


def decode_texture(data: bytes, texture: Texture) -> Image.Image:
    colours = palette(data, texture)
    indices = decode_indices(data, texture).tobytes()
    output = Image.new("RGBA", (texture.width, texture.height))
    output.putdata([colours[index] for index in indices])
    return output


def replace_texture_indices(data: bytes, texture: Texture, indices: Image.Image) -> bytes:
    if indices.mode != "L" or indices.size != (texture.width, texture.height):
        raise ValueError("GM3 replacement indices must be L mode with matching dimensions")
    source = indices.tobytes()
    maximum = texture.palette_count - 1
    if source and max(source) > maximum:
        raise ValueError(f"GM3 replacement index exceeds palette maximum {maximum}")
    if texture.bits_per_pixel == 8:
        linear = source
    else:
        packed = bytearray(texture.row_bytes * texture.height)
        for y in range(texture.height):
            for x in range(0, texture.width, 2):
                low = source[y * texture.width + x]
                high = source[y * texture.width + x + 1]
                packed[y * texture.row_bytes + x // 2] = low | (high << 4)
        linear = bytes(packed)
    payload = (
        txp_assets.swizzle(linear, texture.row_bytes, texture.height)
        if texture.swizzled
        else linear
    )
    output = bytearray(data)
    output[texture.pixel_offset:texture.pixel_offset + texture.pixel_size] = payload
    reparsed = parse(bytes(output))
    if reparsed.textures != parse(data).textures:
        raise ValueError("GM3 texture replacement changed structural metadata")
    return bytes(output)
