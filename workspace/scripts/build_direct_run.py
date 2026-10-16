#!/usr/bin/env python3
"""Build a PPSSPP-direct Prinny folder from the clean extracted tree.

This intentionally does not create or modify an ISO.  Every native file is
rebuilt from ``extracted`` plus the reviewed translation artifacts.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import struct
from collections import defaultdict
from pathlib import Path

import build_dialog_punctuation_spacing_patch as punctuation
import build_dialog_typewriter_patch as typewriter
from build_boot_ui_runtime_patch import encode_text
import compress_nis_lzs
import decompress_nis_lzs
from build_translated_images_iso import (
    filename_to_asset_id,
    nispack_payload,
    parse_anime_asset,
    parse_nispack,
    patch_anime_entry,
    patch_txp,
    read_start_entries,
    replace_nispack_fixed,
    replace_nispack_in_place,
    replace_start_fixed,
)
from integrate_boot_ui_assets_iso import merge_slots, slot_rows
from integrate_stage_info_iso import (
    load_stage_rows,
    mapping_from_rows,
    patch_stage_info,
)
from lucky_doll import load_rows as load_lucky_doll_rows
from lucky_doll import patch as patch_lucky_doll
from picture_book import load_rows as load_picture_book_rows
from picture_book import patch as patch_picture_book
import start_tables


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_GAME_FILES = (
    "PSP_GAME/PARAM.SFO",
    "PSP_GAME/SYSDIR/BOOT.BIN",
    "PSP_GAME/SYSDIR/EBOOT.BIN",
    "PSP_GAME/USRDIR/SYSTEM.DAT",
    "PSP_GAME/USRDIR/ANIME.DAT",
    "PSP_GAME/USRDIR/BG.DAT",
    "UMD_DATA.BIN",
)
EXPECTED_CHANGED_FILES = {
    "PSP_GAME/SYSDIR/BOOT.BIN",
    "PSP_GAME/SYSDIR/EBOOT.BIN",
    "PSP_GAME/USRDIR/SYSTEM.DAT",
    "PSP_GAME/USRDIR/ANIME.DAT",
    "PSP_GAME/USRDIR/BG.DAT",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_manifest(root: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        rows.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return rows


def manifest_map(rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {str(row["path"]): row for row in rows}


def verify_clean_tree(root: Path) -> None:
    missing = [relative for relative in REQUIRED_GAME_FILES if not (root / relative).is_file()]
    if missing:
        raise ValueError(f"clean extracted tree is incomplete: {missing}")
    boot = (root / "PSP_GAME/SYSDIR/BOOT.BIN").read_bytes()
    if boot[:4] != b"\x7fELF":
        raise ValueError("clean BOOT.BIN is not a plaintext ELF")


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_artifact(path: Path, expected: dict[str, object], label: str) -> bytes:
    data = path.read_bytes()
    expected_size = int(expected["size"])
    expected_hash = str(expected["sha256"])
    if len(data) != expected_size or sha256(data) != expected_hash:
        raise ValueError(f"{label} no longer matches its build report")
    return data


def patch_clear_time(
    source: bytes,
    artifact: dict[str, object],
    character_map: dict[str, bytes],
) -> tuple[bytes, list[dict[str, object]]]:
    source_spec = dict(artifact["source"])
    translation_spec = dict(artifact["translation"])
    if len(source) != int(source_spec["size"]) or sha256(source) != str(
        source_spec["sha256"]
    ):
        raise ValueError("clean ClearTime00.dat does not match the supported revision")
    record_count = int(source_spec["record_count"])
    record_size = int(source_spec["record_size"])
    text_offset = int(source_spec["text_offset"])
    text_size = int(source_spec["text_size"])
    if int.from_bytes(source[:4], "little") != record_count:
        raise ValueError("ClearTime00.dat record count mismatch")
    source_prefix = str(source_spec["prefix"]).encode("cp932")
    translated_prefix = encode_text(str(translation_spec["prefix"]), character_map)
    suffix_translations = {
        source_text.encode("cp932"): encode_text(translated_text, character_map)
        for source_text, translated_text in dict(
            translation_spec.get("suffixes", {})
        ).items()
    }
    star = "★".encode("cp932")
    output = bytearray(source)
    rows: list[dict[str, object]] = []
    for record_index in range(record_count):
        start = record_index * record_size + text_offset
        field = source[start:start + text_size]
        payload = field.split(b"\0", 1)[0]
        if not payload.startswith(source_prefix):
            raise ValueError(f"ClearTime00.dat record {record_index} prefix mismatch")
        suffix = payload[len(source_prefix):]
        is_stars = not len(suffix) % 2 and all(
            suffix[index:index + 2] == star
            for index in range(0, len(suffix), 2)
        )
        if is_stars:
            translated_suffix = suffix
            suffix_kind = "stars"
            star_count = len(suffix) // 2
        elif suffix in suffix_translations:
            translated_suffix = suffix_translations[suffix]
            suffix_kind = "translated"
            star_count = 0
        else:
            raise ValueError(f"ClearTime00.dat record {record_index} suffix mismatch")
        translated = translated_prefix + translated_suffix
        if len(translated) >= text_size:
            raise ValueError(f"ClearTime00.dat record {record_index} exceeds text field")
        output[start:start + text_size] = translated + bytes(text_size - len(translated))
        rows.append(
            {
                "record_index": record_index,
                "encoded_bytes": len(translated),
                "suffix_kind": suffix_kind,
                "stars": star_count,
            }
        )
    return bytes(output), rows


def translated_assets(translated_dir: Path) -> dict[str, Path]:
    mapped: dict[str, Path] = {}
    for png in sorted(translated_dir.glob("*.png")):
        asset_id = filename_to_asset_id(png)
        if asset_id in mapped:
            raise ValueError(f"duplicate translated asset: {asset_id}")
        mapped[asset_id] = png
    if not mapped:
        raise ValueError("translated PNG directory is empty")
    return mapped


def sjis_to_jis(lead: int, trail: int) -> int:
    """Convert a CP932 double-byte code to the JIS index the game's tables use."""
    row = (lead - 0x81 if lead <= 0x9F else lead - 0xC1) * 2 + 0x21
    if trail <= 0x7E:
        column = trail - 0x1F
    elif trail <= 0x9E:
        column = trail - 0x20
    else:
        column = trail - 0x7E
        row += 1
    return (row << 8) | column


