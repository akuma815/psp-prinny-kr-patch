#!/usr/bin/env python3
"""Validate Prinny's font atlas, CP932 map, and JIS/UCS conversion tables."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import defaultdict
from pathlib import Path


ELF_BASE = 0x08804000
ELF_FILE_OFFSET = 84
FONT_NAMES = {
    0x088F758C: "font.fnt",
    0x088F7598: "font.txp",
    0x088F76C4: "jis2ucs.bin",
    0x088F76D0: "ucs2jis.bin",
}
EXPECTED_WORDS = {
    0x0888AF84: 0x3C04088F,  # font.fnt name address
    0x0888AF88: 0x2484758C,
    0x0888AFC8: 0xAC434210,  # store raw font.fnt pointer
    0x0888AFE4: 0x3C04088F,  # font.txp name address
    0x0888AFE8: 0x24847598,
    0x0888B02C: 0xAC434188,  # store raw font.txp pointer
    0x0888B034: 0x24844188,  # initialize TXP object
    0x0888B88C: 0x3C04088F,  # jis2ucs.bin name address
    0x0888B890: 0x248476C4,
    0x0888B8E4: 0x3C04088F,  # ucs2jis.bin name address
    0x0888B8E8: 0x248476D0,
    0x0888B924: 0x0E20E94A,  # jal 0x0883A528: install both tables
    0x08898CA0: 0x8C830088,  # font object +0x88 = font.fnt
    0x08898CB8: 0x94620000,  # first u16 = map entry count
    0x08899738: 0x286100D8,  # active cache cap = 216 glyphs
    0x08899974: 0x24A5FF7F,  # CP932 lead normalization (0x81 path)
    0x08899984: 0x24A5FF3F,  # CP932 lead normalization (0xC1 path)
    0x0889998C: 0x00451021,  # lead * 3
    0x08899990: 0x00021180,  # lead * 192
    0x08899998: 0x2442005F,  # dense index trail bias
    0x088999BC: 0x8C44420C,  # load font.fnt map pointer
    0x088999DC: 0x94840000,  # load mapped glyph ID
    0x08899A30: 0x0E203BD2,  # copy one bitmap row
    0x08899A34: 0x2406000A,  # 10 bytes = 20 pixels at 4bpp
    0x08899A38: 0x2610FFFF,  # 14-row loop counter decrement
}


def _offset(va: int) -> int:
    return ELF_FILE_OFFSET + va - ELF_BASE


def _u32(data: bytes, va: int) -> int:
    return struct.unpack_from("<I", data, _offset(va))[0]


def _cstring(data: bytes, va: int) -> str:
    start = _offset(va)
    return data[start:data.index(0, start)].decode("ascii")


def dense_cp932_index(code: bytes) -> int:
    """Reproduce the supported BOOT renderer's CP932-to-map index formula."""
    if len(code) == 1:
        value = code[0]
        if not 0x20 <= value <= 0x7E:
            raise ValueError("single-byte font code is outside the observed range")
        return value - 0x20
    if len(code) != 2:
        raise ValueError("font code must contain one or two bytes")
    lead, trail = code
    if 0x81 <= lead < 0xA0:
        lead_index = lead - 0x81
    elif 0xE0 <= lead <= 0xFC:
        lead_index = lead - 0xC1
    else:
        raise ValueError("double-byte font code has an unsupported lead byte")
    return lead_index * 192 + trail + 0x1F


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def analyze(
    boot: bytes,
    font_fnt: bytes,
    font_txp: bytes,
    jis2ucs_raw: bytes,
    ucs2jis_raw: bytes,
) -> dict[str, object]:
    if len(font_fnt) < 2 or len(font_fnt) % 2:
        raise ValueError("font.fnt must be an even-sized u16 table")
    map_count, = struct.unpack_from("<H", font_fnt)
    glyph_map = struct.unpack_from(f"<{(len(font_fnt) - 2) // 2}H", font_fnt, 2)
    if map_count != len(glyph_map):
        raise ValueError("font.fnt header does not match its map entry count")

    if len(font_txp) < 0x50:
        raise ValueError("font.txp is truncated")
    width, height, pixel_format, unknown_6, palette_width, palette_height, unknown_c, flags = (
        struct.unpack_from("<8H", font_txp)
    )
    palette_bytes = palette_width * palette_height * 4
    pixel_offset = 0x10 + palette_bytes
    pixel_bytes = len(font_txp) - pixel_offset
    if pixel_format != 0x10:
        raise ValueError("font.txp is not the observed 4bpp indexed format")
    if pixel_bytes * 2 != width * height:
        raise ValueError("font.txp 4bpp payload does not match width and height")
    cell_width, cell_height = 20, 14
    cell_bytes = cell_width * cell_height // 2
    glyph_count = pixel_bytes // cell_bytes
    if pixel_bytes % cell_bytes:
        raise ValueError("font.txp payload is not an integer number of glyph cells")
    if set(glyph_map) != set(range(glyph_count)):
        raise ValueError("font.fnt glyph IDs do not cover the TXP glyph set exactly")

    if len(jis2ucs_raw) != 0x20000 or len(ucs2jis_raw) != 0x20000:
        raise ValueError("JIS/UCS tables must each contain 65,536 u16 entries")
    jis2ucs = struct.unpack("<65536H", jis2ucs_raw)
    ucs2jis = struct.unpack("<65536H", ucs2jis_raw)
    duplicate_targets: dict[int, list[int]] = defaultdict(list)
    for jis, ucs in enumerate(jis2ucs):
        if ucs:
            duplicate_targets[ucs].append(jis)
    duplicates = {
        f"U+{ucs:04X}": [f"0x{jis:04X}" for jis in values]
        for ucs, values in duplicate_targets.items()
        if len(values) > 1
    }

    mismatches = [
        f"0x{va:08X}: expected 0x{expected:08X}, got 0x{_u32(boot, va):08X}"
        for va, expected in EXPECTED_WORDS.items()
        if _u32(boot, va) != expected
    ]
    if mismatches:
        raise ValueError("BOOT font-path fingerprint mismatch: " + "; ".join(mismatches))
    names = {f"0x{va:08X}": _cstring(boot, va) for va in FONT_NAMES}
    if names != {f"0x{va:08X}": name for va, name in FONT_NAMES.items()}:
        raise ValueError("BOOT font asset names do not match the supported revision")

    samples = {}
    for char in ("A", "あ", "ア", "国", "プ"):
        encoded = char.encode("cp932")
        index = dense_cp932_index(encoded)
        samples[f"U+{ord(char):04X}"] = {
            "cp932": encoded.hex().upper(),
            "dense_index": index,
            "glyph_id": glyph_map[index],
            "jis": f"0x{ucs2jis[ord(char)]:04X}",
        }

    jis_assigned = sum(value != 0 for value in jis2ucs)
    ucs_assigned = sum(value != 0 for value in ucs2jis)
    canonical_roundtrips = sum(
        value != 0 and jis2ucs[value] == ucs for ucs, value in enumerate(ucs2jis)
    )
    return {
        "schema_version": 1,
        "supported_revision": "ULJS00150 1.01",
        "files": {
            "font.fnt": {"size": len(font_fnt), "sha256": _sha256(font_fnt)},
            "font.txp": {"size": len(font_txp), "sha256": _sha256(font_txp)},
            "jis2ucs.bin": {"size": len(jis2ucs_raw), "sha256": _sha256(jis2ucs_raw)},
            "ucs2jis.bin": {"size": len(ucs2jis_raw), "sha256": _sha256(ucs2jis_raw)},
        },
        "font_map": {
            "entry_count": map_count,
            "dense_cp932_index_range": [0, map_count - 1],
            "glyph_count": glyph_count,
            "mapped_nonzero_entries": sum(value != 0 for value in glyph_map),
            "unmapped_or_blank_entries": sum(value == 0 for value in glyph_map),
            "glyph_ids_are_exact_range": set(glyph_map) == set(range(glyph_count)),
            "samples": samples,
        },
        "font_texture": {
            "width": width,
            "height": height,
            "pixel_format": f"0x{pixel_format:04X}",
            "unknown_6": unknown_6,
            "palette_width": palette_width,
            "palette_height": palette_height,
            "unknown_c": unknown_c,
            "flags": flags,
            "palette_bytes": palette_bytes,
            "pixel_offset": f"0x{pixel_offset:X}",
            "pixel_bytes": pixel_bytes,
            "bits_per_pixel": 4,
            "cell_width": cell_width,
            "cell_height": cell_height,
            "bytes_per_glyph": cell_bytes,
            "glyph_count": glyph_count,
        },
        "conversion_tables": {
            "endian": "little",
            "entry_width_bits": 16,
            "entry_count_each": 65536,
            "jis2ucs_assigned": jis_assigned,
            "ucs2jis_assigned": ucs_assigned,
            "canonical_ucs_roundtrips": canonical_roundtrips,
            "duplicate_unicode_targets": duplicates,
            "hangul_syllables_mapped": sum(
                ucs2jis[codepoint] != 0 for codepoint in range(0xAC00, 0xD7A4)
            ),
        },
        "runtime_path": {
            "asset_names": names,
            "table_installer": "0x0883A528",
            "font_initializer": "0x08898C90",
            "dialog_renderer": "0x08899698",
            "source_cell": "20x14 pixels, 4bpp, 140 bytes",
            "active_cache": "two 0x8000-byte 256x256 4bpp pages",
            "active_glyph_cap_per_page": 216,
            "cache_layout": "12 columns x 18 rows of 20x14 cells",
        },
        "poc_status": {
            "visibility_gate": "not run",
            "known_blocker": "Hangul syllables have no UCS-to-JIS assignments or glyph cells",
            "next_probe": (
                "Replace one confirmed CP932 code's map target and 20x14 glyph bitmap, "
                "rebuild the unchanged-size assets, then verify the main dialog renderer in PPSSPP."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("boot", type=Path)
    parser.add_argument("font_fnt", type=Path)
    parser.add_argument("font_txp", type=Path)
    parser.add_argument("jis2ucs", type=Path)
    parser.add_argument("ucs2jis", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = analyze(
        args.boot.read_bytes(),
        args.font_fnt.read_bytes(),
        args.font_txp.read_bytes(),
        args.jis2ucs.read_bytes(),
        args.ucs2jis.read_bytes(),
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"OK: wrote {args.output}")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
