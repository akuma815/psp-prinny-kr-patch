#!/usr/bin/env python3
"""Extend the production Hangul font and patch fixed-slot BOOT.BIN UI strings."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

import build_demo00_production as production
import build_font_poc
import font_assets


TXP_HEADER_SIZE = 0x50
BYTES_PER_GLYPH = 140


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def slot_size(source_size: int) -> int:
    return ((source_size + 1 + 3) // 4) * 4


def mapping_from_rows(rows: list[dict[str, object]]) -> dict[str, bytes]:
    return {
        chr(int(str(row["codepoint"])[2:], 16)): bytes.fromhex(str(row["cp932_hex"]))
        for row in rows
    }


def encode_text(text: str, mapping: dict[str, bytes]) -> bytes:
    output = bytearray()
    for character in text:
        if character in mapping:
            output.extend(mapping[character])
        else:
            output.extend(character.encode("cp932", errors="strict"))
    return bytes(output)


def build(args: argparse.Namespace) -> dict[str, object]:
    profile = load_json(args.profile)
    artifact = load_json(args.artifact)
    reclaim = load_json(args.reclaim_report)
    base_mapping_artifact = load_json(args.base_mapping)
    source_boot = args.boot_bin.read_bytes()
    if len(source_boot) != int(artifact["source"]["size"]):
        raise ValueError("BOOT.BIN size mismatch")
    if sha256(source_boot) != artifact["source"]["sha256"]:
        raise ValueError("BOOT.BIN SHA-256 mismatch")
    if reclaim.get("status") != "PASS":
        raise ValueError("union glyph reclaim gate is not PASS")

    font_fnt = args.font_fnt.read_bytes()
    font_txp = args.font_txp.read_bytes()
    count, = struct.unpack_from("<H", font_fnt)
    glyph_map = list(struct.unpack_from(f"<{count}H", font_fnt, 2))
    base_rows = list(base_mapping_artifact["entries"])
    character_map = mapping_from_rows(base_rows)
    base_glyphs = {int(row["glyph_id"]) for row in base_rows}

    target_characters = {
        character
        for entry in artifact["entries"]
        for character in entry["translation"]
        if "\uac00" <= character <= "\ud7a3"
    }
    # build_direct_run.py encodes stage/lucky-doll/clear-time text with this
    # mapping too, so their Hangul demand must be part of the union font.
    for extra_path in getattr(args, "extra_text", None) or []:
        extra_text = extra_path.read_text(encoding="utf-8")
        target_characters.update(
            character
            for character in extra_text
            if "\uac00" <= character <= "\ud7a3"
        )
    target_hangul = sorted(target_characters)
    new_characters = [character for character in target_hangul if character not in character_map]
    available_glyphs = [
        int(glyph)
        for glyph in reclaim["supply"]["candidate_glyph_ids"]
        if int(glyph) not in base_glyphs
    ]
    if len(available_glyphs) < len(new_characters):
        raise ValueError("not enough safely reclaimable glyphs for BOOT UI")

    used_codes = set(character_map.values())
    selected_codes: list[bytes] = []
    for code in production.allocation_codes(profile):
        if code in used_codes:
            continue
        dense_index = font_assets.dense_cp932_index(code)
        if dense_index >= count or glyph_map[dense_index] != 0:
            continue
        selected_codes.append(code)
        if len(selected_codes) == len(new_characters):
            break
    if len(selected_codes) != len(new_characters):
        raise ValueError("not enough blank CP932 user-defined codes for BOOT UI")

    output_txp = bytearray(font_txp)
    new_rows: list[dict[str, object]] = []
    for character, code, glyph_id in zip(
        new_characters,
        selected_codes,
        available_glyphs[:len(new_characters)],
        strict=True,
    ):
        dense_index = font_assets.dense_cp932_index(code)
        glyph_map[dense_index] = glyph_id
        cell = build_font_poc.rasterize(character, args.source_font, profile)
        packed = build_font_poc.pack_4bpp_low_first(
            cell, int(profile["target"]["palette_levels"])
        )
        if len(packed) != BYTES_PER_GLYPH:
            raise ValueError("rasterizer emitted an invalid glyph cell")
        start = TXP_HEADER_SIZE + glyph_id * BYTES_PER_GLYPH
        output_txp[start:start + BYTES_PER_GLYPH] = packed
        character_map[character] = code
        new_rows.append({
            "character": character,
            "codepoint": f"U+{ord(character):04X}",
            "cp932_hex": code.hex().upper(),
            "dense_index": dense_index,
            "glyph_id": glyph_id,
        })

    output_fnt = bytearray(font_fnt)
    struct.pack_into(f"<{count}H", output_fnt, 2, *glyph_map)
    output_boot = bytearray(source_boot)
    patched_slots: list[dict[str, object]] = []
    allowed_changes: set[int] = set()
    for entry in artifact["entries"]:
        offset = int(entry["offset"], 0)
        source_payload = entry["source"].encode("cp932")
        capacity = slot_size(len(source_payload))
        if output_boot[offset:offset + len(source_payload)] != source_payload:
            raise ValueError(f"{entry['offset']} source payload mismatch")
        payload = encode_text(entry["translation"], character_map)
        if len(payload) >= capacity:
            raise ValueError(f"{entry['offset']} translation exceeds fixed slot")
        output_boot[offset:offset + capacity] = payload + bytes(capacity - len(payload))
        allowed_changes.update(range(offset, offset + capacity))
        patched_slots.append({
            "offset": entry["offset"],
            "slot_size": capacity,
            "encoded_bytes": len(payload),
        })
    changed = {
        index for index, pair in enumerate(zip(source_boot, output_boot)) if pair[0] != pair[1]
    }
    if not changed.issubset(allowed_changes):
        raise ValueError("BOOT.BIN changed outside declared fixed slots")

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "font.fnt").write_bytes(output_fnt)
    (args.output / "font.txp").write_bytes(output_txp)
    (args.output / "BOOT.BIN").write_bytes(output_boot)
    # PPSSPP and CFW can load an unencrypted ELF under the EBOOT.BIN filename.
    # Keep this explicit candidate separate from the source encrypted ~PSP file.
    (args.output / "EBOOT.BIN").write_bytes(output_boot)
    combined_rows = base_rows + new_rows
    mapping_artifact = {
        "schema_version": 1,
        "mapping_id": "demo00-plus-boot-ui/production-hangul-cp932-v1",
        "base_mapping": str(args.base_mapping),
        "entry_count": len(combined_rows),
        "added_entry_count": len(new_rows),
        "entries": combined_rows,
    }
    (args.output / "hangul_mapping.json").write_text(
        json.dumps(mapping_artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report = {
        "status": "PASS",
        "source_boot": {
            "size": len(source_boot),
            "sha256": sha256(source_boot),
            "format": "ELF",
        },
        "output_boot": {
            "size": len(output_boot),
            "sha256": sha256(output_boot),
            "changed_bytes": len(changed),
            "patched_slots": len(patched_slots),
        },
        "font": {
            "base_mapping_entries": len(base_rows),
            "new_hangul": len(new_rows),
            "combined_mapping_entries": len(combined_rows),
            "new_codepoints": [row["codepoint"] for row in new_rows],
            "font_fnt_sha256": sha256(output_fnt),
            "font_txp_sha256": sha256(output_txp),
        },
        "deployment": {
            "BOOT.BIN": "replace /PSP_GAME/SYSDIR/BOOT.BIN",
            "EBOOT.BIN": "replace /PSP_GAME/SYSDIR/EBOOT.BIN with the generated plaintext ELF candidate",
            "verification": "pending PPSSPP executable-load and difficulty-screen render test",
        },
        "slots": patched_slots,
    }
    (args.output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("reclaim_report", type=Path)
    parser.add_argument("source_font", type=Path)
    parser.add_argument("font_fnt", type=Path)
    parser.add_argument("font_txp", type=Path)
    parser.add_argument("base_mapping", type=Path)
    parser.add_argument("boot_bin", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--extra-text",
        action="append",
        type=Path,
        default=[],
        help=(
            "additional UTF-8 text files (e.g. stage_info.csv) whose Hangul "
            "characters must also be present in the union mapping"
        ),
    )
    args = parser.parse_args()
    report = build(args)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