def patch_unicode_tables(
    jis2ucs: bytes, ucs2jis: bytes, mapping_rows: list[dict[str, object]]
) -> tuple[bytes, bytes, dict[str, object]]:
    """Teach start.dat's JIS<->Unicode tables about the custom Hangul codes.

    The game converts its CP932 text to Unicode through these tables before
    handing strings to firmware services such as the save-data dialog.  Our
    Hangul lives in the CP932 user-defined area, which both tables map to
    U+0000, so every Korean string reached the firmware empty and the PSP save
    dialog closed the moment it opened.  The JIS rows the custom codes land on
    are unused in the retail tables, so filling them in is additive.
    """
    forward = bytearray(jis2ucs)
    reverse = bytearray(ucs2jis)
    written = 0
    for row in mapping_rows:
        codepoint = int(str(row["codepoint"])[2:], 16)
        code = bytes.fromhex(str(row["cp932_hex"]))
        if len(code) != 2:
            raise ValueError(f"unexpected CP932 code width: {row['cp932_hex']}")
        jis = sjis_to_jis(code[0], code[1])
        if jis * 2 + 2 > len(forward) or codepoint * 2 + 2 > len(reverse):
            raise ValueError(f"conversion table index out of range for {row}")
        if struct.unpack_from("<H", forward, jis * 2)[0]:
            raise ValueError(f"jis2ucs slot already used for {row['cp932_hex']}")
        if struct.unpack_from("<H", reverse, codepoint * 2)[0]:
            raise ValueError(f"ucs2jis slot already used for {row['codepoint']}")
        struct.pack_into("<H", forward, jis * 2, codepoint)
        struct.pack_into("<H", reverse, codepoint * 2, jis)
        written += 1
    report = {
        "characters": written,
        "jis2ucs_sha256": sha256(bytes(forward)),
        "ucs2jis_sha256": sha256(bytes(reverse)),
    }
    return bytes(forward), bytes(reverse), report


