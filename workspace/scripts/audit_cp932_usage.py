#!/usr/bin/env python3
"""Audit CP932 code usage in Prinny's confirmed structured text assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import Counter, defaultdict
from pathlib import Path

import demo00
import font_assets
import music_shop


PRINNY_NAME_RECORD_SIZE = 20
PRINNY_NAME_TEXT_OFFSET = 2
PRINNY_NAME_TEXT_SIZE = 18
PRINNY_NAME_FOOTER_SIZE = 12


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_prinny_names(data: bytes) -> list[str]:
    if len(data) < 4 + PRINNY_NAME_FOOTER_SIZE:
        raise ValueError("PrinnyName.dat is truncated")
    count, = struct.unpack_from("<I", data)
    expected = 4 + count * PRINNY_NAME_RECORD_SIZE + PRINNY_NAME_FOOTER_SIZE
    if len(data) != expected:
        raise ValueError(
            f"PrinnyName.dat size mismatch: count={count} requires {expected}, got {len(data)}"
        )
    names: list[str] = []
    for index in range(count):
        start = 4 + index * PRINNY_NAME_RECORD_SIZE
        record_id, = struct.unpack_from("<H", data, start)
        if record_id != index + 1:
            raise ValueError(f"PrinnyName.dat record ID mismatch at index {index}")
        raw = data[
            start + PRINNY_NAME_TEXT_OFFSET:
            start + PRINNY_NAME_TEXT_OFFSET + PRINNY_NAME_TEXT_SIZE
        ]
        payload, separator, padding = raw.partition(b"\0")
        if not separator or any(padding):
            raise ValueError(f"PrinnyName.dat invalid fixed string at index {index}")
        text = payload.decode("cp932", errors="strict")
        if text.encode("cp932") != payload:
            raise ValueError(f"PrinnyName.dat non-reversible string at index {index}")
        names.append(text)
    if data[-PRINNY_NAME_FOOTER_SIZE:] != bytes(PRINNY_NAME_FOOTER_SIZE):
        raise ValueError("PrinnyName.dat footer is not zero-filled")
    return names


def cp932_units(text: str) -> list[bytes]:
    units: list[bytes] = []
    for character in text:
        raw = character.encode("cp932", errors="strict")
        if len(raw) not in (1, 2) or raw.decode("cp932") != character:
            raise ValueError(f"unsupported CP932 character {character!r}")
        units.append(raw)
    return units


def renderable_codes(glyph_map: tuple[int, ...]) -> dict[bytes, tuple[str, int, int]]:
    candidates = [bytes([value]) for value in range(0x20, 0x7F)]
    for lead in (*range(0x81, 0xA0), *range(0xE0, 0xFD)):
        for trail in (*range(0x40, 0x7F), *range(0x80, 0xFD)):
            candidates.append(bytes((lead, trail)))
    result: dict[bytes, tuple[str, int, int]] = {}
    for code in candidates:
        try:
            character = code.decode("cp932", errors="strict")
            if len(character) != 1 or character.encode("cp932") != code:
                continue
            dense_index = font_assets.dense_cp932_index(code)
        except (UnicodeError, ValueError):
            continue
        if dense_index >= len(glyph_map):
            continue
        glyph_id = glyph_map[dense_index]
        if glyph_id:
            result[code] = (character, dense_index, glyph_id)
    return result


def audit(assets: Path) -> dict[str, object]:
    paths = {
        "Demo00.dat": assets / "Demo00.dat",
        "MusicShop.dat": assets / "MusicShop.dat",
        "PrinnyName.dat": assets / "PrinnyName.dat",
        "font.fnt": assets / "font.fnt",
    }
    raw = {name: path.read_bytes() for name, path in paths.items()}
    texts: dict[str, list[str]] = defaultdict(list)

    demo = demo00.parse(raw["Demo00.dat"])
    for record in demo.records:
        texts["Demo00.dat"].extend((record.speaker, *record.lines))
    music = music_shop.parse(raw["MusicShop.dat"])
    for record in music.records:
        texts["MusicShop.dat"].extend(
            (record.short_name.text, record.display_name.text)
        )
    texts["PrinnyName.dat"].extend(parse_prinny_names(raw["PrinnyName.dat"]))

    total = Counter[bytes]()
    by_asset: dict[str, Counter[bytes]] = {}
    for asset, slots in texts.items():
        counter = Counter(unit for text in slots for unit in cp932_units(text))
        by_asset[asset] = counter
        total.update(counter)

    map_count, = struct.unpack_from("<H", raw["font.fnt"])
    glyph_map = struct.unpack_from(f"<{map_count}H", raw["font.fnt"], 2)
    renderable = renderable_codes(glyph_map)
    unused = sorted(set(renderable) - set(total))

    probes = []
    for source, generated in zip(
        ("\u30d7", "\u30ea", "\u30cb", "\u30fc"),
        ("\uac00", "\uac01", "\ubfb0", "\ud7a3"),
    ):
        code = source.encode("cp932")
        character, dense_index, glyph_id = renderable[code]
        probes.append(
            {
                "source_character": character,
                "generated_character": generated,
                "cp932_hex": code.hex().upper(),
                "dense_index": dense_index,
                "glyph_id": glyph_id,
                "confirmed_corpus_occurrences": total[code],
                "occurrences_by_asset": {
                    asset: counter[code] for asset, counter in by_asset.items()
                },
            }
        )

    return {
        "schema_version": 1,
        "status": "PARTIAL: confirmed structured corpus audited; not a whole-game allocation proof",
        "scope": {
            "assets": {
                name: {
                    "size": len(raw[name]),
                    "sha256": sha256(raw[name]),
                    "text_slots": len(texts[name]),
                    "nonempty_text_slots": sum(bool(value) for value in texts[name]),
                }
                for name in texts
            },
            "total_text_slots": sum(len(value) for value in texts.values()),
            "nonempty_text_slots": sum(
                bool(text) for values in texts.values() for text in values
            ),
        },
        "usage": {
            "total_character_occurrences": sum(total.values()),
            "distinct_cp932_codes": len(total),
            "renderable_nonblank_cp932_codes": len(renderable),
            "unused_renderable_codes_in_confirmed_corpus": len(unused),
            "most_common": [
                {
                    "character": renderable.get(code, (code.decode("cp932"), 0, 0))[0],
                    "cp932_hex": code.hex().upper(),
                    "occurrences": count,
                }
                for code, count in total.most_common(64)
            ],
        },
        "multi_glyph_probe": {
            "display_sequence_source": "\u30d7\u30ea\u30cb\u30fc",
            "display_sequence_generated": "\uac00\uac01\ubfb0\ud7a3",
            "replacements": probes,
            "policy": "temporary global replacement of four confirmed codes; not production allocation",
        },
        "unused_candidate_examples": [
            {
                "character": renderable[code][0],
                "cp932_hex": code.hex().upper(),
                "dense_index": renderable[code][1],
                "glyph_id": renderable[code][2],
            }
            for code in unused[:128]
        ],
        "limitations": [
            "Only Demo00.dat, MusicShop.dat, and PrinnyName.dat have confirmed string boundaries in this audit.",
            "An unused code in this report may still be used by another UI, script, DLC, save data, or executable literal.",
            "Production code allocation remains blocked until all target text consumers are inventoried.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assets", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit(args.assets)
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
