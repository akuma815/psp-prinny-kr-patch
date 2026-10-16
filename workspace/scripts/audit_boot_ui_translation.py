#!/usr/bin/env python3
"""Validate fixed-slot BOOT.BIN UI translations without modifying the executable."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


TOKEN_RE = re.compile(r"%[-+ #0]*\d*(?:\.\d+)?[ds]")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded_size(text: str) -> int:
    size = 0
    for character in text:
        if "\uac00" <= character <= "\ud7a3":
            size += 2
        else:
            size += len(character.encode("cp932", errors="strict"))
    return size


def slot_size(source_size: int) -> int:
    return ((source_size + 1 + 3) // 4) * 4


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    root = args.project_root.resolve()
    artifact_path = args.artifact or root / "workspace" / "text" / "boot_ui_translation.json"
    report_path = args.report or root / "work" / "analysis" / "boot_ui_translation_report.json"
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    source_path = root / artifact["source"]["path"]
    source = source_path.read_bytes()

    errors: list[str] = []
    if len(source) != artifact["source"]["size"]:
        errors.append("source size mismatch")
    if sha256(source) != artifact["source"]["sha256"]:
        errors.append("source SHA-256 mismatch")

    rows: list[dict[str, object]] = []
    unique_hangul: set[str] = set()
    for entry in artifact["entries"]:
        offset = int(entry["offset"], 0)
        source_payload = entry["source"].encode("cp932")
        capacity = slot_size(len(source_payload))
        actual = source[offset:offset + len(source_payload)]
        if actual != source_payload:
            errors.append(f"{entry['offset']} source payload mismatch")
        if source[offset + len(source_payload)] != 0:
            errors.append(f"{entry['offset']} source is not NUL terminated")

        translated_size = encoded_size(entry["translation"])
        # Compare visible glyph units, not raw bytes.  Format tokens contain
        # one-byte ASCII in both source and translation and are expanded before
        # display, while ASCII spaces are preserved but do not consume a cache
        # cell or a patched typewriter reveal unit.
        source_reveal_units = sum(
            character != " " for character in entry["source"]
        )
        translated_reveal_units = sum(
            character != " " for character in entry["translation"]
        )
        fits = translated_size < capacity
        if not fits:
            errors.append(
                f"{entry['offset']} translation needs {translated_size + 1} bytes; slot is {capacity}"
            )
        within_source_payload = translated_size <= len(source_payload)
        if not within_source_payload:
            errors.append(
                f"{entry['offset']} translation payload is {translated_size} bytes; "
                f"source payload is only {len(source_payload)} bytes"
            )
        within_source_reveal_budget = (
            translated_reveal_units <= source_reveal_units
        )
        if not within_source_reveal_budget:
            errors.append(
                f"{entry['offset']} translation needs {translated_reveal_units} "
                f"progressive-reveal glyphs; source budget is {source_reveal_units}"
            )
        source_tokens = TOKEN_RE.findall(entry["source"])
        translation_tokens = TOKEN_RE.findall(entry["translation"])
        if source_tokens != translation_tokens:
            source_conversions = [token[-1] for token in source_tokens]
            translation_conversions = [token[-1] for token in translation_tokens]
            allowed_override = bool(entry.get("allow_format_override"))
            if not allowed_override or source_conversions != translation_conversions:
                errors.append(f"{entry['offset']} format-token mismatch")
        unique_hangul.update(c for c in entry["translation"] if "\uac00" <= c <= "\ud7a3")
        rows.append(
            {
                "offset": entry["offset"],
                "slot_size": capacity,
                "source_bytes": len(source_payload),
                "translation_bytes": translated_size,
                "source_reveal_units": source_reveal_units,
                "translation_reveal_units": translated_reveal_units,
                "remaining_bytes": capacity - translated_size - 1,
                "fits": fits,
                "within_source_payload": within_source_payload,
                "within_source_reveal_budget": within_source_reveal_budget,
            }
        )

    report = {
        "status": "PASS" if not errors else "FAIL",
        "artifact": str(artifact_path.relative_to(root)),
        "source": str(source_path.relative_to(root)),
        "entry_count": len(rows),
        "unique_hangul": len(unique_hangul),
        "errors": errors,
        "entries": rows,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
