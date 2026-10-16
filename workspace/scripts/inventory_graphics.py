#!/usr/bin/env python3
"""Inventory and render Prinny TXP entries from BG.DAT and decompressed start.dat."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import inspect_nispack
import inspect_start_dat
import anime_assets
import txp_assets


def read_bg(path: Path) -> list[tuple[dict[str, object], bytes]]:
    rows = []
    with path.open("rb") as stream:
        for entry in inspect_nispack.read_entries(path):
            if not entry.name.lower().endswith(".txp"):
                continue
            stream.seek(entry.offset)
            data = stream.read(entry.size)
            record = txp_assets.inventory_record(
                "BG.DAT", entry.index, entry.name, entry.offset, data
            )
            rows.append((record, data))
    return rows


def read_start(path: Path) -> list[tuple[dict[str, object], bytes]]:
    rows = []
    _, entries = inspect_start_dat.read_entries(path)
    with path.open("rb") as stream:
        for entry in entries:
            if not entry.name.lower().endswith(".txp"):
                continue
            stream.seek(entry.data_start)
            data = stream.read(entry.span)
            record = txp_assets.inventory_record(
                "start.dat", entry.index, entry.name, entry.data_start, data
            )
            rows.append((record, data))
    return rows


def anime_rows_from_data(
    data: bytes, *, source: str, entry_name: str, archive_index: int, file_offset: int
) -> list[tuple[dict[str, object], object]]:
    rows = []
    for record in anime_assets.parse_records(data):
        for texture_index, texture in enumerate(record.textures):
            name = f"{Path(entry_name).stem}_r{record.index:02d}_t{texture_index:02d}"
            rows.append(({
                "asset_id": f"{source}/{entry_name}/record-{record.index}/texture-{texture_index}",
                "source": source,
                "archive_index": archive_index,
                "entry_name": entry_name,
                "record_index": record.index,
                "record_offset": file_offset + record.offset,
                "record_size": record.size,
                "texture_index": texture_index,
                "name": name,
                "offset": file_offset + record.offset + texture.offset,
                "size": texture.size,
                "width": texture.width,
                "height": texture.height,
                "bits_per_pixel": texture.bits_per_pixel,
                "swizzled": texture.swizzled,
                "palette_count": len(record.palettes),
                "state": "not_reviewed",
            }, (data, record, texture_index)))
    return rows


def read_anime(path: Path) -> list[tuple[dict[str, object], object]]:
    rows = []
    with path.open("rb") as stream:
        for entry in inspect_nispack.read_entries(path):
            stream.seek(entry.offset)
            data = stream.read(entry.size)
            rows.extend(anime_rows_from_data(
                data, source="ANIME.DAT", entry_name=entry.name,
                archive_index=entry.index, file_offset=entry.offset,
            ))
    return rows


def read_start_anime(path: Path) -> list[tuple[dict[str, object], object]]:
    _, entries = inspect_start_dat.read_entries(path)
    entry = next((item for item in entries if item.name == "anime00.dat"), None)
    if entry is None:
        raise ValueError("start.dat has no anime00.dat entry")
    with path.open("rb") as stream:
        stream.seek(entry.data_start)
        data = stream.read(entry.span)
    return anime_rows_from_data(
        data, source="start.dat", entry_name=entry.name,
        archive_index=entry.index, file_offset=entry.data_start,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bg", required=True, type=Path)
    parser.add_argument("--start", required=True, type=Path)
    parser.add_argument("--anime", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    groups = {"bg": read_bg(args.bg), "start": read_start(args.start)}
    anime_rows = read_anime(args.anime)
    start_anime_rows = read_start_anime(args.start)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for group, rows in groups.items():
        png_dir = args.output_dir / group
        png_dir.mkdir(parents=True, exist_ok=True)
        sheet_assets = []
        for record, data in rows:
            name = str(record["name"])
            image_path = png_dir / f"{Path(name).stem}.png"
            txp_assets.decode_txp(data).save(image_path)
            record["preview"] = image_path.relative_to(args.output_dir).as_posix()
            records.append(record)
            if name != "font.txp":
                sheet_assets.append((name, data))
        txp_assets.make_contact_sheet(
            sheet_assets,
            args.output_dir / f"{group}_contact_sheet.png",
            thumb_width=256,
            columns=4,
        )

    anime_dir = args.output_dir / "anime"
    anime_dir.mkdir(parents=True, exist_ok=True)
    anime_sheet = []
    anime_sheets_by_entry = defaultdict(list)
    for record, payload in anime_rows:
        data, anime_record, texture_index = payload
        image = anime_assets.decode_texture(data, anime_record, texture_index)
        image_path = anime_dir / f"{record['name']}.png"
        image.save(image_path)
        record["preview"] = image_path.relative_to(args.output_dir).as_posix()
        records.append(record)
        # Contact sheets accept TXP data, so build a small equivalent TXP blob.
        texture = anime_record.textures[texture_index]
        required = 16 if texture.bits_per_pixel == 4 else 256
        palette = anime_assets.palette_for_texture(anime_record, texture_index, required)
        base = anime_record.offset
        palette_raw = data[base + palette.offset:base + palette.offset + required * 4]
        pixel_raw = data[base + texture.offset:base + texture.offset + texture.size]
        pixel_format = txp_assets.FORMAT_INDEX4 if texture.bits_per_pixel == 4 else txp_assets.FORMAT_INDEX8
        header = txp_assets.HEADER.pack(
            texture.width, texture.height, pixel_format, 0, required, 1,
            texture.swizzled, 1,
        )
        sheet_item = (str(record["name"]), header + palette_raw + pixel_raw)
        anime_sheet.append(sheet_item)
        anime_sheets_by_entry[str(record["entry_name"])].append(sheet_item)
    txp_assets.make_contact_sheet(
        anime_sheet, args.output_dir / "anime_contact_sheet.png", thumb_width=192, columns=5
    )
    sheets_dir = args.output_dir / "anime_sheets"
    for entry_name, sheet_items in anime_sheets_by_entry.items():
        txp_assets.make_contact_sheet(
            sheet_items,
            sheets_dir / f"{Path(entry_name).stem}.png",
            thumb_width=320,
            columns=4,
        )

    start_anime_dir = args.output_dir / "start_anime"
    start_anime_dir.mkdir(parents=True, exist_ok=True)
    start_anime_sheet = []
    for record, payload in start_anime_rows:
        data, anime_record, texture_index = payload
        image = anime_assets.decode_texture(data, anime_record, texture_index)
        image_path = start_anime_dir / f"{record['name']}.png"
        image.save(image_path)
        record["preview"] = image_path.relative_to(args.output_dir).as_posix()
        records.append(record)
        texture = anime_record.textures[texture_index]
        required = 16 if texture.bits_per_pixel == 4 else 256
        palette = anime_assets.palette_for_texture(anime_record, texture_index, required)
        base = anime_record.offset
        palette_raw = data[base + palette.offset:base + palette.offset + required * 4]
        pixel_raw = data[base + texture.offset:base + texture.offset + texture.size]
        pixel_format = txp_assets.FORMAT_INDEX4 if texture.bits_per_pixel == 4 else txp_assets.FORMAT_INDEX8
        header = txp_assets.HEADER.pack(
            texture.width, texture.height, pixel_format, 0, required, 1,
            texture.swizzled, 1,
        )
        start_anime_sheet.append((str(record["name"]), header + palette_raw + pixel_raw))
    txp_assets.make_contact_sheet(
        start_anime_sheet,
        args.output_dir / "start_anime_contact_sheet.png",
        thumb_width=256,
        columns=4,
    )

    report = {
        "schema_version": 1,
        "scope": {
            "BG.DAT": str(args.bg),
            "start.dat": str(args.start),
            "ANIME.DAT": str(args.anime),
        },
        "counts": {
            **{key: len(value) for key, value in groups.items()},
            "anime": len(anime_rows),
            "start_anime": len(start_anime_rows),
        },
        "total": len(records),
        "entries": records,
    }
    report_path = args.output_dir / "txp_inventory.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"OK: rendered {len(records)} graphics assets "
        f"({len(groups['bg'])} BG TXP, {len(groups['start'])} start TXP, "
        f"{len(anime_rows)} ANIME textures, {len(start_anime_rows)} start ANIME textures)"
    )
    print(f"OK: wrote {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
