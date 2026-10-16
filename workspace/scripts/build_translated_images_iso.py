#!/usr/bin/env python3
"""Insert reviewed translated PNGs into Prinny's native containers and ISO.

The input ISO is treated as the current production baseline, so dialogue,
font, executable, and previously integrated changes are preserved.  PNGs are
quantized to each source texture's existing indexed CLUT; texture dimensions,
descriptors, and pixel payload sizes stay unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

from PIL import Image

import anime_assets
import build_iso_production
import compress_nis_lzs
import decompress_nis_lzs
import inspect_start_dat
import txp_assets
from inspect_nispack import ENTRY as NIS_ENTRY
from inspect_nispack import SIGNATURE as NIS_SIGNATURE


PNG_NAME = re.compile(r"^\d+_(.+)\.png$", re.IGNORECASE)
ISO_TARGETS = ("SYSTEM.DAT", "ANIME.DAT", "BG.DAT")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def align(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def parse_nispack(data: bytes) -> list[dict[str, object]]:
    if not data.startswith(NIS_SIGNATURE):
        raise ValueError("not a NISPACK archive")
    count, = struct.unpack_from("<I", data, len(NIS_SIGNATURE))
    table_end = len(NIS_SIGNATURE) + 4 + count * NIS_ENTRY.size
    if table_end > len(data):
        raise ValueError("NISPACK table is truncated")
    entries: list[dict[str, object]] = []
    for index in range(count):
        record = len(NIS_SIGNATURE) + 4 + index * NIS_ENTRY.size
        name_raw, offset, size, unknown = NIS_ENTRY.unpack_from(data, record)
        name = name_raw.split(b"\0", 1)[0].decode("ascii")
        if not name or Path(name).name != name:
            raise ValueError(f"unsafe NISPACK entry name: {name!r}")
        if offset > len(data) or size > len(data) - offset:
            raise ValueError(f"NISPACK entry is outside archive: {name}")
        entries.append({
            "index": index,
            "name": name,
            "offset": offset,
            "size": size,
            "unknown": unknown,
            "record": record,
        })
    ordered = sorted(entries, key=lambda item: int(item["offset"]))
    for before, after in zip(ordered, ordered[1:]):
        if int(before["offset"]) + int(before["size"]) > int(after["offset"]):
            raise ValueError("overlapping NISPACK entries")
    return entries


def nispack_payload(data: bytes, entry: dict[str, object]) -> bytes:
    start = int(entry["offset"])
    return data[start:start + int(entry["size"])]


def replace_nispack_fixed(
    archive: bytes, replacements: dict[str, bytes]
) -> bytes:
    """Replace same-size NISPACK entries without touching its table."""
    entries = parse_nispack(archive)
    by_name = {str(item["name"]): item for item in entries}
    if not set(replacements) <= set(by_name):
        raise ValueError(f"missing NISPACK entries: {sorted(set(replacements) - set(by_name))}")
    output = bytearray(archive)
    for name, replacement in replacements.items():
        entry = by_name[name]
        if len(replacement) != int(entry["size"]):
            raise ValueError(f"fixed NISPACK payload size changed: {name}")
        start = int(entry["offset"])
        output[start:start + len(replacement)] = replacement
    parsed = parse_nispack(bytes(output))
    parsed_by_name = {str(item["name"]): item for item in parsed}
    for name, replacement in replacements.items():
        if nispack_payload(bytes(output), parsed_by_name[name]) != replacement:
            raise ValueError(f"NISPACK round-trip mismatch: {name}")
    return bytes(output)


def replace_nispack_in_place(
    archive: bytes, replacements: dict[str, bytes]
) -> bytes:
    """Replace NISPACK payloads without moving any entry.

    The retail archive stores every member on a 2048-byte UMD sector boundary.
    Repacking with tighter packing keeps PPSSPP happy but breaks the save-data
    icon read on real hardware, so each replacement must fit inside the slot it
    already occupies; the remainder of that slot is zero-filled and only the
    stored size changes.
    """
    entries = parse_nispack(archive)
    by_name = {str(item["name"]): item for item in entries}
    missing = set(replacements) - set(by_name)
    if missing:
        raise ValueError(f"missing NISPACK entries: {sorted(missing)}")

    ordered = sorted(entries, key=lambda item: int(item["offset"]))
    slot_end: dict[int, int] = {}
    for position, item in enumerate(ordered):
        index = int(item["index"])
        if position + 1 < len(ordered):
            slot_end[index] = int(ordered[position + 1]["offset"])
        else:
            slot_end[index] = len(archive)

    output = bytearray(archive)
    for name, payload in replacements.items():
        item = by_name[name]
        offset = int(item["offset"])
        limit = slot_end[int(item["index"])]
        if offset + len(payload) > limit:
            raise ValueError(
                f"{name} does not fit its original NISPACK slot: "
                f"{len(payload)} > {limit - offset}"
            )
        output[offset:limit] = payload + bytes(limit - offset - len(payload))
        struct.pack_into("<II", output, int(item["record"]) + 32, offset, len(payload))

    if len(output) != len(archive):
        raise ValueError("in-place NISPACK repack changed the archive size")
    check = {str(item["name"]): item for item in parse_nispack(bytes(output))}
    for item in entries:
        name = str(item["name"])
        expected = replacements.get(name, nispack_payload(archive, item))
        if nispack_payload(bytes(output), check[name]) != expected:
            raise ValueError(f"in-place NISPACK payload mismatch: {name}")
        if int(check[name]["offset"]) != int(item["offset"]):
            raise ValueError(f"in-place NISPACK entry moved: {name}")
    return bytes(output)


def replace_nispack_variable(
    archive: bytes, replacements: dict[str, bytes], alignment: int = 16
) -> bytes:
    """Repack NISPACK entries while preserving names, order, and unknown fields."""
    entries = parse_nispack(archive)
    by_name = {str(item["name"]): item for item in entries}
    if not set(replacements) <= set(by_name):
        raise ValueError(f"missing NISPACK entries: {sorted(set(replacements) - set(by_name))}")
    ordered = sorted(entries, key=lambda item: int(item["offset"]))
    header_end = min(int(item["offset"]) for item in ordered)
    header = bytearray(archive[:header_end])
    cursor = header_end
    chunks: list[bytes] = []
    locations: dict[int, tuple[int, int]] = {}
    for item in ordered:
        padded = align(cursor, alignment)
        if padded != cursor:
            chunks.append(bytes(padded - cursor))
            cursor = padded
        name = str(item["name"])
        payload = replacements.get(name, nispack_payload(archive, item))
        locations[int(item["index"])] = (cursor, len(payload))
        chunks.append(payload)
        cursor += len(payload)
    for item in entries:
        offset, size = locations[int(item["index"])]
        struct.pack_into("<II", header, int(item["record"]) + 32, offset, size)
    output = bytes(header) + b"".join(chunks)
    check = parse_nispack(output)
    check_by_name = {str(item["name"]): item for item in check}
    for item in entries:
        name = str(item["name"])
        expected = replacements.get(name, nispack_payload(archive, item))
        if nispack_payload(output, check_by_name[name]) != expected:
            raise ValueError(f"repacked NISPACK payload mismatch: {name}")
    return output


def read_start_entries(data: bytes) -> tuple[int, list[inspect_start_dat.Entry]]:
    """Use the verified parser through a temporary file-free equivalent."""
    if len(data) < inspect_start_dat.HEADER.size:
        raise ValueError("start.dat header is truncated")
    count, data_marker = inspect_start_dat.HEADER.unpack_from(data)
    table_end = inspect_start_dat.HEADER.size + count * inspect_start_dat.ENTRY.size
    if table_end > len(data):
        raise ValueError("start.dat table is truncated")
    entries: list[inspect_start_dat.Entry] = []
    for index in range(count):
        pos = inspect_start_dat.HEADER.size + index * inspect_start_dat.ENTRY.size
        name_raw, unknown_0, unknown_1, unknown_2, end_raw = \
            inspect_start_dat.ENTRY.unpack_from(data, pos)
        name = name_raw.split(b"\0", 1)[0].decode("ascii")
        end = len(data) if end_raw == 0 and index == count - 1 else end_raw
        start = data_marker if index == 0 else entries[-1].data_end
        if start < table_end or end < start or end > len(data):
            raise ValueError(f"invalid start.dat entry geometry: {name}")
        entries.append(inspect_start_dat.Entry(
            index, name, unknown_0, unknown_1, unknown_2, start, end, end - start
        ))
    return data_marker, entries


def replace_start_fixed(archive: bytes, replacements: dict[str, bytes]) -> bytes:
    _, entries = read_start_entries(archive)
    by_name = {item.name: item for item in entries}
    if not set(replacements) <= set(by_name):
        raise ValueError(f"missing start.dat entries: {sorted(set(replacements) - set(by_name))}")
    output = bytearray(archive)
    for name, replacement in replacements.items():
        entry = by_name[name]
        if len(replacement) != entry.span:
            raise ValueError(f"fixed start.dat payload size changed: {name}")
        output[entry.data_start:entry.data_end] = replacement
    _, checked = read_start_entries(bytes(output))
    checked_by_name = {item.name: item for item in checked}
    for name, replacement in replacements.items():
        item = checked_by_name[name]
        if bytes(output[item.data_start:item.data_end]) != replacement:
            raise ValueError(f"start.dat round-trip mismatch: {name}")
    return bytes(output)


def filename_to_asset_id(path: Path) -> str:
    match = PNG_NAME.match(path.name)
    if not match:
        raise ValueError(f"unexpected translated PNG name: {path.name}")
    tail = match.group(1)
    if tail.startswith("BG.DAT_"):
        return "BG.DAT/" + tail[len("BG.DAT_"):]
    if tail.startswith("start.dat_system"):
        return "start.dat/" + tail[len("start.dat_"):]
    if tail.startswith("ANIME.DAT_"):
        rest = tail[len("ANIME.DAT_"):]
        rest = rest.replace("_record-", "/record-", 1)
        rest = rest.replace("_texture-", "/texture-", 1)
        return "ANIME.DAT/" + rest
    if tail.startswith("start.dat_anime00.dat_"):
        rest = tail[len("start.dat_anime00.dat_"):]
        rest = rest.replace("_texture-", "/texture-", 1)
        return "start.dat/anime00.dat/" + rest
    if tail.startswith("start.dat_") and "_" not in tail[len("start.dat_"):]:
        # plain start.dat texture members such as number.txp or window3.txp
        return "start.dat/" + tail[len("start.dat_"):]
    raise ValueError(f"cannot map translated PNG name: {path.name}")


def palette_colors(txp: bytes) -> list[tuple[int, int, int, int]]:
    info = txp_assets.parse_txp(txp)
    usable = 16 if info.pixel_format == txp_assets.FORMAT_INDEX4 else 256
    return [
        tuple(txp[info.palette_offset + index * 4:info.palette_offset + (index + 1) * 4])
        for index in range(usable)
    ]


def color_distance(
    left: tuple[int, int, int, int], right: tuple[int, int, int, int]
) -> int:
    if left[3] == 0:
        return (left[3] - right[3]) ** 2 * 16
    return (
        (left[0] - right[0]) ** 2
        + (left[1] - right[1]) ** 2
        + (left[2] - right[2]) ** 2
        + (left[3] - right[3]) ** 2 * 4
    )


def quantize_png(
    png: Path, wrapped_txp: bytes
) -> tuple[Image.Image, dict[str, object]]:
    info = txp_assets.parse_txp(wrapped_txp)
    with Image.open(png) as source:
        rgba = source.convert("RGBA")
    if rgba.size != (info.width, info.height):
        raise ValueError(
            f"translated PNG dimensions differ from source: {png.name} "
            f"{rgba.size} != {(info.width, info.height)}"
        )
    palette = palette_colors(wrapped_txp)
    cache: dict[tuple[int, int, int, int], tuple[int, int]] = {}
    indices = bytearray()
    exact_pixels = 0
    squared_error = 0
    maximum_error = 0
    for color in rgba.getdata():
        if color not in cache:
            distances = [color_distance(color, candidate) for candidate in palette]
            index = min(range(len(distances)), key=distances.__getitem__)
            cache[color] = (index, distances[index])
        index, error = cache[color]
        indices.append(index)
        exact_pixels += int(error == 0)
        squared_error += error
        maximum_error = max(maximum_error, error)
    total = info.width * info.height
    return Image.frombytes("L", rgba.size, bytes(indices)), {
        "png": str(png),
        "width": info.width,
        "height": info.height,
        "pixel_format": f"0x{info.pixel_format:04X}",
        "palette_colors": len(palette),
        "unique_png_colors": len(cache),
        "exact_pixel_ratio": exact_pixels / total,
        "mean_weighted_squared_error": squared_error / total,
        "maximum_weighted_squared_error": maximum_error,
    }


def parse_anime_asset(asset_id: str) -> tuple[str, int, int]:
    match = re.fullmatch(
        r"(?:ANIME\.DAT/)?([^/]+\.dat)/record-(\d+)/texture-(\d+)", asset_id
    )
    if not match:
        raise ValueError(f"invalid ANIME asset id: {asset_id}")
    return match.group(1), int(match.group(2)), int(match.group(3))


def patch_anime_entry(
    source: bytes,
    patches: list[tuple[str, int, int, Path]],
    reports: list[dict[str, object]],
) -> bytes:
    output = source
    records = anime_assets.parse_records(source)
    for asset_id, record_index, texture_index, png in patches:
        if record_index >= len(records):
            raise ValueError(f"ANIME record out of range: {asset_id}")
        record = records[record_index]
        if texture_index >= len(record.textures):
            raise ValueError(f"ANIME texture out of range: {asset_id}")
        wrapped = anime_assets.texture_as_txp(output, record, texture_index)
        indices, report = quantize_png(png, wrapped)
        output = anime_assets.replace_texture_indices(
            output, record, texture_index, indices
        )
        decoded_indices = txp_assets.decode_indices(
            anime_assets.texture_as_txp(output, record, texture_index)
        )
        if decoded_indices.tobytes() != indices.tobytes():
            raise ValueError(f"ANIME texture round-trip mismatch: {asset_id}")
        report["asset_id"] = asset_id
        reports.append(report)
    if len(output) != len(source):
        raise ValueError("ANIME entry size changed")
    return output


def patch_txp(
    asset_id: str, source: bytes, png: Path, reports: list[dict[str, object]]
) -> bytes:
    indices, report = quantize_png(png, source)
    output = txp_assets.encode_indices(source, indices)
    if txp_assets.decode_indices(output).tobytes() != indices.tobytes():
        raise ValueError(f"TXP round-trip mismatch: {asset_id}")
    report["asset_id"] = asset_id
    reports.append(report)
    return output


def extract_iso_targets(iso: Path) -> dict[str, bytes]:
    parent = build_iso_production.locate_directory(iso, "/PSP_GAME/USRDIR")
    children = build_iso_production.positioned_children(iso, parent)
    by_name = {
        build_iso_production._normalized_name(item.record.name): item.record
        for item in children
    }
    result = {}
    for name in ISO_TARGETS:
        normalized = build_iso_production._normalized_name(name)
        if normalized not in by_name:
            raise ValueError(f"ISO target is missing: {name}")
        record = by_name[normalized]
        result[name] = build_iso_production.read_region(iso, record.offset, record.size)
    return result


def rebuild_iso(
    baseline: Path, replacements: dict[str, bytes], output: Path
) -> list[dict[str, object]]:
    parent = build_iso_production.locate_directory(baseline, "/PSP_GAME/USRDIR")
    children = build_iso_production.positioned_children(baseline, parent)
    by_name = {
        build_iso_production._normalized_name(item.record.name): item
        for item in children
    }
    selected = [
        by_name[build_iso_production._normalized_name(name)]
        for name in ISO_TARGETS
    ]
    selected.sort(key=lambda item: item.record.offset)
    if [build_iso_production._normalized_name(item.record.name) for item in selected] != [
        build_iso_production._normalized_name(name) for name in ISO_TARGETS
    ]:
        raise ValueError("ISO tail target order changed")
    cursor = selected[0].record.offset
    layouts = []
    for item in selected:
        cursor = align(cursor, build_iso_production.SECTOR_SIZE)
        payload = replacements[
            next(name for name in ISO_TARGETS if
                 build_iso_production._normalized_name(name)
                 == build_iso_production._normalized_name(item.record.name))
        ]
        layouts.append((item, cursor, payload))
        cursor += len(payload)
    if cursor > baseline.stat().st_size:
        raise ValueError("rebuilt ISO tail exceeds original image")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    try:
        shutil.copyfile(baseline, temporary)
        with temporary.open("r+b") as stream:
            region_start = selected[0].record.offset
            region_end = max(
                cursor,
                max(item.record.offset + item.record.size for item in selected),
            )
            stream.seek(region_start)
            remaining = region_end - region_start
            zeroes = bytes(1024 * 1024)
            while remaining:
                amount = min(remaining, len(zeroes))
                stream.write(zeroes[:amount])
                remaining -= amount
            for item, offset, payload in layouts:
                stream.seek(offset)
                stream.write(payload)
                build_iso_production.write_both_endian_u32(
                    stream, item.record_offset + 2,
                    offset // build_iso_production.SECTOR_SIZE,
                )
                build_iso_production.write_both_endian_u32(
                    stream, item.record_offset + 10, len(payload)
                )
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()

    if output.stat().st_size != baseline.stat().st_size:
        raise ValueError("ISO size changed")
    verified = extract_iso_targets(output)
    reports = []
    for name in ISO_TARGETS:
        if verified[name] != replacements[name]:
            raise ValueError(f"ISO round-trip payload mismatch: {name}")
        reports.append({
            "name": name,
            "size": len(replacements[name]),
            "sha256": sha256(replacements[name]),
        })
    return reports


def build(
    baseline_iso: Path,
    translated_dir: Path,
    output_iso: Path,
    work_dir: Path,
) -> dict[str, object]:
    pngs = sorted(translated_dir.glob("*.png"))
    if not pngs:
        raise ValueError("translated PNG directory is empty")
    mapped: dict[str, Path] = {}
    for png in pngs:
        asset_id = filename_to_asset_id(png)
        if asset_id in mapped:
            raise ValueError(f"duplicate translated asset: {asset_id}")
        mapped[asset_id] = png

    containers = extract_iso_targets(baseline_iso)
    system_entries = parse_nispack(containers["SYSTEM.DAT"])
    start_entry = next(
        (item for item in system_entries if item["name"] == "start.lzs"), None
    )
    if start_entry is None:
        raise ValueError("SYSTEM.DAT has no start.lzs")
    start_lzs = nispack_payload(containers["SYSTEM.DAT"], start_entry)
    start_dat, extension = decompress_nis_lzs.decompress(start_lzs)
    if extension != "dat":
        raise ValueError(f"unexpected start.lzs extension: {extension}")

    quantization_reports: list[dict[str, object]] = []

    # Patch BG.DAT TXP entries.
    bg_entries = parse_nispack(containers["BG.DAT"])
    bg_by_name = {str(item["name"]): item for item in bg_entries}
    bg_replacements: dict[str, bytes] = {}
    for asset_id, png in mapped.items():
        if not asset_id.startswith("BG.DAT/"):
            continue
        name = asset_id.split("/", 1)[1]
        if name not in bg_by_name:
            raise ValueError(f"BG.DAT asset is missing: {asset_id}")
        bg_replacements[name] = patch_txp(
            asset_id, nispack_payload(containers["BG.DAT"], bg_by_name[name]),
            png, quantization_reports,
        )
    patched_bg = replace_nispack_fixed(containers["BG.DAT"], bg_replacements)

    # Patch outer ANIME.DAT entries.
    anime_entries = parse_nispack(containers["ANIME.DAT"])
    anime_by_name = {str(item["name"]): item for item in anime_entries}
    outer_groups: dict[str, list[tuple[str, int, int, Path]]] = defaultdict(list)
    for asset_id, png in mapped.items():
        if not asset_id.startswith("ANIME.DAT/"):
            continue
        entry_name, record_index, texture_index = parse_anime_asset(
            asset_id[len("ANIME.DAT/"):]
        )
        outer_groups[entry_name].append(
            (asset_id, record_index, texture_index, png)
        )
    anime_replacements = {}
    for entry_name, patches in outer_groups.items():
        if entry_name not in anime_by_name:
            raise ValueError(f"ANIME.DAT entry is missing: {entry_name}")
        source = nispack_payload(containers["ANIME.DAT"], anime_by_name[entry_name])
        anime_replacements[entry_name] = patch_anime_entry(
            source, patches, quantization_reports
        )
    patched_anime = replace_nispack_fixed(
        containers["ANIME.DAT"], anime_replacements
    )

    # Patch direct TXP and nested anime00.dat inside start.dat.
    _, start_entries = read_start_entries(start_dat)
    start_by_name = {item.name: item for item in start_entries}
    start_replacements: dict[str, bytes] = {}
    for asset_id, png in mapped.items():
        if not asset_id.startswith("start.dat/") or \
                asset_id.startswith("start.dat/anime00.dat/"):
            continue
        name = asset_id.split("/", 1)[1]
        if name not in start_by_name:
            raise ValueError(f"start.dat asset is missing: {asset_id}")
        item = start_by_name[name]
        source = start_dat[item.data_start:item.data_end]
        start_replacements[name] = patch_txp(
            asset_id, source, png, quantization_reports
        )

    nested_groups: list[tuple[str, int, int, Path]] = []
    for asset_id, png in mapped.items():
        prefix = "start.dat/anime00.dat/"
        if not asset_id.startswith(prefix):
            continue
        _, record_index, texture_index = parse_anime_asset(
            "anime00.dat/" + asset_id[len(prefix):]
        )
        nested_groups.append((asset_id, record_index, texture_index, png))
    if nested_groups:
        item = start_by_name.get("anime00.dat")
        if item is None:
            raise ValueError("start.dat has no anime00.dat")
        source = start_dat[item.data_start:item.data_end]
        start_replacements["anime00.dat"] = patch_anime_entry(
            source, nested_groups, quantization_reports
        )
    patched_start = replace_start_fixed(start_dat, start_replacements)

    patched_lzs, lzs_stats = compress_nis_lzs.compress(
        patched_start, extension="dat", flag=0xD5
    )
    restored, restored_extension = decompress_nis_lzs.decompress(patched_lzs)
    if restored != patched_start or restored_extension != "dat":
        raise ValueError("patched start.lzs self-roundtrip failed")
    patched_system = replace_nispack_variable(
        containers["SYSTEM.DAT"], {"start.lzs": patched_lzs}
    )

    work_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "start.dat": patched_start,
        "start.lzs": patched_lzs,
        "SYSTEM.DAT": patched_system,
        "ANIME.DAT": patched_anime,
        "BG.DAT": patched_bg,
    }
    for name, data in outputs.items():
        (work_dir / name).write_bytes(data)

    iso_reports = rebuild_iso(
        baseline_iso,
        {
            "SYSTEM.DAT": patched_system,
            "ANIME.DAT": patched_anime,
            "BG.DAT": patched_bg,
        },
        output_iso,
    )

    if len(quantization_reports) != len(mapped):
        encoded = {str(item["asset_id"]) for item in quantization_reports}
        raise ValueError(f"not every PNG was inserted: {sorted(set(mapped) - encoded)}")

    report = {
        "schema_version": 1,
        "status": "PASS: all translated PNGs inserted into native containers and ISO",
        "baseline_iso": {
            "path": str(baseline_iso),
            "size": baseline_iso.stat().st_size,
            "sha256": sha256_file(baseline_iso),
        },
        "translated_pngs": {
            "directory": str(translated_dir),
            "count": len(mapped),
            "assets": sorted(mapped),
        },
        "groups": {
            "BG.DAT": len(bg_replacements),
            "ANIME.DAT": sum(len(value) for value in outer_groups.values()),
            "start.dat_direct": sum(
                asset.startswith("start.dat/")
                and not asset.startswith("start.dat/anime00.dat/")
                for asset in mapped
            ),
            "start.dat_anime00.dat": len(nested_groups),
        },
        "lzs": {
            "original_size": len(start_lzs),
            "replacement_size": len(patched_lzs),
            "size_delta": len(patched_lzs) - len(start_lzs),
            "self_roundtrip": True,
            "tokens": lzs_stats,
        },
        "containers": iso_reports,
        "quantization": {
            "all_dimensions_preserved": True,
            "all_index_payloads_roundtrip": True,
            "minimum_exact_pixel_ratio": min(
                float(item["exact_pixel_ratio"]) for item in quantization_reports
            ),
            "maximum_mean_weighted_squared_error": max(
                float(item["mean_weighted_squared_error"])
                for item in quantization_reports
            ),
            "entries": quantization_reports,
        },
        "output_iso": {
            "path": str(output_iso),
            "size": output_iso.stat().st_size,
            "sha256": sha256_file(output_iso),
            "same_size_as_baseline": output_iso.stat().st_size
            == baseline_iso.stat().st_size,
        },
        "runtime_gate": {
            "status": "PENDING",
            "reason": "PPSSPP in-game image rendering still requires user review",
        },
    }
    report_path = work_dir / "build_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    output_report = output_iso.with_suffix(output_iso.suffix + ".report.json")
    shutil.copy2(report_path, output_report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-iso", type=Path, required=True)
    parser.add_argument("--translated-dir", type=Path, required=True)
    parser.add_argument("--output-iso", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    args = parser.parse_args()
    report = build(
        args.baseline_iso.resolve(),
        args.translated_dir.resolve(),
        args.output_iso.resolve(),
        args.work_dir.resolve(),
    )
    print(json.dumps({
        "status": report["status"],
        "translated_png_count": report["translated_pngs"]["count"],
        "groups": report["groups"],
        "output_iso": report["output_iso"],
        "report": str((args.work_dir.resolve() / "build_report.json")),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
