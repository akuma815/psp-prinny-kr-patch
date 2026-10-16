#!/usr/bin/env python3
"""List untranslated NUL-terminated Japanese UI strings in the BOOT data block."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_START = 0x0ED000
DEFAULT_END = 0x0F19A0


def is_japanese(character: str) -> bool:
    codepoint = ord(character)
    return (
        0x3040 <= codepoint <= 0x30FF
        or 0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xFF65 <= codepoint <= 0xFF9F
    )


def valid_text(text: str) -> bool:
    if not text or not any(is_japanese(character) for character in text):
        return False
    # U+3000 ideographic space is not "printable" to str.isprintable() but is a
    # legitimate CP932 text character; without it every string containing a
    # full-width space (e.g. tutorial panel titles) escapes this audit.
    return all(
        character in "\n\r\t　" or character.isprintable() for character in text
    )


def slot_size(payload_size: int) -> int:
    return ((payload_size + 1 + 3) // 4) * 4


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--boot",
        type=Path,
        default=PROJECT_ROOT / "extracted/PSP_GAME/SYSDIR/BOOT.BIN",
    )
    parser.add_argument(
        "--artifact",
        type=Path,
        default=PROJECT_ROOT / "workspace/text/boot_ui_translation.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "work/analysis/boot_ui_residual.json",
    )
    parser.add_argument("--start", type=lambda value: int(value, 0), default=DEFAULT_START)
    parser.add_argument("--end", type=lambda value: int(value, 0), default=DEFAULT_END)
    args = parser.parse_args()

    source = args.boot.read_bytes()
    artifact = json.loads(args.artifact.read_text(encoding="utf-8"))
    patched_offsets = {int(entry["offset"], 0) for entry in artifact["entries"]}
    rows: list[dict[str, object]] = []
    cursor = args.start
    while cursor < args.end:
        end = source.find(b"\0", cursor, args.end)
        if end < 0:
            break
        payload = source[cursor:end]
        try:
            text = payload.decode("cp932")
        except UnicodeDecodeError:
            cursor += 1
            continue
        if cursor not in patched_offsets and valid_text(text):
            rows.append(
                {
                    "offset": f"0x{cursor:06X}",
                    "source": text,
                    "payload_bytes": len(payload),
                    "slot_size": slot_size(len(payload)),
                }
            )
        cursor = end + 1

    report = {
        "schema_version": 1,
        "source": str(args.boot),
        "range": [f"0x{args.start:06X}", f"0x{args.end:06X}"],
        "patched_entries": len(patched_offsets),
        "residual_count": len(rows),
        "entries": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "residual_count": len(rows),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
