#!/usr/bin/env python3
"""Embed the world sign, tutorial sign, and timer HUD textures in a direct-run tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
from pathlib import Path

from PIL import Image

import anime_assets
import compress_nis_lzs
import decompress_nis_lzs
import inspect_nispack
import inspect_start_dat
import txp_assets
from match_ppsspp_quick_hash import stable_quick_tex_hash


TUTORIAL_BOUNDS = ((211, 179, 256, 210),)
TIMER_BOUNDS = ((3, 68, 253, 89), (70, 95, 193, 116), (3, 125, 114, 146))
TUTORIAL_BANKS = {
    "2d08ded3": 1,
    "46fe2552": 5,
    "5976a553": 4,
    "742b67e5": 0,
    "a43c0364": 2,
}
TIMER_BANKS = {
    "564378d0": 0,
    "862c2386": 3,
    "982610db": 1,
    "a8d5f299": 2,
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def nispack_payload(path: Path, name: str) -> tuple[bytes, inspect_nispack.Entry]:
    data = path.read_bytes()
    entry = next((item for item in inspect_nispack.read_entries(path) if item.name == name), None)
    if entry is None:
        raise ValueError(f"NISPACK entry missing: {path} / {name}")
    return data[entry.offset : entry.offset + entry.size], entry


def replace_nispack_payload(path: Path, entry: inspect_nispack.Entry, payload: bytes) -> bytes:
    if len(payload) != entry.size:
        raise ValueError(f"NISPACK fixed-size replacement mismatch: {len(payload)} != {entry.size}")
    data = bytearray(path.read_bytes())
    data[entry.offset : entry.offset + entry.size] = payload
    return bytes(data)


def start_entries(data: bytes):
    count, marker = inspect_start_dat.HEADER.unpack_from(data)
    cursor = inspect_start_dat.HEADER.size
    previous = marker
    for index in range(count):
        name_raw, unknown_0, unknown_1, unknown_2, end_raw = inspect_start_dat.ENTRY.unpack_from(data, cursor)
        cursor += inspect_start_dat.ENTRY.size
        name = name_raw.split(b"\0", 1)[0].decode("ascii")
        end = len(data) if end_raw == 0 and index == count - 1 else end_raw
        yield index, name, previous, end, (unknown_0, unknown_1, unknown_2)
        previous = end


def in_bounds(x: int, y: int, bounds: tuple[tuple[int, int, int, int], ...]) -> bool:
    return any(x0 <= x < x1 and y0 <= y < y1 for x0, y0, x1, y1 in bounds)


def palette_banks(data: bytes, record: anime_assets.Record) -> list[list[tuple[int, int, int, int]]]:
    palette = record.palettes[0]
    if palette.color_count % 16:
        raise ValueError("CLUT4 palette count is not a multiple of 16")
    raw = data[
        record.offset + palette.offset :
        record.offset + palette.offset + palette.color_count * 4
    ]
    return [
        [tuple(raw[pos : pos + 4]) for pos in range(start, start + 64, 4)]
        for start in range(0, len(raw), 64)
    ]


def clut_key(path: Path) -> str:
    stem = path.stem
    if len(stem) < 16:
        raise ValueError(f"unexpected replacement filename: {path.name}")
    return stem[8:16].lower()


def build_indices(
    data: bytes,
    record_index: int,
    texture_index: int,
    replacement_paths: list[Path],
    bank_map: dict[str, int],
    bounds: tuple[tuple[int, int, int, int], ...],
) -> tuple[Image.Image, dict[str, object]]:
    record = anime_assets.parse_records(data)[record_index]
    texture = record.textures[texture_index]
    if (texture.width, texture.height, texture.bits_per_pixel) != (256, 256, 4):
        raise ValueError("expected a 256x256 CLUT4 texture")
    wrapped = anime_assets.texture_as_txp(data, record, texture_index)
    original = txp_assets.decode_indices(wrapped)
    original_bytes = original.tobytes()
    banks = palette_banks(data, record)

    variants = []
    seen_banks = set()
    for path in replacement_paths:
        key = clut_key(path)
        if key not in bank_map:
            raise ValueError(f"unmapped CLUT variant: {path.name}")
        bank = bank_map[key]
        if bank >= len(banks) or bank in seen_banks:
            raise ValueError(f"invalid or duplicate bank mapping: {path.name} -> {bank}")
        image = Image.open(path).convert("RGBA")
        if image.size != (texture.width, texture.height):
            raise ValueError(f"replacement size mismatch: {path}")
        variants.append((path, bank, image.tobytes()))
        seen_banks.add(bank)

    output = bytearray(original_bytes)
    changed_inside = 0
    changed_outside = 0
    for pixel in range(texture.width * texture.height):
        x = pixel % texture.width
        y = pixel // texture.width
        if not in_bounds(x, y, bounds):
            continue
        best_index = 0
        best_error = None
        for index in range(16):
            error = 0
            for _, bank, rgba in variants:
                target = rgba[pixel * 4 : pixel * 4 + 4]
                color = banks[bank][index]
                error += sum((target[channel] - color[channel]) ** 2 for channel in range(4))
            if best_error is None or error < best_error:
                best_error = error
                best_index = index
        if output[pixel] != best_index:
            output[pixel] = best_index
            changed_inside += 1

    for pixel, (before, after) in enumerate(zip(original_bytes, output, strict=True)):
        if before == after:
            continue
        x = pixel % texture.width
        y = pixel // texture.width
        if not in_bounds(x, y, bounds):
            changed_outside += 1
    if changed_outside:
        raise RuntimeError(f"indices changed outside protected bounds: {changed_outside}")

    image = Image.frombytes("L", (texture.width, texture.height), bytes(output))
    return image, {
        "record": record_index,
        "texture": texture_index,
        "bounds": [list(item) for item in bounds],
        "replacement_files": [path.name for path, _, _ in variants],
        "bank_mapping": {path.name: bank for path, bank, _ in variants},
        "changed_indices_inside": changed_inside,
        "changed_indices_outside": changed_outside,
        "source_content_hash": f"{stable_quick_tex_hash(wrapped[txp_assets.parse_txp(wrapped).pixel_offset:]):08x}",
    }


def render_banks(data: bytes, record_index: int, texture_index: int, output_dir: Path, prefix: str) -> list[str]:
    record = anime_assets.parse_records(data)[record_index]
    texture = record.textures[texture_index]
    pixel_start = record.offset + texture.offset
    pixels = data[pixel_start : pixel_start + texture.size]
    banks = palette_banks(data, record)
    paths = []
    for bank, colors in enumerate(banks):
        palette = b"".join(bytes(color) for color in colors)
        header = txp_assets.HEADER.pack(256, 256, txp_assets.FORMAT_INDEX4, 0, 16, 1, texture.swizzled, 1)
        destination = output_dir / f"{prefix}_bank-{bank}.png"
        destination.parent.mkdir(parents=True, exist_ok=True)
        txp_assets.decode_txp(header + palette + pixels).save(destination)
        paths.append(str(destination))
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-direct-run", type=Path, required=True)
    parser.add_argument("--world-stage", type=Path, required=True)
    parser.add_argument("--texture-dir", type=Path, required=True)
    parser.add_argument("--output-direct-run", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    if args.output_direct_run.exists():
        raise FileExistsError(f"output already exists: {args.output_direct_run}")
    shutil.copytree(args.base_direct_run, args.output_direct_run)
    usrdir = args.output_direct_run / "PSP_GAME" / "USRDIR"
    preview_dir = args.report.parent / "decoded_previews"

    # Timer: ANIME.DAT / anime95.dat / record 3 / texture 0.
    anime_path = usrdir / "ANIME.DAT"
    anime95, anime95_entry = nispack_payload(anime_path, "anime95.dat")
    timer_paths = sorted(args.texture_dir.glob("09596a50*b5a34886.png"))
    if len(timer_paths) != 4:
        raise ValueError(f"expected 4 timer variants, got {len(timer_paths)}")
    timer_indices, timer_report = build_indices(
        anime95, 3, 0, timer_paths, TIMER_BANKS, TIMER_BOUNDS
    )
    timer_record = anime_assets.parse_records(anime95)[3]
    patched_anime95 = anime_assets.replace_texture_indices(anime95, timer_record, 0, timer_indices)
    anime_path.write_bytes(replace_nispack_payload(anime_path, anime95_entry, patched_anime95))
    timer_record_after = anime_assets.parse_records(patched_anime95)[3]
    timer_raw_after = patched_anime95[
        timer_record_after.offset + timer_record_after.textures[0].offset :
        timer_record_after.offset + timer_record_after.textures[0].offset + timer_record_after.textures[0].size
    ]
    timer_report["output_content_hash"] = f"{stable_quick_tex_hash(timer_raw_after):08x}"
    timer_report["decoded_previews"] = render_banks(patched_anime95, 3, 0, preview_dir, "timer")

    # Tutorial sign: SYSTEM.DAT / start.lzs / anime00.dat / record 17 / texture 0.
    system_path = usrdir / "SYSTEM.DAT"
    start_slot, start_entry = nispack_payload(system_path, "start.lzs")
    _, _, stored_size, _ = decompress_nis_lzs.HEADER.unpack_from(start_slot)
    logical_start_lzs = start_slot[: stored_size + 4]
    start_dat, extension = decompress_nis_lzs.decompress(logical_start_lzs)
    if extension.lower() != "dat":
        raise ValueError(f"unexpected start.lzs extension: {extension}")
    anime00_item = next(item for item in start_entries(start_dat) if item[1] == "anime00.dat")
    _, _, anime00_start, anime00_end, _ = anime00_item
    anime00 = start_dat[anime00_start:anime00_end]
    tutorial_paths = sorted(args.texture_dir.glob("08de41e0*b6e0db29.png"))
    if len(tutorial_paths) != 5:
        raise ValueError(f"expected 5 tutorial variants, got {len(tutorial_paths)}")
    tutorial_indices, tutorial_report = build_indices(
        anime00, 17, 0, tutorial_paths, TUTORIAL_BANKS, TUTORIAL_BOUNDS
    )
    tutorial_record = anime_assets.parse_records(anime00)[17]
    patched_anime00 = anime_assets.replace_texture_indices(anime00, tutorial_record, 0, tutorial_indices)
    patched_start = bytearray(start_dat)
    patched_start[anime00_start:anime00_end] = patched_anime00
    packed_start, compression_stats = compress_nis_lzs.compress(bytes(patched_start), extension="dat", flag=0xD5)
    restored, restored_extension = decompress_nis_lzs.decompress(packed_start)
    if restored != bytes(patched_start) or restored_extension.lower() != "dat":
        raise RuntimeError("patched start.lzs roundtrip failed")
    if len(packed_start) > len(start_slot):
        raise ValueError(f"patched start.lzs no longer fits: {len(packed_start)} > {len(start_slot)}")
    padded_start = packed_start + bytes(len(start_slot) - len(packed_start))
    system_path.write_bytes(replace_nispack_payload(system_path, start_entry, padded_start))
    tutorial_record_after = anime_assets.parse_records(patched_anime00)[17]
    tutorial_raw_after = patched_anime00[
        tutorial_record_after.offset + tutorial_record_after.textures[0].offset :
        tutorial_record_after.offset + tutorial_record_after.textures[0].offset + tutorial_record_after.textures[0].size
    ]
    tutorial_report["output_content_hash"] = f"{stable_quick_tex_hash(tutorial_raw_after):08x}"
    tutorial_report["decoded_previews"] = render_banks(patched_anime00, 17, 0, preview_dir, "tutorial")
    tutorial_report["start_lzs"] = {
        "source_logical_size": len(logical_start_lzs),
        "output_logical_size": len(packed_start),
        "slot_size": len(start_slot),
        "padding": len(start_slot) - len(packed_start),
        "compression": compression_stats,
    }

    # World sign: previously verified GM3 PoC STAGE.DAT.
    stage_path = usrdir / "STAGE.DAT"
    if stage_path.stat().st_size != args.world_stage.stat().st_size:
        raise ValueError("world-sign STAGE.DAT size differs from the base")
    shutil.copy2(args.world_stage, stage_path)

    changed_files = []
    for name in ("ANIME.DAT", "SYSTEM.DAT", "STAGE.DAT"):
        before = args.base_direct_run / "PSP_GAME" / "USRDIR" / name
        after = usrdir / name
        changed_files.append({
            "path": f"PSP_GAME/USRDIR/{name}",
            "source_sha256": sha256_file(before),
            "output_sha256": sha256_file(after),
            "size": after.stat().st_size,
        })

    report = {
        "status": "PASS: three native stage HUD assets embedded in the direct-run tree",
        "base_direct_run": str(args.base_direct_run),
        "output_direct_run": str(args.output_direct_run),
        "tutorial": tutorial_report,
        "timer": timer_report,
        "world_stage": {
            "source": str(args.world_stage),
            "sha256": sha256_file(args.world_stage),
        },
        "changed_files": changed_files,
        "runtime_verification": "PENDING: PPSSPP texture replacement OFF",
        "physical_psp_verification": "PENDING",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
