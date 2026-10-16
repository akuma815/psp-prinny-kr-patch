#!/usr/bin/env python3
"""Build translated Prinny DIDT0 DLC and an extended-font direct-run PoC."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import struct
from dataclasses import replace
from pathlib import Path

import build_demo00_production as production
import build_font_poc
import compress_nis_lzs
import decompress_nis_lzs
import didt
import font_assets
from build_translated_images_iso import (
    nispack_payload,
    parse_nispack,
    read_start_entries,
    replace_nispack_in_place,
    replace_start_fixed,
)


TXP_HEADER_SIZE = 0x50
BYTES_PER_GLYPH = 140
DDEM_FILES = ("DL0000.EDAT", "DL0001.EDAT", "DL0002.EDAT")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def mapping_from_rows(rows: list[dict[str, object]]) -> dict[str, bytes]:
    return {
        str(row["character"]): bytes.fromhex(str(row["cp932_hex"]))
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


def slot_source(raw: bytes) -> bytes:
    end = raw.index(0)
    if any(raw[end:]):
        raise ValueError("source slot has non-zero bytes after NUL")
    return raw[:end]


def encode_slot(text: str, size: int, mapping: dict[str, bytes], context: str) -> bytes:
    payload = encode_text(text, mapping)
    if len(payload) >= size:
        raise ValueError(f"{context} exceeds {size - 1} bytes: {len(payload)}")
    return payload + bytes(size - len(payload))


def diff_ranges(source: bytes, output: bytes) -> list[dict[str, object]]:
    if len(source) != len(output):
        raise ValueError("fixed-size diff input lengths differ")
    changed = [index for index, (before, after) in enumerate(zip(source, output)) if before != after]
    if not changed:
        return []
    ranges: list[dict[str, object]] = []
    start = previous = changed[0]
    for offset in changed[1:]:
        if offset != previous + 1:
            ranges.append({"start": f"0x{start:08X}", "end": f"0x{previous + 1:08X}"})
            start = offset
        previous = offset
    ranges.append({"start": f"0x{start:08X}", "end": f"0x{previous + 1:08X}"})
    return ranges


def extend_font(
    profile: dict[str, object],
    reclaim: dict[str, object],
    mapping_artifact: dict[str, object],
    source_font: Path,
    font_fnt: bytes,
    font_txp: bytes,
    texts: list[str],
) -> tuple[bytes, bytes, dict[str, object], dict[str, bytes]]:
    count, = struct.unpack_from("<H", font_fnt)
    glyph_map = list(struct.unpack_from(f"<{count}H", font_fnt, 2))
    base_rows = list(mapping_artifact["entries"])
    character_map = mapping_from_rows(base_rows)
    base_glyphs = {int(row["glyph_id"]) for row in base_rows}
    target_hangul = sorted({
        character
        for text in texts
        for character in text
        if "\uac00" <= character <= "\ud7a3"
    })
    new_characters = [character for character in target_hangul if character not in character_map]
    available_glyphs = [
        int(glyph)
        for glyph in reclaim["supply"]["candidate_glyph_ids"]
        if int(glyph) not in base_glyphs
    ]
    if len(available_glyphs) < len(new_characters):
        raise ValueError(
            f"not enough safely reclaimable glyphs: need {len(new_characters)}, "
            f"have {len(available_glyphs)}"
        )
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
        raise ValueError("not enough blank CP932 user-defined codes")

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
        packed = build_font_poc.pack_4bpp_low_first(
            build_font_poc.rasterize(character, source_font, profile),
            int(profile["target"]["palette_levels"]),
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
    artifact = {
        "schema_version": 1,
        "mapping_id": "prinny-dlc/production-hangul-cp932-v1",
        "base_mapping": mapping_artifact.get("mapping_id"),
        "entry_count": len(combined_rows),
        "added_entry_count": len(new_rows),
        "new_characters": new_characters,
        "entries": combined_rows,
    }
    return bytes(output_fnt), bytes(output_txp), artifact, character_map


def patch_ddem(
    source: bytes,
    rows: list[dict[str, str]],
    mapping: dict[str, bytes],
) -> tuple[bytes, dict[str, object]]:
    container = didt.parse(source)
    chunk = container.chunk("DDEM")
    table = didt.parse_ddem(chunk.payload)
    by_id = {int(row["record_id"], 0): row for row in rows}
    if len(by_id) != len(rows) or set(by_id) != {record.record_id for record in table.records}:
        raise ValueError("DDEM CSV record population does not match the source table")
    allowed: set[int] = set()
    output_records: list[didt.DdemRecord] = []
    payload_base = chunk.offset + didt.CHUNK_HEADER.size
    for record in table.records:
        row = by_id[record.record_id]
        if row["status"] != "complete":
            raise ValueError(f"{row['entry_id']} is not complete")
        expected_record_offset = payload_base + 4 + record.index * didt.DDEM_RECORD_SIZE
        if int(row["record_index"]) != record.index or int(row["source_offset"], 0) != expected_record_offset:
            raise ValueError(f"{row['entry_id']} protected record coordinate changed")
        raw = bytearray(record.raw)
        slots = [
            ("speaker", didt.DDEM_SPEAKER_OFFSET, didt.DDEM_SPEAKER_SIZE, record.speaker_raw),
            *(
                (f"line_{index}", offset, didt.DDEM_LINE_SIZE, source_raw)
                for index, (offset, source_raw) in enumerate(
                    zip(didt.DDEM_LINE_OFFSETS, record.lines_raw, strict=True), 1
                )
            ),
        ]
        for field, relative_offset, size, source_raw in slots:
            prefix = "speaker" if field == "speaker" else field
            source_key = f"{prefix}_bytes"
            offset_key = f"{prefix}_offset"
            max_key = f"{prefix}_max_bytes"
            ko_key = f"ko_{prefix}"
            if bytes.fromhex(row[source_key]) != slot_source(source_raw):
                raise ValueError(f"{row['entry_id']} {source_key} changed")
            absolute = expected_record_offset + relative_offset
            if int(row[offset_key], 0) != absolute or int(row[max_key]) != size - 1:
                raise ValueError(f"{row['entry_id']} {prefix} protected boundary changed")
            encoded = encode_slot(row[ko_key], size, mapping, f"{row['entry_id']} {prefix}")
            raw[relative_offset:relative_offset + size] = encoded
            allowed.update(range(absolute, absolute + size))
        output_records.append(didt.DdemRecord(record.index, record.record_id, bytes(raw)))
    output_table = didt.DdemTable(tuple(output_records), table.footer)
    output = container.replace_chunk_payload("DDEM", output_table.to_bytes()).to_bytes()
    changed = {index for index, (before, after) in enumerate(zip(source, output)) if before != after}
    if len(output) != len(source) or not changed <= allowed:
        raise ValueError("DDEM output changed outside registered fixed slots")
    return output, {
        "records": len(table.records),
        "allowed_bytes": len(allowed),
        "changed_bytes": len(changed),
        "diff_ranges": diff_ranges(source, output),
    }


def patch_dsti(
    source: bytes,
    rows: list[dict[str, str]],
    mapping: dict[str, bytes],
) -> tuple[bytes, dict[str, object]]:
    container = didt.parse(source)
    chunk = container.chunk("DSTI")
    table = didt.parse_dsti(chunk.payload)
    dlc_id = f"dl{container.dlc_index:04d}"
    selected = [row for row in rows if row["dlc_id"] == dlc_id]
    by_index = {int(row["slot_index"]): row for row in selected}
    if len(by_index) != didt.DSTI_SLOT_COUNT or set(by_index) != set(range(didt.DSTI_SLOT_COUNT)):
        raise ValueError(f"{dlc_id} DSTI CSV population mismatch")
    output_slots: list[bytes] = []
    allowed: set[int] = set()
    title_row = by_index[0]
    if container.title != title_row["ja"].lstrip("\u3000"):
        raise ValueError(
            f"{title_row['entry_id']} header title does not match the DSTI title"
        )
    title_raw = encode_slot(
        title_row["ko"].lstrip("\u3000"),
        didt.DLC_TITLE_SIZE,
        mapping,
        f"{title_row['entry_id']} header title",
    )
    container = container.replace_title_raw(title_raw)
    allowed.update(range(didt.DLC_TITLE_OFFSET, didt.DLC_TITLE_OFFSET + didt.DLC_TITLE_SIZE))
    payload_base = chunk.offset + didt.CHUNK_HEADER.size
    for index, source_raw in enumerate(table.slots_raw):
        row = by_index[index]
        ja = table.slots[index]
        expected_status = "empty" if not ja else "complete"
        if row["status"] != expected_status:
            raise ValueError(f"{row['entry_id']} status is {row['status']}, expected {expected_status}")
        if bytes.fromhex(row["source_bytes"]) != slot_source(source_raw) or row["ja"] != ja:
            raise ValueError(f"{row['entry_id']} protected source changed")
        absolute = payload_base + didt.DSTI_HEADER_SIZE + index * didt.DSTI_SLOT_SIZE
        if int(row["source_offset"], 0) != absolute or int(row["max_bytes"]) != didt.DSTI_SLOT_SIZE - 1:
            raise ValueError(f"{row['entry_id']} protected boundary changed")
        text = row["ko"] if ja else ""
        output_slots.append(encode_slot(text, didt.DSTI_SLOT_SIZE, mapping, row["entry_id"]))
        if ja:
            allowed.update(range(absolute, absolute + didt.DSTI_SLOT_SIZE))
    output_table = didt.DstiTable(table.header, tuple(output_slots), table.footer)
    output = container.replace_chunk_payload("DSTI", output_table.to_bytes()).to_bytes()
    changed = {index for index, (before, after) in enumerate(zip(source, output)) if before != after}
    if len(output) != len(source) or not changed <= allowed:
        raise ValueError("DSTI output changed outside registered fixed slots")
    return output, {
        "slots": len(table.slots_raw),
        "translated_slots": sum(bool(text) for text in table.slots),
        "header_title": title_row["ko"].lstrip("\u3000"),
        "header_title_offset": f"0x{didt.DLC_TITLE_OFFSET:08X}",
        "allowed_bytes": len(allowed),
        "changed_bytes": len(changed),
        "diff_ranges": diff_ranges(source, output),
    }


def patch_direct_run_system(
    source_system: bytes,
    original_font_fnt: bytes,
    original_font_txp: bytes,
    output_font_fnt: bytes,
    output_font_txp: bytes,
) -> tuple[bytes, dict[str, object]]:
    entries = parse_nispack(source_system)
    by_name = {str(entry["name"]): entry for entry in entries}
    start_lzs_slot = nispack_payload(source_system, by_name["start.lzs"])
    if len(start_lzs_slot) < decompress_nis_lzs.HEADER.size:
        raise ValueError("start.lzs slot is shorter than its header")
    _, _, stored_size, _ = decompress_nis_lzs.HEADER.unpack_from(start_lzs_slot)
    logical_size = stored_size + 4
    if logical_size > len(start_lzs_slot):
        raise ValueError(
            f"start.lzs header exceeds its NISPACK slot: {logical_size} > {len(start_lzs_slot)}"
        )
    start_lzs = start_lzs_slot[:logical_size]
    start, extension = decompress_nis_lzs.decompress(start_lzs)
    if extension != "dat":
        raise ValueError(f"unexpected start.lzs extension: {extension}")
    _, start_entries = read_start_entries(start)
    start_by_name = {entry.name: entry for entry in start_entries}
    for name, expected in (("font.fnt", original_font_fnt), ("font.txp", original_font_txp)):
        entry = start_by_name[name]
        if start[entry.data_start:entry.data_end] != expected:
            raise ValueError(f"direct-run {name} does not match the locked 987-character baseline")
    patched_start = replace_start_fixed(
        start,
        {"font.fnt": output_font_fnt, "font.txp": output_font_txp},
    )
    compressed, stats = compress_nis_lzs.compress(patched_start, extension="dat", flag=0xD5)
    restored, restored_extension = decompress_nis_lzs.decompress(compressed)
    if restored != patched_start or restored_extension != "dat":
        raise ValueError("DLC start.lzs self-roundtrip failed")
    if len(compressed) > len(start_lzs_slot):
        raise ValueError(
            f"DLC start.lzs no longer fits: {len(compressed)} > {len(start_lzs_slot)}"
        )
    padded = compressed + bytes(len(start_lzs_slot) - len(compressed))
    output_system = replace_nispack_in_place(source_system, {"start.lzs": padded})
    return output_system, {
        "source_system_sha256": sha256(source_system),
        "output_system_sha256": sha256(output_system),
        "source_start_lzs_size": len(start_lzs),
        "source_start_lzs_slot_size": len(start_lzs_slot),
        "compressed_start_lzs_size": len(compressed),
        "padding": len(start_lzs_slot) - len(compressed),
        "lzs_stats": stats,
    }


def build(args: argparse.Namespace) -> dict[str, object]:
    if args.output.exists():
        raise ValueError(f"output already exists: {args.output}")
    profile = load_json(args.profile)
    reclaim = load_json(args.reclaim_report)
    mapping_artifact = load_json(args.base_mapping)
    if int(mapping_artifact["entry_count"]) != 987:
        raise ValueError("DLC build requires the locked 987-character final mapping")
    dialogue_rows = {
        filename: load_csv(args.translation_dir / f"{filename[:6].lower()}_ddem.csv")
        for filename in DDEM_FILES
    }
    dsti_rows = load_csv(args.translation_dir / "dlc_stage_info.csv")
    texts = [
        row[field]
        for rows in dialogue_rows.values()
        for row in rows
        for field in ("ko_speaker", "ko_line_1", "ko_line_2", "ko_line_3")
    ] + [row["ko"] for row in dsti_rows]
    original_fnt = args.base_font_fnt.read_bytes()
    original_txp = args.base_font_txp.read_bytes()
    output_fnt, output_txp, output_mapping, character_map = extend_font(
        profile,
        reclaim,
        mapping_artifact,
        args.source_font,
        original_fnt,
        original_txp,
        texts,
    )

    args.output.mkdir(parents=True)
    dlc_output = args.output / "memstick/PSP/GAME/ULJS00150"
    dlc_output.mkdir(parents=True)
    shutil.copy2(args.input_dir / "PARAM.PBP", dlc_output / "PARAM.PBP")
    dlc_reports: dict[str, object] = {}
    for filename in DDEM_FILES:
        source = (args.input_dir / filename).read_bytes()
        after_ddem, ddem_report = patch_ddem(source, dialogue_rows[filename], character_map)
        output, dsti_report = patch_dsti(after_ddem, dsti_rows, character_map)
        if didt.parse(output).to_bytes() != output:
            raise ValueError(f"{filename} final DIDT0 round-trip mismatch")
        (dlc_output / filename).write_bytes(output)
        dlc_reports[filename] = {
            "source_sha256": sha256(source),
            "output_sha256": sha256(output),
            "size": len(output),
            "ddem": ddem_report,
            "dsti": dsti_report,
        }

    direct_output = args.output / "direct_run"
    shutil.copytree(args.base_direct_run, direct_output)
    system_path = direct_output / "PSP_GAME/USRDIR/SYSTEM.DAT"
    output_system, system_report = patch_direct_run_system(
        system_path.read_bytes(),
        original_fnt,
        original_txp,
        output_fnt,
        output_txp,
    )
    system_path.write_bytes(output_system)
    (args.output / "font.fnt").write_bytes(output_fnt)
    (args.output / "font.txp").write_bytes(output_txp)
    (args.output / "hangul_mapping.json").write_text(
        json.dumps(output_mapping, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report = {
        "schema_version": 1,
        "status": "PASS: translated fixed-slot DLC and extended-font direct-run PoC built",
        "scope": "non-distributable runtime PoC; emulator and PSP verification pending",
        "inputs": {
            "base_mapping_sha256": sha256(args.base_mapping.read_bytes()),
            "base_font_fnt_sha256": sha256(original_fnt),
            "base_font_txp_sha256": sha256(original_txp),
            "translation_csv_sha256": {
                path.name: sha256(path.read_bytes())
                for path in sorted(args.translation_dir.glob("*.csv"))
            },
        },
        "font": {
            "base_entries": int(mapping_artifact["entry_count"]),
            "added_entries": int(output_mapping["added_entry_count"]),
            "final_entries": int(output_mapping["entry_count"]),
            "new_characters": output_mapping["new_characters"],
            "remaining_candidate_glyphs": len(reclaim["supply"]["candidate_glyph_ids"])
            - int(output_mapping["entry_count"]),
            "font_fnt_sha256": sha256(output_fnt),
            "font_txp_sha256": sha256(output_txp),
        },
        "dlc": dlc_reports,
        "direct_run": {
            "path": direct_output.as_posix(),
            "system": system_report,
        },
    }
    (args.output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    project = script_dir.parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=project / "original/Prinny DLC")
    parser.add_argument("--translation-dir", type=Path, default=project / "workspace/text/translation/dlc")
    parser.add_argument("--profile", type=Path, default=project / "workspace/config/demo00_production_profile.json")
    parser.add_argument("--reclaim-report", type=Path, default=project / "work/analysis/demo00_boot_ui_fixed_font_reclaim.json")
    parser.add_argument("--base-mapping", type=Path, default=project / "work/builds/direct_run_boot_ui_full_20260729/hangul_mapping.json")
    parser.add_argument("--base-font-fnt", type=Path, default=project / "work/builds/direct_run_boot_ui_full_20260729/font.fnt")
    parser.add_argument("--base-font-txp", type=Path, default=project / "work/builds/direct_run_boot_ui_full_20260729/font.txp")
    parser.add_argument("--source-font", type=Path, default=project.parent.parent / "Font/HancomMalangMalang-Regular.ttf")
    parser.add_argument("--base-direct-run", type=Path, default=project / "work/builds/direct_run_latest")
    parser.add_argument("--output", type=Path, default=project / "work/builds/dlc_kr_20260802_r2")
    args = parser.parse_args()
    report = build(args)
    print(
        f"PASS: {len(report['dlc'])} DLC files, "
        f"{report['font']['added_entries']} new glyphs, "
        f"mapping={report['font']['final_entries']}"
    )
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
