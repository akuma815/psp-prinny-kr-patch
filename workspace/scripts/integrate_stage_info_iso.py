#!/usr/bin/env python3
"""Insert translated StageInfo00.dat and its extended Hangul font into a Prinny ISO."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
from pathlib import Path

import build_demo00_production as production
import build_font_poc
import compress_nis_lzs
import decompress_nis_lzs
import font_assets
from build_translated_images_iso import (
    extract_iso_targets,
    nispack_payload,
    parse_nispack,
    read_start_entries,
    rebuild_iso,
    replace_nispack_variable,
    replace_start_fixed,
)


TXP_HEADER_SIZE = 0x50
BYTES_PER_GLYPH = 140
STAGE_RECORD_COUNT = 20
STAGE_RECORD_OFFSET = 0x04
STAGE_RECORD_STRIDE = 0x170
STAGE_SLOT_COUNT = 11
STAGE_SLOT_SIZE = 33
STAGE_PAYLOAD_SIZE = 32
STAGE_EXPECTED_SIZE = STAGE_RECORD_OFFSET + STAGE_RECORD_COUNT * STAGE_RECORD_STRIDE + 12


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def load_stage_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != STAGE_RECORD_COUNT * STAGE_SLOT_COUNT:
        raise ValueError(f"unexpected StageInfo row count: {len(rows)}")
    return rows


def extend_font(
    profile: dict[str, object],
    reclaim: dict[str, object],
    mapping_artifact: dict[str, object],
    source_font: Path,
    font_fnt: bytes,
    font_txp: bytes,
    stage_rows: list[dict[str, str]],
) -> tuple[bytes, bytes, dict[str, object], dict[str, bytes], list[dict[str, object]]]:
    count, = struct.unpack_from("<H", font_fnt)
    glyph_map = list(struct.unpack_from(f"<{count}H", font_fnt, 2))
    base_rows = list(mapping_artifact["entries"])
    character_map = mapping_from_rows(base_rows)
    used_glyphs = {int(row["glyph_id"]) for row in base_rows}

    target_hangul = sorted({
        character
        for row in stage_rows
        for character in row.get("ko", "")
        if "\uac00" <= character <= "\ud7a3"
    })
    new_characters = [character for character in target_hangul if character not in character_map]
    available_glyphs = [
        int(glyph)
        for glyph in reclaim["supply"]["candidate_glyph_ids"]
        if int(glyph) not in used_glyphs
    ]
    if len(available_glyphs) < len(new_characters):
        raise ValueError("not enough safely reclaimable glyphs for StageInfo")

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
        raise ValueError("not enough blank CP932 user-defined codes for StageInfo")

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
        cell = build_font_poc.rasterize(character, source_font, profile)
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
    combined_rows = base_rows + new_rows
    output_mapping = {
        "schema_version": 1,
        "mapping_id": "demo00-plus-boot-ui-plus-stage-info/production-hangul-cp932-v1",
        "base_mapping": mapping_artifact.get("mapping_id", ""),
        "entry_count": len(combined_rows),
        "added_entry_count": len(new_rows),
        "entries": combined_rows,
    }
    return (
        bytes(output_fnt),
        bytes(output_txp),
        output_mapping,
        character_map,
        new_rows,
    )


def patch_stage_info(
    source: bytes,
    rows: list[dict[str, str]],
    character_map: dict[str, bytes],
) -> tuple[bytes, list[dict[str, object]]]:
    if len(source) != STAGE_EXPECTED_SIZE:
        raise ValueError(f"unexpected StageInfo00.dat size: {len(source)}")
    if struct.unpack_from("<I", source, 0)[0] != STAGE_RECORD_COUNT:
        raise ValueError("unexpected StageInfo record count")

    output = bytearray(source)
    report_rows: list[dict[str, object]] = []
    for row in rows:
        record_index = int(row["record_index"]) - 1
        slot_index = int(row["slot_index"])
        expected_offset = (
            STAGE_RECORD_OFFSET
            + record_index * STAGE_RECORD_STRIDE
            + 2
            + slot_index * STAGE_SLOT_SIZE
        )
        declared_offset = int(row["source_offset"], 0)
        if declared_offset != expected_offset:
            raise ValueError(f"{row['entry_id']} offset mismatch")
        source_payload = bytes.fromhex(row["source_bytes"])
        slot = source[expected_offset:expected_offset + STAGE_SLOT_SIZE]
        if slot[:len(source_payload)] != source_payload or slot[len(source_payload)] != 0:
            raise ValueError(f"{row['entry_id']} source payload mismatch")

        translation = row.get("ko", "")
        if source_payload and not translation:
            raise ValueError(f"{row['entry_id']} has no Korean translation")
        if not source_payload:
            continue
        payload = encode_text(translation, character_map)
        if len(payload) > STAGE_PAYLOAD_SIZE:
            raise ValueError(
                f"{row['entry_id']} exceeds {STAGE_PAYLOAD_SIZE} bytes: {len(payload)}"
            )
        replacement = payload + bytes(STAGE_SLOT_SIZE - len(payload))
        output[expected_offset:expected_offset + STAGE_SLOT_SIZE] = replacement
        report_rows.append({
            "entry_id": row["entry_id"],
            "offset": f"0x{expected_offset:04X}",
            "encoded_bytes": len(payload),
            "remaining_bytes": STAGE_PAYLOAD_SIZE - len(payload),
        })

    for item in report_rows:
        offset = int(str(item["offset"]), 0)
        slot = bytes(output[offset:offset + STAGE_SLOT_SIZE])
        payload = slot.split(b"\0", 1)[0]
        if not payload or any(slot[len(payload):]):
            raise ValueError(f"{item['entry_id']} failed fixed-slot round-trip")
    return bytes(output), report_rows


def build(args: argparse.Namespace) -> dict[str, object]:
    profile = load_json(args.profile)
    reclaim = load_json(args.reclaim_report)
    if reclaim.get("status") != "PASS":
        raise ValueError("union glyph reclaim gate is not PASS")
    mapping_artifact = load_json(args.base_mapping)
    stage_rows = load_stage_rows(args.stage_csv)

    containers = extract_iso_targets(args.baseline_iso)
    system_entries = parse_nispack(containers["SYSTEM.DAT"])
    start_entry = next((entry for entry in system_entries if entry["name"] == "start.lzs"), None)
    if start_entry is None:
        raise ValueError("SYSTEM.DAT has no start.lzs")
    start_lzs = nispack_payload(containers["SYSTEM.DAT"], start_entry)
    start_dat, extension = decompress_nis_lzs.decompress(start_lzs)
    if extension != "dat":
        raise ValueError(f"unexpected start.lzs extension: {extension}")
    _, entries = read_start_entries(start_dat)
    by_name = {entry.name: entry for entry in entries}
    required = {"font.fnt", "font.txp", "StageInfo00.dat"}
    if not required <= set(by_name):
        raise ValueError(f"start.dat is missing: {sorted(required - set(by_name))}")

    def payload(name: str) -> bytes:
        entry = by_name[name]
        return start_dat[entry.data_start:entry.data_end]

    source_fnt = payload("font.fnt")
    source_txp = payload("font.txp")
    source_stage = payload("StageInfo00.dat")
    output_fnt, output_txp, output_mapping, character_map, new_rows = extend_font(
        profile,
        reclaim,
        mapping_artifact,
        args.source_font,
        source_fnt,
        source_txp,
        stage_rows,
    )
    output_stage, patched_rows = patch_stage_info(source_stage, stage_rows, character_map)

    patched_start = replace_start_fixed(
        start_dat,
        {
            "font.fnt": output_fnt,
            "font.txp": output_txp,
            "StageInfo00.dat": output_stage,
        },
    )
    patched_lzs, lzs_stats = compress_nis_lzs.compress(
        patched_start,
        extension="dat",
        flag=0xD5,
    )
    restored, restored_extension = decompress_nis_lzs.decompress(patched_lzs)
    if restored != patched_start or restored_extension != "dat":
        raise ValueError("patched start.lzs failed self-roundtrip")
    patched_system = replace_nispack_variable(
        containers["SYSTEM.DAT"],
        {"start.lzs": patched_lzs},
    )
    replacements = dict(containers)
    replacements["SYSTEM.DAT"] = patched_system
    iso_reports = rebuild_iso(args.baseline_iso, replacements, args.output_iso)

    args.work_dir.mkdir(parents=True, exist_ok=True)
    (args.work_dir / "StageInfo00.dat").write_bytes(output_stage)
    (args.work_dir / "font.fnt").write_bytes(output_fnt)
    (args.work_dir / "font.txp").write_bytes(output_txp)
    (args.work_dir / "hangul_mapping.json").write_text(
        json.dumps(output_mapping, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report = {
        "schema_version": 1,
        "status": "PASS",
        "baseline_iso": {
            "path": str(args.baseline_iso),
            "sha256": sha256_file(args.baseline_iso),
        },
        "stage_info": {
            "csv": str(args.stage_csv),
            "source_sha256": sha256(source_stage),
            "output_sha256": sha256(output_stage),
            "patched_slots": len(patched_rows),
            "slots": patched_rows,
        },
        "font": {
            "base_mapping_entries": len(mapping_artifact["entries"]),
            "new_hangul": len(new_rows),
            "new_codepoints": [row["codepoint"] for row in new_rows],
            "combined_mapping_entries": len(output_mapping["entries"]),
            "font_fnt_sha256": sha256(output_fnt),
            "font_txp_sha256": sha256(output_txp),
        },
        "start_lzs": {
            "before_size": len(start_lzs),
            "after_size": len(patched_lzs),
            "self_roundtrip": True,
            "tokens": lzs_stats,
        },
        "containers": iso_reports,
        "output_iso": {
            "path": str(args.output_iso),
            "size": args.output_iso.stat().st_size,
            "sha256": sha256_file(args.output_iso),
        },
    }
    (args.work_dir / "integration_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline_iso", type=Path)
    parser.add_argument("stage_csv", type=Path)
    parser.add_argument("profile", type=Path)
    parser.add_argument("reclaim_report", type=Path)
    parser.add_argument("base_mapping", type=Path)
    parser.add_argument("source_font", type=Path)
    parser.add_argument("output_iso", type=Path)
    parser.add_argument("work_dir", type=Path)
    args = parser.parse_args()
    report = build(args)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
