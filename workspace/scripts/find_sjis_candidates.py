#!/usr/bin/env python3
"""Find Shift-JIS-looking byte runs for survey use only.

Hits are candidates, not proof that the game consumes the bytes as text.
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path


def is_lead(value: int) -> bool:
    return 0x81 <= value <= 0x9F or 0xE0 <= value <= 0xFC


def is_trail(value: int) -> bool:
    return 0x40 <= value <= 0x7E or 0x80 <= value <= 0xFC


def is_single(value: int) -> bool:
    return 0x20 <= value <= 0x7E or 0xA1 <= value <= 0xDF


def japanese_count(text: str) -> int:
    total = 0
    for character in text:
        codepoint = ord(character)
        if (
            0x3040 <= codepoint <= 0x30FF
            or 0x3400 <= codepoint <= 0x4DBF
            or 0x4E00 <= codepoint <= 0x9FFF
            or 0xFF61 <= codepoint <= 0xFF9F
            or "CJK" in unicodedata.name(character, "")
        ):
            total += 1
    return total


def candidates(data: bytes, minimum_japanese: int) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    position = 0
    while position < len(data):
        start = position
        cursor = position
        while cursor < len(data):
            value = data[cursor]
            if is_lead(value):
                if cursor + 1 >= len(data) or not is_trail(data[cursor + 1]):
                    break
                cursor += 2
            elif is_single(value):
                cursor += 1
            else:
                break

        if cursor > start:
            raw = data[start:cursor]
            try:
                text = raw.decode("shift_jis")
            except UnicodeDecodeError:
                text = ""
            count = japanese_count(text)
            if count >= minimum_japanese:
                results.append(
                    {
                        "offset": start,
                        "length": len(raw),
                        "japanese_characters": count,
                        "raw_hex": raw.hex().upper(),
                        "text": text,
                    }
                )
            position = max(cursor, start + 1)
        else:
            position += 1
    return results


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--minimum-japanese", type=int, default=4)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    found = candidates(args.input.read_bytes(), args.minimum_japanese)
    shown = found[: args.limit]
    if args.json:
        print(json.dumps(shown, ensure_ascii=False, indent=2))
    else:
        print(f"candidate runs: {len(found)} (showing {len(shown)})")
        for item in shown:
            print(
                f"0x{item['offset']:08X}  {item['length']:5d} bytes  "
                f"jp={item['japanese_characters']:3d}  {item['text']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
