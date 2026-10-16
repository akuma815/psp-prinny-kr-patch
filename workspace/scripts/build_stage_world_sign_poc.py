#!/usr/bin/env python3
"""Bake the translated world-direction sign into every owning GM3 in STAGE.DAT."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

import gm3_assets
import inspect_nispack
from match_ppsspp_quick_hash import stable_quick_tex_hash


EXPECTED_STAGE_SHA256 = "09e373171069b3ff9402eef0fd4b86e1d21a3c1ea6597265038a305c8935f717"
EXPECTED_REFERENCE_SHA256 = "83c39c50a682875aeeb0efe6147212938dcb1356650a1e06687ebbb1f91f7bf9"
SOURCE_CONTENT_HASH = 0x65714C1A
EXPECTED_TARGETS = 17


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def nearest_indices(image: Image.Image, colours: tuple[tuple[int, int, int, int], ...]) -> Image.Image:
    cache: dict[tuple[int, int, int, int], int] = {}
    indices = bytearray()
    for pixel in image.getdata():
        if pixel not in cache:
            cache[pixel] = min(
                range(len(colours)),
                key=lambda index: sum((pixel[channel] - colours[index][channel]) ** 2 for channel in range(4)),
            )
        indices.append(cache[pixel])
    return Image.frombytes("L", image.size, bytes(indices))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("reference", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--preview", type=Path, required=True)
    args = parser.parse_args()

    source_hash = file_sha256(args.source)
    reference_hash = file_sha256(args.reference)
    if source_hash != EXPECTED_STAGE_SHA256:
        raise SystemExit(f"unexpected source STAGE.DAT SHA-256: {source_hash}")
    if reference_hash != EXPECTED_REFERENCE_SHA256:
        raise SystemExit(f"unexpected translated sign SHA-256: {reference_hash}")
    reference = Image.open(args.reference).convert("RGBA")
    if reference.size != (256, 128):
        raise SystemExit(f"translated sign must be 256x128, got {reference.size}")

    source = args.source.read_bytes()
    output = bytearray(source)
    targets = []
    first_preview = None
    allowed_ranges = []
    for entry in inspect_nispack.read_entries(args.source):
        if not entry.name.lower().endswith(".gm3"):
            continue
        payload = source[entry.offset:entry.offset + entry.size]
        parsed = gm3_assets.parse(payload)
        for texture in parsed.textures:
            raw = payload[texture.pixel_offset:texture.pixel_offset + texture.pixel_size]
            if stable_quick_tex_hash(raw) != SOURCE_CONTENT_HASH:
                continue
            if (texture.width, texture.height, texture.bits_per_pixel) != (256, 128, 8):
                raise SystemExit(f"content hash collision at {entry.name}/texture-{texture.index}")
            indices = nearest_indices(reference, gm3_assets.palette(payload, texture))
            replaced = gm3_assets.replace_texture_indices(payload, texture, indices)
            decoded = gm3_assets.decode_texture(replaced, gm3_assets.parse(replaced).textures[texture.index])
            absolute_start = entry.offset + texture.pixel_offset
            absolute_end = absolute_start + texture.pixel_size
            output[entry.offset:entry.offset + entry.size] = replaced
            allowed_ranges.append((absolute_start, absolute_end))
            difference = ImageChops.difference(reference, decoded)
            stats = ImageStat.Stat(difference)
            targets.append({
                "entry": entry.name,
                "texture": texture.index,
                "pixel_range": [absolute_start, absolute_end],
                "source_quick_hash": f"{SOURCE_CONTENT_HASH:08x}",
                "replacement_quick_hash": f"{stable_quick_tex_hash(replaced[texture.pixel_offset:texture.pixel_offset + texture.pixel_size]):08x}",
                "mean_absolute_rgba_error": [round(value, 6) for value in stats.mean],
            })
            if first_preview is None:
                first_preview = decoded

    if len(targets) != EXPECTED_TARGETS:
        raise SystemExit(f"expected {EXPECTED_TARGETS} world-sign owners, found {len(targets)}")
    changed = [index for index, (old, new) in enumerate(zip(source, output)) if old != new]
    if not changed:
        raise SystemExit("replacement produced no changed bytes")
    outside = [
        index for index in changed
        if not any(start <= index < end for start, end in allowed_ranges)
    ]
    if outside:
        raise SystemExit(f"bytes changed outside approved texture payloads: {outside[:10]}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(output)
    args.preview.parent.mkdir(parents=True, exist_ok=True)
    assert first_preview is not None
    first_preview.save(args.preview)
    report = {
        "status": "PASS: translated world sign baked into all GM3 owners with bounded writes",
        "source": str(args.source),
        "source_sha256": source_hash,
        "reference": str(args.reference),
        "reference_sha256": reference_hash,
        "output": str(args.output),
        "output_sha256": file_sha256(args.output),
        "output_size": args.output.stat().st_size,
        "changed_byte_count": len(changed),
        "changed_bounds": [min(changed), max(changed) + 1],
        "target_count": len(targets),
        "targets": targets,
        "non_target_changed_bytes": len(outside),
        "preview": str(args.preview),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(report["status"])
    print(f"targets={len(targets)} changed_bytes={len(changed)}")
    print(f"output_sha256={report['output_sha256']}")
    print(f"report={args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
