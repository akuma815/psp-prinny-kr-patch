#!/usr/bin/env python3
"""Validate and summarize the observed Demo00.dat display-control fields."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import demo00
import inspect_start_dat


SPEAKER_STYLE_RANGES = {
    200: (2, 4),
    201: (5, 6),
    202: (7, 8),
}


def analyze(demo_path: Path, start_path: Path) -> dict[str, object]:
    table = demo00.parse(demo_path.read_bytes())
    _, assets = inspect_start_dat.read_entries(start_path)
    asset_names = {entry.name for entry in assets}

    layouts = Counter(record.control_2 for record in table.records)
    reserved = Counter(record.unknown_3 for record in table.records)
    speaker_styles = Counter(record.speaker_control for record in table.records)
    line_counts = Counter(sum(bool(line) for line in record.lines) for record in table.records)
    style_lengths: dict[int, Counter[int]] = defaultdict(Counter)
    style_speakers: dict[int, set[str]] = defaultdict(set)
    style_errors: list[dict[str, object]] = []

    for record in table.records:
        length = len(record.speaker)
        style_lengths[record.speaker_control][length] += 1
        style_speakers[record.speaker_control].add(record.speaker)
        if record.speaker_control == 0:
            valid = length == 0
        else:
            bounds = SPEAKER_STYLE_RANGES.get(record.speaker_control)
            valid = bounds is not None and bounds[0] <= length <= bounds[1]
        if not valid:
            style_errors.append({
                "record_id": record.record_id,
                "style": record.speaker_control,
                "speaker": record.speaker,
                "character_length": length,
            })

    face_values = [record.value_4 for record in table.records]
    face_ids = sorted({abs(value) for value in face_values if value})
    missing_faces = [
        {"face_id": face_id, "asset": f"wf_{face_id:04d}.txp"}
        for face_id in face_ids
        if f"wf_{face_id:04d}.txp" not in asset_names
    ]

    return {
        "schema_version": 1,
        "inputs": {
            "demo00": demo_path.as_posix(),
            "start_dat": start_path.as_posix(),
        },
        "record_count": len(table.records),
        "layout_variant": {
            "consumer_range": [0, 17],
            "observed_counts": {str(key): layouts[key] for key in sorted(layouts)},
        },
        "reserved_3": {
            "observed_counts": {str(key): reserved[key] for key in sorted(reserved)},
            "all_zero": set(reserved) == {0},
        },
        "face_asset_signed": {
            "zero_count": sum(value == 0 for value in face_values),
            "positive_count": sum(value > 0 for value in face_values),
            "negative_count": sum(value < 0 for value in face_values),
            "unique_nonzero_asset_ids": len(face_ids),
            "matched_start_assets": len(face_ids) - len(missing_faces),
            "missing_start_assets": missing_faces,
            "asset_name_rule": "wf_{abs(value):04d}.txp",
            "sign_semantics": "unresolved; preserve exactly",
        },
        "speaker_box_style": {
            "observed_counts": {
                str(key): speaker_styles[key] for key in sorted(speaker_styles)
            },
            "character_length_counts": {
                str(style): {
                    str(length): counts[length] for length in sorted(counts)
                }
                for style, counts in sorted(style_lengths.items())
            },
            "unique_speaker_counts": {
                str(style): len(names) for style, names in sorted(style_speakers.items())
            },
            "observed_length_policy": {
                "0": "no speaker/nameplate",
                "200": "2-4 characters (short)",
                "201": "5-6 characters (medium)",
                "202": "7-8 characters (long)",
            },
            "validation_errors": style_errors,
        },
        "line_count_distribution": {
            str(key): line_counts[key] for key in sorted(line_counts)
        },
        "safe_edit_policy": {
            "preserve_fields": [
                "layout_variant",
                "reserved_3",
                "face_asset_signed",
                "speaker_box_style",
            ],
            "note": (
                "Do not recompute nameplate style for Korean text until rendered "
                "pixel widths and the Hangul encoding policy are verified."
            ),
        },
    }


def validate(report: dict[str, object]) -> None:
    if report["record_count"] != 1572:
        raise ValueError("unexpected Demo00 record count")
    if not report["reserved_3"]["all_zero"]:  # type: ignore[index]
        raise ValueError("Demo00 +0x03 is not uniformly zero")
    face = report["face_asset_signed"]  # type: ignore[assignment]
    if face["missing_start_assets"]:  # type: ignore[index]
        raise ValueError("some signed face IDs do not resolve to start.dat assets")
    speaker = report["speaker_box_style"]  # type: ignore[assignment]
    if speaker["validation_errors"]:  # type: ignore[index]
        raise ValueError("speaker box style does not match observed length tiers")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("demo00", type=Path)
    parser.add_argument("start_dat", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = analyze(args.demo00, args.start_dat)
    validate(report)
    rendered = json.dumps(report, ensure_ascii=True, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"OK: wrote {args.output}")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