def make_stage_rows(
    stage_csv: Path, stage_mode: str
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    rows = load_stage_rows(stage_csv)
    probes: list[dict[str, str]] = []
    if stage_mode == "full":
        return rows, probes

    rows = copy.deepcopy(rows)
    probe_records = {*range(1, 6), *range(16, 21)}
    for row in rows:
        record_index = int(row["record_index"])
        slot_index = int(row["slot_index"])
        if record_index not in probe_records or slot_index not in (0, 1):
            continue
        marker = (
            f"S{record_index:02d} TITLE"
            if slot_index == 0
            else f"S{record_index:02d} LINE"
        )
        row["ko"] = marker
        probes.append({"entry_id": row["entry_id"], "marker": marker})
    return rows, probes


def patch_native_files(
    clean_root: Path,
    boot_artifact: Path,
    boot_ui_dir: Path,
    demo_dir: Path,
    stage_dir: Path,
    stage_csv: Path,
    lucky_doll_csv: Path,
    picture_book_csv: Path,
    lucky_item_csv: Path,
    collection_csv: Path,
    honor_csv: Path,
    music_shop_csv: Path,
    clear_time_artifact: Path,
    translated_dir: Path,
    stage_mode: str,
    renderer_cache_mode: str = "reuse",
) -> tuple[dict[str, bytes], dict[str, object]]:
    clean_boot = (clean_root / "PSP_GAME/SYSDIR/BOOT.BIN").read_bytes()
    clean_eboot = (clean_root / "PSP_GAME/SYSDIR/EBOOT.BIN").read_bytes()
    # Keep the game's three-line reveal loop completely native.  Runtime
    # comparison showed that removing the broad hook restores the correct
    # per-item description after a selection change.  Use the compact Korean
    # advances only in the renderer; 13/13 kept content correct but visibly
    # separated every glyph and clipped the camera option at the panel edge.
    if renderer_cache_mode == "reuse":
        typewriter_boot, typewriter_report = typewriter.patch_renderer_only(
            clean_boot, 6, 9
        )
    elif renderer_cache_mode == "native":
        typewriter_boot, typewriter_report = (
            typewriter.patch_renderer_without_glyph_cache(clean_boot, 6, 9)
        )
    elif renderer_cache_mode == "native_reveal":
        # Native atlas plus the CP932 complete-character reveal loop.  The
        # reveal hook was removed while it was suspected in the settings
        # description mixing; that symptom is now attributed to a PPSSPP dev
        # build regression, so the hook returns to fix mid-reveal half-character
        # artifacts in mixed-width Korean dialogue.
        typewriter_boot, typewriter_report = typewriter.patch_executable(
            clean_boot, 6, 9
        )
    else:
        raise ValueError(f"unsupported renderer cache mode: {renderer_cache_mode}")
    punctuation_boot = typewriter_boot
    punctuation_report = {
        "status": "disabled_with_native_reveal_loop",
        "reason": (
            "The broad reveal hook is disabled; compact 6/9-pixel advances are "
            "installed directly by renderer-only mode."
        ),
        "spacing": {
            "space_advance_px": 6,
            "double_byte_advance_px": 9,
            "ui_refresh_geometry_px": 9,
        },
    }

    boot_table = load_json(boot_artifact)
    ui_rows = slot_rows(boot_table)
    generated_boot = (boot_ui_dir / "BOOT.BIN").read_bytes()
    final_boot = merge_slots(punctuation_boot, generated_boot, ui_rows)
    if len(final_boot) > len(clean_eboot):
        raise ValueError("plaintext EBOOT candidate exceeds the original EBOOT slot")
    final_eboot = final_boot

    clean_system = (clean_root / "PSP_GAME/USRDIR/SYSTEM.DAT").read_bytes()
    clean_anime = (clean_root / "PSP_GAME/USRDIR/ANIME.DAT").read_bytes()
    clean_bg = (clean_root / "PSP_GAME/USRDIR/BG.DAT").read_bytes()
    system_entries = parse_nispack(clean_system)
    start_entry = next(
        (entry for entry in system_entries if entry["name"] == "start.lzs"), None
    )
    if start_entry is None:
        raise ValueError("SYSTEM.DAT has no start.lzs")
    clean_start_lzs = nispack_payload(clean_system, start_entry)
    clean_start, extension = decompress_nis_lzs.decompress(clean_start_lzs)
    if extension != "dat":
        raise ValueError(f"unexpected start.lzs extension: {extension}")
    _, start_entries = read_start_entries(clean_start)
    start_by_name = {entry.name: entry for entry in start_entries}
    required = {
        "Demo00.dat",
        "font.fnt",
        "font.txp",
        "StageInfo00.dat",
        "LuckyDoll.dat",
        "PictureBook.dat",
        "LuckyItem.dat",
        "Collection.dat",
        "Honor.dat",
        "MusicShop.dat",
        "ClearTime00.dat",
        "anime00.dat",
        "jis2ucs.bin",
        "ucs2jis.bin",
    }
    if not required <= set(start_by_name):
        raise ValueError(f"start.dat is missing: {sorted(required - set(start_by_name))}")

    def start_payload(name: str) -> bytes:
        entry = start_by_name[name]
        return clean_start[entry.data_start:entry.data_end]

    demo_report = load_json(demo_dir / "report.json")
    demo_output = validate_artifact(
        demo_dir / "Demo00.dat",
        demo_report["outputs"]["Demo00.dat"],
        "Demo00.dat",
    )
    if sha256(start_payload("Demo00.dat")) != str(
        demo_report["inputs"]["Demo00.dat_sha256"]
    ):
        raise ValueError("clean Demo00.dat does not match the supported revision")

    boot_ui_report = load_json(boot_ui_dir / "report.json")
    final_font_fnt = (boot_ui_dir / "font.fnt").read_bytes()
    final_font_txp = (boot_ui_dir / "font.txp").read_bytes()
    if sha256(final_font_fnt) != str(boot_ui_report["font"]["font_fnt_sha256"]):
        raise ValueError("BOOT UI font.fnt no longer matches its build report")
    if sha256(final_font_txp) != str(boot_ui_report["font"]["font_txp_sha256"]):
        raise ValueError("BOOT UI font.txp no longer matches its build report")

    mapping = load_json(boot_ui_dir / "hangul_mapping.json")
    character_map = mapping_from_rows(list(mapping["entries"]))
    final_jis2ucs, final_ucs2jis, unicode_table_report = patch_unicode_tables(
        start_payload("jis2ucs.bin"),
        start_payload("ucs2jis.bin"),
        list(mapping["entries"]),
    )
    stage_rows, probes = make_stage_rows(stage_csv, stage_mode)
    final_stage, patched_stage_rows = patch_stage_info(
        start_payload("StageInfo00.dat"), stage_rows, character_map
    )
    lucky_doll_rows = load_lucky_doll_rows(lucky_doll_csv)
    final_lucky_doll, patched_lucky_doll_rows = patch_lucky_doll(
        start_payload("LuckyDoll.dat"), lucky_doll_rows, character_map
    )
    picture_book_rows = load_picture_book_rows(picture_book_csv)
    final_picture_book, patched_picture_book_rows = patch_picture_book(
        start_payload("PictureBook.dat"), picture_book_rows, character_map
    )
    table_results: dict[str, tuple[bytes, list[dict[str, object]]]] = {}
    for member, csv_path in (
        ("LuckyItem.dat", lucky_item_csv),
        ("Collection.dat", collection_csv),
        ("Honor.dat", honor_csv),
        ("MusicShop.dat", music_shop_csv),
    ):
        table_rows = start_tables.load_rows(csv_path, member)
        table_results[member] = start_tables.patch(
            member, start_payload(member), table_rows, character_map
        )
    clear_time_table = load_json(clear_time_artifact)
    final_clear_time, patched_clear_time_rows = patch_clear_time(
        start_payload("ClearTime00.dat"), clear_time_table, character_map
    )

    mapped = translated_assets(translated_dir)
    quantization_reports: list[dict[str, object]] = []

    bg_entries = parse_nispack(clean_bg)
    bg_by_name = {str(entry["name"]): entry for entry in bg_entries}
    bg_replacements: dict[str, bytes] = {}
    for asset_id, png in mapped.items():
        if not asset_id.startswith("BG.DAT/"):
            continue
        name = asset_id.split("/", 1)[1]
        if name not in bg_by_name:
            raise ValueError(f"BG.DAT asset is missing: {asset_id}")
        bg_replacements[name] = patch_txp(
            asset_id,
            nispack_payload(clean_bg, bg_by_name[name]),
            png,
            quantization_reports,
        )
    final_bg = replace_nispack_fixed(clean_bg, bg_replacements)

    anime_entries = parse_nispack(clean_anime)
    anime_by_name = {str(entry["name"]): entry for entry in anime_entries}
    outer_groups: dict[str, list[tuple[str, int, int, Path]]] = defaultdict(list)
    for asset_id, png in mapped.items():
        if not asset_id.startswith("ANIME.DAT/"):
            continue
        entry_name, record_index, texture_index = parse_anime_asset(
            asset_id[len("ANIME.DAT/") :]
        )
        outer_groups[entry_name].append(
            (asset_id, record_index, texture_index, png)
        )
    anime_replacements: dict[str, bytes] = {}
    for entry_name, patches in outer_groups.items():
        if entry_name not in anime_by_name:
            raise ValueError(f"ANIME.DAT entry is missing: {entry_name}")
        anime_replacements[entry_name] = patch_anime_entry(
            nispack_payload(clean_anime, anime_by_name[entry_name]),
            patches,
            quantization_reports,
        )
    final_anime = replace_nispack_fixed(clean_anime, anime_replacements)

    start_replacements: dict[str, bytes] = {
        "Demo00.dat": demo_output,
        "font.fnt": final_font_fnt,
        "font.txp": final_font_txp,
        "StageInfo00.dat": final_stage,
        "LuckyDoll.dat": final_lucky_doll,
        "PictureBook.dat": final_picture_book,
        "LuckyItem.dat": table_results["LuckyItem.dat"][0],
        "Collection.dat": table_results["Collection.dat"][0],
        "Honor.dat": table_results["Honor.dat"][0],
        "MusicShop.dat": table_results["MusicShop.dat"][0],
        "ClearTime00.dat": final_clear_time,
        "jis2ucs.bin": final_jis2ucs,
        "ucs2jis.bin": final_ucs2jis,
    }
    for asset_id, png in mapped.items():
        if not asset_id.startswith("start.dat/") or asset_id.startswith(
            "start.dat/anime00.dat/"
        ):
            continue
        name = asset_id.split("/", 1)[1]
        if name not in start_by_name:
            raise ValueError(f"start.dat asset is missing: {asset_id}")
        start_replacements[name] = patch_txp(
            asset_id, start_payload(name), png, quantization_reports
        )

    nested: list[tuple[str, int, int, Path]] = []
    prefix = "start.dat/anime00.dat/"
    for asset_id, png in mapped.items():
        if not asset_id.startswith(prefix):
            continue
        _, record_index, texture_index = parse_anime_asset(
            "anime00.dat/" + asset_id[len(prefix) :]
        )
        nested.append((asset_id, record_index, texture_index, png))
    if nested:
        start_replacements["anime00.dat"] = patch_anime_entry(
            start_payload("anime00.dat"), nested, quantization_reports
        )

    final_start = replace_start_fixed(clean_start, start_replacements)
    final_start_lzs, lzs_stats = compress_nis_lzs.compress(
        final_start, extension="dat", flag=0xD5
    )
    restored, restored_extension = decompress_nis_lzs.decompress(final_start_lzs)
    if restored != final_start or restored_extension != "dat":
        raise ValueError("final start.lzs failed self-roundtrip")
    # Retail SYSTEM.DAT satisfies align(offset + size, 2048) == next offset for
    # every member.  A shorter start.lzs breaks that chain, and on real hardware
    # the save-data icon that follows it is then read from the wrong place, so
    # the firmware save dialog closes immediately.  Pad the stored payload back
    # to the original length; the LZS header carries its own compressed size, so
    # the trailing zeros are never decoded.
    original_start_lzs_size = len(clean_start_lzs)
    if len(final_start_lzs) > original_start_lzs_size:
        raise ValueError(
            "recompressed start.lzs is larger than the retail payload: "
            f"{len(final_start_lzs)} > {original_start_lzs_size}"
        )
    padded_start_lzs = final_start_lzs + bytes(
        original_start_lzs_size - len(final_start_lzs)
    )
    final_system = replace_nispack_in_place(
        clean_system, {"start.lzs": padded_start_lzs}
    )

    if len(quantization_reports) != len(mapped):
        encoded = {str(item["asset_id"]) for item in quantization_reports}
        raise ValueError(f"not every PNG was inserted: {sorted(set(mapped) - encoded)}")

    native = {
        "PSP_GAME/SYSDIR/BOOT.BIN": final_boot,
        "PSP_GAME/SYSDIR/EBOOT.BIN": final_eboot,
        "PSP_GAME/USRDIR/SYSTEM.DAT": final_system,
        "PSP_GAME/USRDIR/ANIME.DAT": final_anime,
        "PSP_GAME/USRDIR/BG.DAT": final_bg,
    }
    details: dict[str, object] = {
        "executables": {
            "typewriter": typewriter_report,
            "punctuation": punctuation_report,
            "boot_ui_slots": len(ui_rows),
            "plaintext_eboot": True,
        },
        "stage_info": {
            "mode": stage_mode,
            "csv": str(stage_csv),
            "csv_sha256": sha256_file(stage_csv),
            "patched_slots": len(patched_stage_rows),
            "output_sha256": sha256(final_stage),
            "probes": probes,
        },
        "lucky_doll": {
            "csv": str(lucky_doll_csv),
            "csv_sha256": sha256_file(lucky_doll_csv),
            "patched_records": len(patched_lucky_doll_rows),
            "output_sha256": sha256(final_lucky_doll),
            "records": patched_lucky_doll_rows,
        },
        "picture_book": {
            "csv": str(picture_book_csv),
            "csv_sha256": sha256_file(picture_book_csv),
            "patched_slots": len(patched_picture_book_rows),
            "output_sha256": sha256(final_picture_book),
        },
        "start_tables": {
            member: {
                "patched_slots": len(result[1]),
                "output_sha256": sha256(result[0]),
            }
            for member, result in table_results.items()
        },
        "clear_time": {
            "artifact": str(clear_time_artifact),
            "artifact_sha256": sha256_file(clear_time_artifact),
            "patched_records": len(patched_clear_time_rows),
            "output_sha256": sha256(final_clear_time),
            "records": patched_clear_time_rows,
        },
        "images": {
            "translated_pngs": len(mapped),
            "assets": sorted(mapped),
            "groups": {
                "BG.DAT": len(bg_replacements),
                "ANIME.DAT": sum(len(value) for value in outer_groups.values()),
                "start.dat_direct": sum(
                    asset.startswith("start.dat/")
                    and not asset.startswith("start.dat/anime00.dat/")
                    for asset in mapped
                ),
                "start.dat_anime00.dat": len(nested),
            },
            "minimum_exact_pixel_ratio": min(
                float(item["exact_pixel_ratio"]) for item in quantization_reports
            ),
            "maximum_mean_weighted_squared_error": max(
                float(item["mean_weighted_squared_error"])
                for item in quantization_reports
            ),
        },
        "unicode_tables": unicode_table_report,
        "start_lzs": {
            "source_size": len(clean_start_lzs),
            "output_size": len(final_start_lzs),
            "stored_size": len(padded_start_lzs),
            "zero_padding": len(padded_start_lzs) - len(final_start_lzs),
            "self_roundtrip": True,
            "tokens": lzs_stats,
        },
    }
    return native, details


def build(args: argparse.Namespace) -> dict[str, object]:
    clean_root = args.clean.resolve()
    output_root = args.output.resolve()
    report_path = args.report.resolve()
    verify_clean_tree(clean_root)
    if output_root == clean_root or clean_root in output_root.parents:
        raise ValueError("output must not be the clean extracted tree or one of its children")
    if output_root.exists():
        if not args.replace:
            raise FileExistsError(f"output already exists: {output_root}")
        shutil.rmtree(output_root)

    source_manifest = tree_manifest(clean_root)
    native, details = patch_native_files(
        clean_root,
        args.boot_artifact.resolve(),
        args.boot_ui_dir.resolve(),
        args.demo_dir.resolve(),
        args.stage_dir.resolve(),
        args.stage_csv.resolve(),
        args.lucky_doll_csv.resolve(),
        args.picture_book_csv.resolve(),
        args.lucky_item_csv.resolve(),
        args.collection_csv.resolve(),
        args.honor_csv.resolve(),
        args.music_shop_csv.resolve(),
        args.clear_time_artifact.resolve(),
        args.translated_dir.resolve(),
        args.stage_mode,
        args.renderer_cache_mode,
    )

    temporary = output_root.with_name(output_root.name + ".tmp")
    if temporary.exists():
        shutil.rmtree(temporary)
    try:
        shutil.copytree(clean_root, temporary)
        for relative, data in native.items():
            destination = temporary / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        output_manifest = tree_manifest(temporary)
        before = manifest_map(source_manifest)
        after = manifest_map(output_manifest)
        changed = sorted(
            path for path in before.keys() | after.keys() if before.get(path) != after.get(path)
        )
        if set(changed) != EXPECTED_CHANGED_FILES:
            raise ValueError(f"unexpected direct-run diff: {changed}")
        os.replace(temporary, output_root)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)

    report = {
        "schema_version": 1,
        "status": "PASS: clean extracted tree rebuilt for direct PPSSPP execution",
        "iso_created": False,
        "clean_root": str(clean_root),
        "output_root": str(output_root),
        "stage_mode": args.stage_mode,
        "renderer_cache_mode": args.renderer_cache_mode,
        "source_manifest": source_manifest,
        "output_manifest": output_manifest,
        "changed_files": changed,
        "details": details,
        "runtime_gate": {
            "status": "PENDING",
            "requirements": [
                "PPSSPP replacement textures OFF",
                "fresh boot without an old savestate for the first check",
                "user review of the handoff's first nine screens",
            ],
        },
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "output_root": str(output_root),
                "stage_mode": args.stage_mode,
                "changed_files": changed,
                "report": str(report_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean", type=Path, default=PROJECT_ROOT / "extracted")
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "work/builds/direct_run_latest",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_ROOT / "work/reports/direct_run_latest.json",
    )
    parser.add_argument(
        "--boot-artifact",
        type=Path,
        default=PROJECT_ROOT / "workspace/text/boot_ui_translation.json",
    )
    parser.add_argument(
        "--boot-ui-dir",
        type=Path,
        default=PROJECT_ROOT / "work/builds/direct_run_boot_ui_full_20260726",
    )
    parser.add_argument(
        "--demo-dir",
        type=Path,
        default=PROJECT_ROOT / "work/production/demo00",
    )
    parser.add_argument(
        "--stage-dir",
        type=Path,
        default=PROJECT_ROOT / "work/builds/integrated_20260726/stage_info",
    )
    parser.add_argument(
        "--stage-csv",
        type=Path,
        default=PROJECT_ROOT / "workspace/text/translation/stage_info.csv",
    )
    parser.add_argument(
        "--lucky-doll-csv",
        type=Path,
        default=PROJECT_ROOT / "workspace/text/translation/lucky_doll.csv",
    )
    parser.add_argument(
        "--picture-book-csv",
        type=Path,
        default=PROJECT_ROOT
        / "workspace/text/translation/picture_book_ko_translated.csv",
    )
    parser.add_argument(
        "--lucky-item-csv",
        type=Path,
        default=PROJECT_ROOT
        / "workspace/text/translation/lucky_item_ko_translated.csv",
    )
    parser.add_argument(
        "--collection-csv",
        type=Path,
        default=PROJECT_ROOT
        / "workspace/text/translation/collection_ko_translated.csv",
    )
    parser.add_argument(
        "--honor-csv",
        type=Path,
        default=PROJECT_ROOT / "workspace/text/translation/honor_ko_translated.csv",
    )
    parser.add_argument(
        "--music-shop-csv",
        type=Path,
        default=PROJECT_ROOT
        / "workspace/text/translation/music_shop_ko_translated.csv",
    )
    parser.add_argument(
        "--clear-time-artifact",
        type=Path,
        default=PROJECT_ROOT / "workspace/text/translation/clear_time.json",
    )
    parser.add_argument(
        "--translated-dir",
        type=Path,
        default=PROJECT_ROOT
        / "work/live/image_first_pass_review/gallery/assets/translated",
    )
    parser.add_argument("--stage-mode", choices=("full", "probe"), default="full")
    parser.add_argument(
        "--renderer-cache-mode",
        choices=("reuse", "native", "native_reveal"),
        default="reuse",
        help=(
            "use the production glyph cache, native-atlas diagnostic control, "
            "or native atlas plus the CP932 complete-character reveal loop"
        ),
    )
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    build(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
