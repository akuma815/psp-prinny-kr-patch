#!/usr/bin/env python3
"""Match PPSSPP quick hashes across Prinny TXP and ANIME indexed textures."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

import anime_assets
import decompress_nis_lzs
import inspect_nispack
import inspect_start_dat
import txp_assets
from match_ppsspp_quick_hash import stable_quick_tex_hash


def nispack_entries(data: bytes):
    if data[: len(inspect_nispack.SIGNATURE)] != inspect_nispack.SIGNATURE:
        raise ValueError("not NISPACK")
    count = struct.unpack_from("<I", data, len(inspect_nispack.SIGNATURE))[0]
    cursor = len(inspect_nispack.SIGNATURE) + 4
    for index in range(count):
        name_raw, offset, size, unknown = inspect_nispack.ENTRY.unpack_from(data, cursor)
        cursor += inspect_nispack.ENTRY.size
        name = name_raw.split(b"\0", 1)[0].decode("ascii")
        if offset + size > len(data):
            raise ValueError(f"entry outside NISPACK: {name}")
        yield index, name, data[offset : offset + size], unknown


def start_entries(data: bytes):
    if len(data) < inspect_start_dat.HEADER.size:
        raise ValueError("start.dat header truncated")
    count, data_marker = inspect_start_dat.HEADER.unpack_from(data)
    cursor = inspect_start_dat.HEADER.size
    previous_end = data_marker
    for index in range(count):
        name_raw, unknown_0, unknown_1, unknown_2, end_raw = inspect_start_dat.ENTRY.unpack_from(data, cursor)
        cursor += inspect_start_dat.ENTRY.size
        name = name_raw.split(b"\0", 1)[0].decode("ascii")
        end = len(data) if end_raw == 0 and index == count - 1 else end_raw
        if previous_end > end or end > len(data):
            raise ValueError(f"entry outside start.dat: {name}")
        yield index, name, data[previous_end:end], (unknown_0, unknown_1, unknown_2)
        previous_end = end


def scan_payload(owner: str, name: str, data: bytes, targets: set[int], rows: list[dict]):
    try:
        info = txp_assets.parse_txp(data)
    except ValueError:
        pass
    else:
        raw = data[info.pixel_offset : info.pixel_offset + info.pixel_bytes]
        value = stable_quick_tex_hash(raw)
        if value in targets:
            rows.append({
                "owner": owner,
                "entry": name,
                "kind": "TXP",
                "width": info.width,
                "height": info.height,
                "bpp": 4 if info.pixel_format == txp_assets.FORMAT_INDEX4 else 8,
                "swizzled": info.swizzled,
                "hash": f"{value:08x}",
            })

    try:
        records = anime_assets.parse_records(data)
    except ValueError:
        return
    for record in records:
        for texture_index, texture in enumerate(record.textures):
            start = record.offset + texture.offset
            raw = data[start : start + texture.size]
            value = stable_quick_tex_hash(raw)
            if value in targets:
                rows.append({
                    "owner": owner,
                    "entry": name,
                    "kind": "ANIME",
                    "record": record.index,
                    "texture": texture_index,
                    "width": texture.width,
                    "height": texture.height,
                    "bpp": texture.bits_per_pixel,
                    "swizzled": texture.swizzled,
                    "hash": f"{value:08x}",
                })


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("archive", nargs="+", type=Path)
    parser.add_argument("--hash", action="append", required=True)
    args = parser.parse_args()
    targets = {int(value, 16) for value in args.hash}
    rows: list[dict] = []
    entry_count = 0
    for archive in args.archive:
        outer = archive.read_bytes()
        for _, name, payload, _ in nispack_entries(outer):
            entry_count += 1
            owner = archive.name
            scan_payload(owner, name, payload, targets, rows)
            if name.lower().endswith(".lzs"):
                if len(payload) < decompress_nis_lzs.HEADER.size:
                    continue
                _, _, stored_size, _ = decompress_nis_lzs.HEADER.unpack_from(payload)
                unpacked, extension = decompress_nis_lzs.decompress(payload[: stored_size + 4])
                if extension.lower() == "dat":
                    for _, child_name, child, _ in start_entries(unpacked):
                        entry_count += 1
                        scan_payload(f"{archive.name}/{name}", child_name, child, targets, rows)

    report = {
        "status": "PASS: indexed texture hash scan completed",
        "archives": [str(path) for path in args.archive],
        "targets": [f"{value:08x}" for value in sorted(targets)],
        "entries_scanned": entry_count,
        "matches": rows,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
