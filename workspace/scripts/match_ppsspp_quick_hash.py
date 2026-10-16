#!/usr/bin/env python3
"""Match PPSSPP quick content hashes against raw GM3 indexed texture payloads."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

import gm3_assets
import inspect_nispack


INITIAL = (0xC00B, 0x9BD9, 0x4B73, 0xB651, 0x4D9B, 0x4309, 0x0083, 0x0001)


def stable_quick_tex_hash(data: bytes) -> int:
    """Portable form of PPSSPP QuickTexHash for aligned, 64-byte-sized data."""
    if len(data) % 64:
        check = 0
        words = struct.unpack(f"<{len(data) // 4}I", data[:len(data) // 4 * 4])
        for index in range(0, len(words) - 1, 2):
            check = (check + words[index]) & 0xFFFFFFFF
            check ^= words[index + 1]
        return check

    cursor16 = [0] * 8
    cursor2 = list(INITIAL)
    for offset in range(0, len(data), 64):
        a16 = struct.unpack_from("<8H", data, offset)
        b32 = struct.unpack_from("<4I", data, offset + 16)
        c32 = struct.unpack_from("<4I", data, offset + 32)
        d16 = struct.unpack_from("<8H", data, offset + 48)
        for index in range(8):
            cursor16[index] = (
                cursor16[index] + a16[index] * cursor2[index]
            ) & 0xFFFF
        cursor32 = [
            cursor16[index * 2] | (cursor16[index * 2 + 1] << 16)
            for index in range(4)
        ]
        for index in range(4):
            cursor32[index] = ((cursor32[index] ^ b32[index]) + c32[index]) & 0xFFFFFFFF
        cursor16 = [
            (cursor32[index // 2] >> (16 * (index % 2))) & 0xFFFF
            for index in range(8)
        ]
        for index in range(8):
            cursor16[index] ^= (d16[index] * cursor2[index]) & 0xFFFF
            cursor2[index] = (cursor2[index] + 0x2455) & 0xFFFF

    cursor32 = [
        cursor16[index * 2] | (cursor16[index * 2 + 1] << 16)
        for index in range(4)
    ]
    cursor2_32 = [
        cursor2[index * 2] | (cursor2[index * 2 + 1] << 16)
        for index in range(4)
    ]
    return sum(
        (cursor32[index] + cursor2_32[index]) & 0xFFFFFFFF
        for index in range(4)
    ) & 0xFFFFFFFF


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage_dat", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("hash", nargs="+", help="8-digit PPSSPP content hash")
    args = parser.parse_args()
    targets = {int(value, 16): value.lower() for value in args.hash}
    matches = {value: [] for value in targets.values()}
    observations = []

    with args.stage_dat.open("rb") as stream:
        for entry in inspect_nispack.read_entries(args.stage_dat):
            if not entry.name.lower().endswith(".gm3"):
                continue
            stream.seek(entry.offset)
            payload = stream.read(entry.size)
            parsed = gm3_assets.parse(payload)
            for texture in parsed.textures:
                raw = payload[texture.pixel_offset:texture.pixel_offset + texture.pixel_size]
                value = stable_quick_tex_hash(raw)
                row = {
                    "entry": entry.name,
                    "texture": texture.index,
                    "width": texture.width,
                    "height": texture.height,
                    "bpp": texture.bits_per_pixel,
                    "swizzled": texture.swizzled,
                    "hash": f"{value:08x}",
                }
                observations.append(row)
                if value in targets:
                    matches[targets[value]].append(row)

    report = {
        "status": "PASS: PPSSPP quick hashes computed for all GM3 pixel payloads",
        "source": str(args.stage_dat),
        "texture_count": len(observations),
        "targets": matches,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for target, rows in matches.items():
        print(f"{target}: {len(rows)} GM3 matches")
        for row in rows[:30]:
            print(f"  {row['entry']}/texture-{row['texture']} {row['width']}x{row['height']} {row['bpp']}bpp")
    print(f"report={args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
