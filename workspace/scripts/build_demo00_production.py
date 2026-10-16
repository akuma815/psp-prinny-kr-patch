#!/usr/bin/env python3
"""Build deterministic production Hangul font assets and fixed-slot Demo00.dat."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from dataclasses import replace
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw

import build_font_poc
import demo00
import font_assets


TXP_HEADER_SIZE = 0x50
BYTES_PER_GLYPH = 140
REVIEW_STATUSES = {"needs_review", "needs_human_review", "in_progress"}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_blob(name: str, data: bytes, expected: dict[str, object]) -> None:
    if len(data) != int(expected["size"]):
        raise ValueError(f"{name} size mismatch")
    actual = sha256(data)
    if actual != expected["sha256"]:
        raise ValueError(f"{name} SHA-256 mismatch: {actual}")


def supported_trails(profile: dict[str, object]) -> tuple[int, ...]:
    allocation = profile["allocation"]
    values: list[int] = []
    for start, end in allocation["trail_ranges"]:
        values.extend(range(int(start, 0), int(end, 0) + 1))
    if len(values) != len(set(values)) or 0x7F in values:
        raise ValueError("allocation trail ranges overlap or include 0x7F")
    return tuple(values)


def allocation_codes(profile: dict[str, object]) -> tuple[bytes, ...]:
    allocation = profile["allocation"]
    leads = range(int(allocation["lead_start"], 0), int(allocation["lead_end"], 0) + 1)
    return tuple(bytes((lead, trail)) for lead in leads for trail in supported_trails(profile))


def target_characters(artifact: dict[str, object]) -> tuple[set[str], list[dict[str, object]]]:
    entries = artifact.get("entries", [])
    if not isinstance(entries, list):
        raise ValueError("translation artifact entries are missing")
    complete: list[dict[str, object]] = []
    characters: set[str] = set()
    for entry in entries:
        translation = entry["translation"]
        status = translation["status"]
        if status in REVIEW_STATUSES:
            raise ValueError(f"review is incomplete for {entry['entry_id']}")
        if status == "complete":
            complete.append(entry)
            characters.update(translation["speaker"])
            for line in translation["lines"]:
                characters.update(line)
        elif status != "untranslated":
            raise ValueError(f"unsupported translation status {status!r}")
    return characters, complete


def encode_text(text: str, mapping: dict[str, bytes]) -> bytes:
    output = bytearray()
    for character in text:
        if character in mapping:
            output.extend(mapping[character])
            continue
        try:
            encoded = character.encode("cp932", errors="strict")
        except UnicodeEncodeError as error:
            raise ValueError(f"unmapped character U+{ord(character):04X}") from error
        if len(encoded) == 1:
            font_assets.dense_cp932_index(encoded)
        elif len(encoded) == 2:
            font_assets.dense_cp932_index(encoded)
        else:
            raise ValueError(f"unsupported encoded width for U+{ord(character):04X}")
        output.extend(encoded)
    return bytes(output)


def decode_text(raw: bytes, reverse_mapping: dict[bytes, str]) -> str:
    output: list[str] = []
    cursor = 0
    while cursor < len(raw):
        value = raw[cursor]
        if 0x81 <= value <= 0x9F or 0xE0 <= value <= 0xFC:
            if cursor + 1 >= len(raw):
                raise ValueError("truncated double-byte character")
            unit = raw[cursor:cursor + 2]
            cursor += 2
        else:
            unit = raw[cursor:cursor + 1]
            cursor += 1
        if unit in reverse_mapping:
            output.append(reverse_mapping[unit])
        else:
            output.append(unit.decode("cp932", errors="strict"))
    return "".join(output)


def encode_slot(text: str, size: int, mapping: dict[str, bytes], field: str) -> bytes:
    payload = encode_text(text, mapping)
    if len(payload) >= size:
        raise ValueError(
            f"{field} requires {len(payload) + 1} bytes including NUL, slot is {size}"
        )
    return payload + bytes(size - len(payload))


def slot_payload(raw: bytes) -> bytes:
    payload, separator, padding = raw.partition(b"\0")
    if not separator or any(padding):
        raise ValueError("rebuilt fixed slot has invalid termination or padding")
    return payload


def diff_indexes(before: bytes, after: bytes) -> list[int]:
    if len(before) != len(after):
        raise ValueError("diff_indexes requires equal-sized inputs")
    return [index for index, pair in enumerate(zip(before, after)) if pair[0] != pair[1]]


def preview_sheet(
    characters: Iterable[str], font_path: Path, profile: dict[str, object], output: Path
) -> None:
    chars = list(characters)
    scale = 2
    columns = 24
    rows = (len(chars) + columns - 1) // columns
    image = Image.new("L", (columns * 20 * scale, rows * 14 * scale), 0)
    for index, character in enumerate(chars):
        cell = build_font_poc.rasterize(character, font_path, profile)
        cell = cell.resize((40, 28), Image.Resampling.NEAREST)
        image.paste(cell, ((index % columns) * 40, (index // columns) * 28))
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def build(
    profile_path: Path,
    artifact_path: Path,
    reclaim_report_path: Path,
    font_path: Path,
    font_fnt_path: Path,
    font_txp_path: Path,
    demo00_path: Path,
    output_dir: Path,
) -> dict[str, object]:
    profile = load_json(profile_path)
    artifact = load_json(artifact_path)
    reclaim_report = load_json(reclaim_report_path)
    if profile.get("schema_version") != 1:
        raise ValueError("unsupported production profile schema")
    if artifact.get("source", {}).get("sha256") != profile["inputs"]["Demo00.dat"]["sha256"]:
        raise ValueError("translation artifact source identity is stale")

    source_font = font_path.read_bytes()
    if sha256(source_font) != profile["source_font"]["sha256"]:
        raise ValueError("source TTF SHA-256 mismatch")
    font_fnt = font_fnt_path.read_bytes()
    font_txp = font_txp_path.read_bytes()
    demo_source = demo00_path.read_bytes()
    verify_blob("font.fnt", font_fnt, profile["inputs"]["font.fnt"])
    verify_blob("font.txp", font_txp, profile["inputs"]["font.txp"])
    verify_blob("Demo00.dat", demo_source, profile["inputs"]["Demo00.dat"])

    characters, complete_entries = target_characters(artifact)
    hangul = tuple(sorted(c for c in characters if "가" <= c <= "힣"))
    non_hangul = tuple(sorted(characters - set(hangul)))
    for character in non_hangul:
        encode_text(character, {})
    expected = profile["expected"]
    if sha256(reclaim_report_path.read_bytes()) != expected["reclaim_report_sha256"]:
        raise ValueError("fixed-size glyph reclaim report hash changed")
    if reclaim_report.get("status") != "PASS":
        raise ValueError("fixed-size glyph reclaim gate is not PASS")
    if len(complete_entries) != int(expected["complete_entries"]):
        raise ValueError("approved entry count differs from production profile")
    if len(artifact["entries"]) - len(complete_entries) != int(expected["excluded_entries"]):
        raise ValueError("excluded entry count differs from production profile")
    if len(hangul) != int(expected["hangul_syllables"]):
        raise ValueError("Hangul demand differs from production profile")

    map_count, = struct.unpack_from("<H", font_fnt)
    original_map = list(struct.unpack_from(f"<{map_count}H", font_fnt, 2))
    txp_width, txp_height, pixel_format = struct.unpack_from("<HHH", font_txp)
    if (txp_width, pixel_format) != (20, 0x10):
        raise ValueError("font.txp geometry or format changed")
    original_pixels = len(font_txp) - TXP_HEADER_SIZE
    if original_pixels % BYTES_PER_GLYPH:
        raise ValueError("original font.txp has a partial glyph cell")
    original_glyphs = original_pixels // BYTES_PER_GLYPH
    if original_glyphs != int(expected["original_glyphs"]) or txp_height != original_glyphs * 14:
        raise ValueError("original glyph count or texture height changed")

    table = demo00.parse(demo_source)
    original_text_payloads = [
        slot_payload(raw)
        for record in table.records
        for raw in (record.speaker_raw, *record.lines_raw)
    ]
    candidates = allocation_codes(profile)
    source_conflicts = {
        code for code in candidates
        if any(code in payload for payload in original_text_payloads)
    }
    selected: list[bytes] = []
    for code in candidates:
        if code in source_conflicts:
            continue
        dense_index = font_assets.dense_cp932_index(code)
        if dense_index >= map_count:
            continue
        if profile["allocation"]["require_original_blank_map_entry"] and original_map[dense_index] != 0:
            continue
        selected.append(code)
        if len(selected) == len(hangul):
            break
    if len(selected) != len(hangul):
        raise ValueError(f"only {len(selected)} safe allocation codes for {len(hangul)} Hangul")
    char_to_code = dict(zip(hangul, selected))
    reverse_mapping = {code: char for char, code in char_to_code.items()}
    patched_map = list(original_map)
    reclaim_glyphs = tuple(reclaim_report["supply"]["selected_glyph_ids"])
    if len(reclaim_glyphs) != len(hangul) or len(set(reclaim_glyphs)) != len(hangul):
        raise ValueError("fixed-size reclaim selection does not match Hangul demand")
    if any(not 0 < glyph_id < original_glyphs for glyph_id in reclaim_glyphs):
        raise ValueError("fixed-size reclaim glyph ID is outside the original font")
    mapping_rows: list[dict[str, object]] = []
    output_txp = bytearray(font_txp)
    for character, code, glyph_id in zip(hangul, selected, reclaim_glyphs):
        dense_index = font_assets.dense_cp932_index(code)
        patched_map[dense_index] = glyph_id
        cell = build_font_poc.rasterize(character, font_path, profile)
        packed = build_font_poc.pack_4bpp_low_first(
            cell, int(profile["target"]["palette_levels"])
        )
        if len(packed) != BYTES_PER_GLYPH:
            raise ValueError("rasterizer emitted an invalid glyph cell")
        glyph_start = TXP_HEADER_SIZE + glyph_id * BYTES_PER_GLYPH
        output_txp[glyph_start:glyph_start + BYTES_PER_GLYPH] = packed
        mapping_rows.append(
            {
                "character": character,
                "codepoint": f"U+{ord(character):04X}",
                "cp932_hex": code.hex().upper(),
                "dense_index": dense_index,
                "glyph_id": glyph_id,
            }
        )

    expanded_glyphs = original_glyphs
    expanded_height = txp_height
    if expanded_glyphs != int(expected["expanded_glyphs"]):
        raise ValueError("expanded glyph count differs from production profile")
    if expanded_height != int(expected["expanded_texture_height"]) or expanded_height > 0xFFFF:
        raise ValueError("expanded texture height is invalid")
    if set(patched_map) != set(range(expanded_glyphs)):
        raise ValueError("patched font map does not preserve the original glyph range")

    output_fnt = bytearray(font_fnt)
    struct.pack_into(f"<{map_count}H", output_fnt, 2, *patched_map)
    if (len(output_txp) - TXP_HEADER_SIZE) * 2 != txp_width * expanded_height:
        raise ValueError("fixed-size font.txp header and payload disagree")

    artifact_by_id = {entry["entry_id"]: entry for entry in artifact["entries"]}
    records = list(table.records)
    allowed_changes: set[int] = set()
    slot_maximum = 0
    for record in table.records:
        entry_id = f"demo00/{record.record_id:04X}"
        entry = artifact_by_id.get(entry_id)
        if entry is None:
            raise ValueError(f"translation artifact missing {entry_id}")
        if entry["protected"]["raw_hex"] != record.to_bytes().hex():
            raise ValueError(f"protected raw record is stale for {entry_id}")
        translation = entry["translation"]
        if translation["status"] == "untranslated":
            continue
        if translation["status"] != "complete":
            raise ValueError(f"non-build-eligible status for {entry_id}")
        speaker_raw = encode_slot(
            translation["speaker"], demo00.SPEAKER_SIZE, char_to_code, f"{entry_id} speaker"
        )
        lines_raw = tuple(
            encode_slot(line, demo00.LINE_SIZE, char_to_code, f"{entry_id} line {index}")
            for index, line in enumerate(translation["lines"])
        )
        slot_maximum = max(
            slot_maximum,
            len(slot_payload(speaker_raw)),
            *(len(slot_payload(line)) for line in lines_raw),
        )
        if decode_text(slot_payload(speaker_raw), reverse_mapping) != translation["speaker"]:
            raise ValueError(f"speaker round-trip failed for {entry_id}")
        for index, raw in enumerate(lines_raw):
            if decode_text(slot_payload(raw), reverse_mapping) != translation["lines"][index]:
                raise ValueError(f"line round-trip failed for {entry_id}/{index}")
        records[record.index] = replace(record, speaker_raw=speaker_raw, lines_raw=lines_raw)
        record_offset = demo00.HEADER.size + record.index * demo00.RECORD_SIZE
        allowed_changes.update(range(record_offset + 7, record_offset + 24))
        for line_offset in demo00.LINE_OFFSETS:
            allowed_changes.update(range(record_offset + line_offset, record_offset + line_offset + demo00.LINE_SIZE))

    output_demo = demo00.Table(tuple(records), table.footer).to_bytes()
    if len(output_demo) != len(demo_source):
        raise ValueError("production Demo00.dat size changed")
    demo_changes = diff_indexes(demo_source, output_demo)
    if not demo_changes or not set(demo_changes) <= allowed_changes:
        raise ValueError("Demo00.dat changed outside approved fixed string slots")
    reparsed = demo00.parse(output_demo)
    for before, after in zip(table.records, reparsed.records):
        if before.to_bytes()[:7] != after.to_bytes()[:7] or before.tail != after.tail:
            raise ValueError("Demo00 control metadata changed")

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "font.fnt").write_bytes(bytes(output_fnt))
    (output_dir / "font.txp").write_bytes(bytes(output_txp))
    (output_dir / "Demo00.dat").write_bytes(output_demo)
    mapping_document = {
        "schema_version": 1,
        "mapping_id": "demo00/production-hangul-cp932-v1",
        "profile": profile["profile_id"],
        "assignment_order": profile["allocation"]["assignment_order"],
        "entry_count": len(mapping_rows),
        "entries": mapping_rows,
    }
    (output_dir / "hangul_mapping.json").write_text(
        json.dumps(mapping_document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    preview_sheet(hangul, font_path, profile, output_dir / "hangul_preview.png")

    report = {
        "schema_version": 1,
        "gate_id": "DEMO00-PRODUCTION-ASSETS-001",
        "status": "PASS: deterministic Hangul allocation, fixed-size reclaimed font, and fixed-slot Demo00 built",
        "inputs": {
            "profile": profile_path.as_posix(),
            "translation_artifact": artifact_path.as_posix(),
            "reclaim_report": reclaim_report_path.as_posix(),
            "source_font_sha256": sha256(source_font),
            "font.fnt_sha256": sha256(font_fnt),
            "font.txp_sha256": sha256(font_txp),
            "Demo00.dat_sha256": sha256(demo_source),
        },
        "demand": {
            "complete_entries": len(complete_entries),
            "excluded_entries": len(artifact["entries"]) - len(complete_entries),
            "distinct_characters": len(characters),
            "hangul_syllables": len(hangul),
            "non_hangul_characters": len(non_hangul),
            "unencodable_characters": 0,
        },
        "allocation": {
            "candidate_region": "CP932 user-defined F0-F9",
            "candidate_codes": len(candidates),
            "source_text_conflicts_skipped": len(source_conflicts),
            "source_text_conflict_codes": [code.hex().upper() for code in sorted(source_conflicts)],
            "selected_codes": len(selected),
            "first_code": selected[0].hex().upper(),
            "last_code": selected[-1].hex().upper(),
            "all_original_map_entries_blank": True,
            "selected_codes_absent_from_original_Demo00": True,
            "reclaimed_original_glyphs": len(reclaim_glyphs),
            "reclaimable_supply": reclaim_report["supply"]["reclaimable_glyphs"],
            "reclaim_surplus": reclaim_report["supply"]["surplus"],
        },
        "outputs": {
            "font.fnt": {"size": len(output_fnt), "sha256": sha256(bytes(output_fnt))},
            "font.txp": {
                "size": len(output_txp),
                "sha256": sha256(bytes(output_txp)),
                "original_glyphs": original_glyphs,
                "expanded_glyphs": expanded_glyphs,
                "height": expanded_height,
            },
            "Demo00.dat": {
                "size": len(output_demo),
                "sha256": sha256(output_demo),
                "same_size_as_original": True,
                "actually_changed_bytes": len(demo_changes),
                "all_changes_inside_approved_string_slots": True,
                "control_metadata_byte_identical": True,
                "maximum_payload_bytes": slot_maximum,
            },
            "mapping": {"entries": len(mapping_rows), "path": "hangul_mapping.json"},
            "preview": "hangul_preview.png",
        },
        "runtime_gate": {
            "status": "PENDING",
            "reason": "fixed-size reclaimed font must still pass start.dat/container and PPSSPP load/render verification",
        },
    }
    (output_dir / "report.json").write_text(
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
    parser.add_argument("demo00", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    report = build(
        args.profile,
        args.artifact,
        args.reclaim_report,
        args.source_font,
        args.font_fnt,
        args.font_txp,
        args.demo00,
        args.output_dir,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
