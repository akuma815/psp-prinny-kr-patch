#!/usr/bin/env python3
"""Conservatively audit CP932 code and glyph allocation candidates.

Confirmed structured text and heuristic candidate strings are deliberately
reported as different evidence tiers.  This tool does not approve production
allocation by itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import audit_cp932_usage
import font_assets
import inspect_start_dat


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def strong_japanese_count(text: str) -> int:
    total = 0
    for character in text:
        value = ord(character)
        if (
            0x3040 <= value <= 0x30FF
            or 0x3400 <= value <= 0x4DBF
            or 0x4E00 <= value <= 0x9FFF
            or "CJK" in unicodedata.name(character, "")
        ):
            total += 1
    return total


def is_cp932_lead(value: int) -> bool:
    return 0x81 <= value <= 0x9F or 0xE0 <= value <= 0xFC


def is_cp932_trail(value: int) -> bool:
    return 0x40 <= value <= 0x7E or 0x80 <= value <= 0xFC


def is_cp932_single(value: int) -> bool:
    return 0x20 <= value <= 0x7E or 0xA1 <= value <= 0xDF


def candidate_runs(
    data: bytes,
    *,
    minimum_strong_japanese: int,
    minimum_strong_ratio: float,
    maximum_run_bytes: int,
    require_nul_boundaries: bool = False,
    exclude_utf8_japanese: bool = False,
) -> list[dict[str, object]]:
    """Return strict CP932-looking runs as survey candidates only."""
    results: list[dict[str, object]] = []
    position = 0
    while position < len(data):
        start = position
        cursor = position
        while cursor < len(data) and cursor - start < maximum_run_bytes:
            value = data[cursor]
            if is_cp932_lead(value):
                if cursor + 1 >= len(data) or not is_cp932_trail(data[cursor + 1]):
                    break
                pair = data[cursor:cursor + 2]
                try:
                    pair.decode("cp932", errors="strict")
                except UnicodeDecodeError:
                    break
                cursor += 2
            elif is_cp932_single(value):
                cursor += 1
            else:
                break

        if cursor > start:
            raw = data[start:cursor]
            try:
                text = raw.decode("cp932", errors="strict")
            except UnicodeDecodeError:
                text = ""
            strong = strong_japanese_count(text)
            visible = sum(not character.isspace() for character in text)
            ratio = strong / visible if visible else 0.0
            nul_bounded = (
                start > 0
                and data[start - 1] == 0
                and cursor < len(data)
                and data[cursor] == 0
            )
            utf8_japanese = False
            if exclude_utf8_japanese:
                try:
                    utf8_japanese = strong_japanese_count(raw.decode("utf-8")) >= 2
                except UnicodeDecodeError:
                    pass
            if (
                strong >= minimum_strong_japanese
                and ratio >= minimum_strong_ratio
                and all(character.isprintable() for character in text)
                and (not require_nul_boundaries or nul_bounded)
                and not utf8_japanese
            ):
                results.append(
                    {
                        "offset": start,
                        "length": len(raw),
                        "strong_japanese": strong,
                        "strong_ratio": ratio,
                        "raw": raw,
                        "text": text,
                    }
                )
            position = max(cursor, start + 1)
        else:
            position += 1
    return results


def engine_code_map(glyph_map: tuple[int, ...]) -> dict[bytes, int]:
    result: dict[bytes, int] = {}
    for value in range(0x20, 0x7F):
        code = bytes((value,))
        index = font_assets.dense_cp932_index(code)
        if index < len(glyph_map):
            result[code] = glyph_map[index]
    for lead in (*range(0x81, 0xA0), *range(0xE0, 0xFD)):
        for trail in (*range(0x40, 0x7F), *range(0x80, 0xFD)):
            code = bytes((lead, trail))
            index = font_assets.dense_cp932_index(code)
            if index < len(glyph_map):
                result[code] = glyph_map[index]
    return result


def units_from_raw(raw: bytes) -> list[bytes]:
    units: list[bytes] = []
    cursor = 0
    while cursor < len(raw):
        if is_cp932_lead(raw[cursor]):
            units.append(raw[cursor:cursor + 2])
            cursor += 2
        else:
            units.append(raw[cursor:cursor + 1])
            cursor += 1
    return units


def load_profile(path: Path) -> dict[str, object]:
    profile = json.loads(path.read_text(encoding="utf-8"))
    if profile.get("schema_version") != 1:
        raise ValueError("unsupported CP932 allocation profile schema")
    return profile


def verify_input(name: str, data: bytes, profile: dict[str, object]) -> None:
    expected = profile["inputs"][name]
    if len(data) != expected["size"]:
        raise ValueError(f"{name} size mismatch")
    actual = sha256(data)
    if actual != expected["sha256"]:
        raise ValueError(f"{name} SHA-256 mismatch: {actual}")


def audit(
    profile_path: Path,
    start_path: Path,
    boot_path: Path,
    assets_path: Path,
) -> dict[str, object]:
    profile = load_profile(profile_path)
    start = start_path.read_bytes()
    boot = boot_path.read_bytes()
    font_fnt = (assets_path / "font.fnt").read_bytes()
    verify_input("start.dat", start, profile)
    verify_input("BOOT.BIN", boot, profile)
    verify_input("font.fnt", font_fnt, profile)

    confirmed_report = audit_cp932_usage.audit(assets_path)
    confirmed_codes: set[bytes] = set()
    for name in ("Demo00.dat", "MusicShop.dat", "PrinnyName.dat"):
        # The existing strict audit is the owner of parsing; repeat only its
        # reversible text-to-unit collection for allocation set construction.
        if name == "Demo00.dat":
            import demo00
            parsed = demo00.parse((assets_path / name).read_bytes())
            texts = [value for record in parsed.records for value in (record.speaker, *record.lines)]
        elif name == "MusicShop.dat":
            import music_shop
            parsed = music_shop.parse((assets_path / name).read_bytes())
            texts = [value for record in parsed.records for value in (record.short_name.text, record.display_name.text)]
        else:
            texts = audit_cp932_usage.parse_prinny_names((assets_path / name).read_bytes())
        confirmed_codes.update(unit for text in texts for unit in audit_cp932_usage.cp932_units(text))

    marker, entries = inspect_start_dat.read_entries(start_path)
    entries_by_name = {entry.name: entry for entry in entries}
    configured = profile["candidate_start_entries"]
    missing = sorted(set(configured) - set(entries_by_name))
    if missing:
        raise ValueError(f"configured start.dat entries are missing: {missing}")

    scanner = profile["scanner"]
    source_data: dict[str, bytes] = {"BOOT.BIN": boot}
    for name in configured:
        entry = entries_by_name[name]
        source_data[f"start.dat/{name}"] = start[entry.data_start:entry.data_end]

    candidate_counter: Counter[bytes] = Counter()
    source_summaries: dict[str, object] = {}
    for source_name, data in source_data.items():
        source_scanner = profile["boot_scanner"] if source_name == "BOOT.BIN" else scanner
        runs = candidate_runs(
            data,
            minimum_strong_japanese=source_scanner["minimum_strong_japanese"],
            minimum_strong_ratio=source_scanner["minimum_strong_ratio"],
            maximum_run_bytes=source_scanner["maximum_run_bytes"],
            require_nul_boundaries=source_scanner.get("require_nul_boundaries", False),
            exclude_utf8_japanese=source_scanner.get("exclude_utf8_japanese", False),
        )
        counter = Counter(unit for run in runs for unit in units_from_raw(run["raw"]))
        candidate_counter.update(counter)
        source_summaries[source_name] = {
            "size": len(data),
            "sha256": sha256(data),
            "candidate_runs": len(runs),
            "candidate_characters": sum(len(run["text"]) for run in runs),
            "distinct_cp932_codes": len(counter),
            "examples": [
                {
                    "offset": f"0x{run['offset']:X}",
                    "text": run["text"],
                }
                for run in runs[:scanner["examples_per_source"]]
            ],
        }

    map_count, = struct.unpack_from("<H", font_fnt)
    glyph_map = struct.unpack_from(f"<{map_count}H", font_fnt, 2)
    engine_map = engine_code_map(glyph_map)
    mapped_codes = {code for code, glyph in engine_map.items() if glyph != 0}
    unmapped_codes = set(engine_map) - mapped_codes
    policy_reserved_codes = {bytes((value,)) for value in range(0x20, 0x7F)}
    reserved_codes = confirmed_codes | set(candidate_counter) | policy_reserved_codes
    mapped_candidate_codes = mapped_codes - reserved_codes

    codes_by_glyph: dict[int, set[bytes]] = defaultdict(set)
    for code, glyph in engine_map.items():
        if glyph:
            codes_by_glyph[glyph].add(code)
    reclaimable_glyphs = sorted(
        glyph for glyph, codes in codes_by_glyph.items() if codes.isdisjoint(reserved_codes)
    )

    newly_reserved = set(candidate_counter) - confirmed_codes
    proxy_codes = {
        character.encode("cp932")
        for character in "プリニうわちこくッ"
    }
    proxy_evidence = []
    for code in sorted(proxy_codes):
        proxy_evidence.append(
            {
                "cp932_hex": code.hex().upper(),
                "character": code.decode("cp932"),
                "confirmed": code in confirmed_codes,
                "candidate_occurrences": candidate_counter[code],
                "reserved": code in reserved_codes,
            }
        )

    return {
        "schema_version": 1,
        "status": "PARTIAL: conservative allocation candidates; production mapping not approved",
        "supported_revision": profile["supported_revision"],
        "inputs": {
            "profile": str(profile_path),
            "start.dat": {"size": len(start), "sha256": sha256(start), "data_marker": marker},
            "BOOT.BIN": {"size": len(boot), "sha256": sha256(boot)},
            "font.fnt": {"size": len(font_fnt), "sha256": sha256(font_fnt)},
        },
        "evidence_tiers": {
            "confirmed_structured": {
                "assets": ["Demo00.dat", "MusicShop.dat", "PrinnyName.dat"],
                "distinct_cp932_codes": len(confirmed_codes),
                "source_report": "work/analysis/cp932_usage.json",
            },
            "heuristic_reserved": {
                "policy": "strict CP932 printable runs with strong full-width Japanese thresholds; BOOT.BIN additionally requires NUL boundaries and excludes Japanese UTF-8 literals; candidates, not consumer proof",
                "new_distinct_cp932_codes": len(newly_reserved),
                "total_distinct_cp932_codes": len(candidate_counter),
                "sources": source_summaries,
            },
        },
        "allocation_budget": {
            "engine_code_slots_scanned": len(engine_map),
            "currently_mapped_nonblank_codes": len(mapped_codes),
            "currently_unmapped_or_blank_code_slots": len(unmapped_codes),
            "policy_reserved_single_byte_ascii_codes": len(policy_reserved_codes),
            "reserved_mapped_codes_union": len(mapped_codes & reserved_codes),
            "mapped_code_candidates_after_conservative_reservation": len(mapped_candidate_codes),
            "reclaimable_nonblank_glyph_candidates": len(reclaimable_glyphs),
            "fixed_size_new_glyph_candidate_upper_bound": min(
                len(unmapped_codes), len(reclaimable_glyphs)
            ),
            "candidate_glyph_id_examples": reclaimable_glyphs[:128],
        },
        "dialog_e2e_proxy_codes": proxy_evidence,
        "confirmed_report_summary": {
            "text_slots": confirmed_report["scope"]["total_text_slots"],
            "nonempty_text_slots": confirmed_report["scope"]["nonempty_text_slots"],
            "distinct_cp932_codes": confirmed_report["usage"]["distinct_cp932_codes"],
        },
        "decision": {
            "production_allocation_approved": False,
            "next_gate": "confirm remaining text consumers and compare the approved Korean corpus glyph demand with the conservative reclaimable glyph budget",
        },
        "limitations": [
            "Heuristic strings reserve codes conservatively but do not prove that each run is rendered text.",
            "DLC DDEM, save data, runtime-generated strings, graphics-baked text, and unconfirmed archive consumers remain outside the confirmed denominator.",
            "An unmapped engine code still requires one owned glyph slot and an explicit shared encoder/decoder/font mapping.",
            "A reclaimable glyph candidate is not safe until every code and non-text reference to that glyph is excluded.",
            "All renderer-supported single-byte ASCII codes are reserved by policy because runtime-generated UI can consume them even when they are absent from confirmed string tables.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    parser.add_argument("start_dat", type=Path)
    parser.add_argument("boot_bin", type=Path)
    parser.add_argument("assets", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit(args.profile, args.start_dat, args.boot_bin, args.assets)
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
