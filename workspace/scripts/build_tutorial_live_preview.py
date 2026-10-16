#!/usr/bin/env python3
"""Generate PPSSPP replacement textures for tutorial layout tuning."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from PIL import Image

import anime_assets
import build_tutorial_graphics_poc
import txp_assets


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pixel_data(image: Image.Image):
    getter = getattr(image, "get_flattened_data", None)
    return getter() if getter is not None else image.getdata()


def archive_texture_indices(archive: bytes, config: dict[str, object], texture_index: int) -> Image.Image:
    source = config["source"]
    offset = int(source["entry_offset"], 0)
    size = int(source["entry_size"])
    anime = archive[offset:offset + size]
    record = anime_assets.parse_records(anime)[int(source["record_index"])]
    return txp_assets.decode_indices(anime_assets.texture_as_txp(anime, record, texture_index))


def derive_rgba_palette(
    indices: Image.Image, dump: Image.Image
) -> tuple[dict[int, tuple[int, int, int, int]], dict[int, float]]:
    rgba = dump.convert("RGBA")
    if rgba.size != indices.size:
        raise ValueError(f"dump geometry mismatch: {rgba.size} != {indices.size}")
    colors: dict[int, Counter[tuple[int, int, int, int]]] = {}
    for index, color in zip(indices.tobytes(), pixel_data(rgba)):
        if color[3] == 0:
            color = (0, 0, 0, 0)
        colors.setdefault(index, Counter())[color] += 1
    mapping: dict[int, tuple[int, int, int, int]] = {}
    confidence: dict[int, float] = {}
    for index, counts in colors.items():
        color, count = counts.most_common(1)[0]
        total = counts.total()
        ratio = count / total
        if ratio < 0.5:
            raise ValueError(
                f"PPSSPP dump has no dominant RGBA value for index {index}: "
                f"{count}/{total}; variants={counts.most_common(5)}"
            )
        mapping[index] = color
        confidence[index] = ratio
    return mapping, confidence


def render_replacement(
    baseline: Image.Image,
    candidate: Image.Image,
    mapping: dict[int, tuple[int, int, int, int]],
    dump: Image.Image,
    force_positions: set[int] | None = None,
) -> Image.Image:
    missing = sorted(set(candidate.tobytes()) - set(mapping))
    if missing:
        raise ValueError(f"candidate uses palette indices absent from baseline dump: {missing}")
    output = dump.convert("RGBA")
    pixels = list(pixel_data(output))
    forced = force_positions or set()
    for position, (before, after) in enumerate(zip(baseline.tobytes(), candidate.tobytes())):
        if before != after or position in forced:
            pixels[position] = mapping[after]
    output.putdata(pixels)
    return output


def managed_texture_positions(
    config: dict[str, object], texture_index: int, size: tuple[int, int]
) -> set[int]:
    width, height = size
    bounds: list[list[int]] = []
    texture = next(
        item for item in config["textures"] if int(item["texture_index"]) == texture_index
    )
    bounds.extend(block["clear_bounds"] for block in texture["blocks"])
    for relocation in config.get("sprite_relocations", []):
        source = relocation["source_bounds"]
        if int(relocation["source_texture"]) == texture_index:
            bounds.append(source)
        if int(relocation["destination_texture"]) == texture_index:
            x, y = relocation["destination_xy"]
            bounds.append([x, y, x + source[2] - source[0], y + source[3] - source[1]])

    positions: set[int] = set()
    for left, top, right, bottom in bounds:
        if not (0 <= left <= right <= width and 0 <= top <= bottom <= height):
            raise ValueError(f"managed bounds outside texture {texture_index}: {[left, top, right, bottom]}")
        for y in range(top, bottom):
            positions.update(range(y * width + left, y * width + right))
    return positions


def merge_palette_fallback(
    mapping: dict[int, tuple[int, int, int, int]],
    confidence: dict[int, float],
    fallback_mapping: dict[int, tuple[int, int, int, int]],
    fallback_confidence: dict[int, float],
) -> list[int]:
    added = []
    for index, color in fallback_mapping.items():
        if index not in mapping:
            mapping[index] = color
            confidence[index] = fallback_confidence[index]
            added.append(index)
    return added


def write_texture_aliases(
    dump_dir: Path,
    replacement_dir: Path,
    outputs: list[dict[str, object]],
) -> dict[str, object]:
    """Map every observed content-hash variant of each atlas to the live PNG."""
    canonical_by_prefix: dict[str, tuple[str, tuple[int, int]]] = {}
    for output in outputs:
        name = Path(str(output["output"])).name
        prefix = Path(name).stem[:16]
        size = tuple(int(value) for value in output["size"])
        canonical_by_prefix[prefix] = (name, size)

    # Keep aliases owned by the baked-graphics preview. Running either refresh
    # command must not silently disable the other live-preview set.
    aliases: dict[str, str] = {}
    ini_path = replacement_dir / "textures.ini"
    if ini_path.is_file():
        section = ""
        for raw in ini_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line.startswith("[") and line.endswith("]"):
                section = line.lower()
                continue
            if section == "[hashes]" and "=" in line:
                key, value = (part.strip() for part in line.split("=", 1))
                if key and value:
                    aliases[key] = value
    owned_aliases: dict[str, str] = {}
    for dump_path in sorted(dump_dir.glob("*.png")):
        match = next(
            (
                (canonical, expected_size)
                for prefix, (canonical, expected_size) in canonical_by_prefix.items()
                if dump_path.stem.startswith(prefix)
            ),
            None,
        )
        if match is None:
            continue
        canonical, expected_size = match
        with Image.open(dump_path) as dump:
            if dump.size != expected_size:
                continue
        owned_aliases[dump_path.stem] = canonical
    aliases.update(owned_aliases)

    lines = [
        "[options]",
        "version = 1",
        "hash = quick",
        "ignoreAddress = false",
        "",
        "[hashes]",
    ]
    lines.extend(f"{key} = {aliases[key]}" for key in sorted(aliases))
    ini_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "path": ini_path.as_posix(),
        "alias_count": len(owned_aliases),
        "total_alias_count": len(aliases),
        "sha256": sha256(ini_path.read_bytes()),
    }


def build(
    manifest_path: Path,
    config_path: Path,
    original_archive_path: Path,
    baseline_archive_path: Path,
    font_path: Path,
    dump_dir: Path,
    replacement_dir: Path,
    work_dir: Path,
) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    config = json.loads(config_path.read_text(encoding="utf-8"))
    baseline = baseline_archive_path.read_bytes()
    expected_hash = manifest["baseline"]["archive_sha256"]
    if sha256(baseline) != expected_hash:
        raise ValueError("live-preview baseline ANIME.DAT hash changed")

    generated_dir = work_dir / "generated"
    build_report = build_tutorial_graphics_poc.build(
        config_path, original_archive_path, font_path, generated_dir
    )
    candidate = (generated_dir / "ANIME.DAT").read_bytes()
    replacement_dir.mkdir(parents=True, exist_ok=True)

    outputs = []
    for item in manifest["textures"]:
        texture_index = int(item["texture_index"])
        baseline_indices = archive_texture_indices(baseline, config, texture_index)
        candidate_indices = archive_texture_indices(candidate, config, texture_index)
        expected_size = tuple(int(value) for value in item["size"])
        if baseline_indices.size != expected_size or candidate_indices.size != expected_size:
            raise ValueError(f"texture {texture_index} geometry changed")
        changed_pixels = sum(
            before != after
            for before, after in zip(baseline_indices.tobytes(), candidate_indices.tobytes())
        )
        forced_positions = managed_texture_positions(config, texture_index, expected_size)
        for name in item["dumps"]:
            dump_path = dump_dir / name
            if not dump_path.is_file():
                raise FileNotFoundError(f"required PPSSPP baseline dump is missing: {dump_path}")
            with Image.open(dump_path) as dump:
                mapping, confidence = derive_rgba_palette(baseline_indices, dump)
                fallback_indices_added = []
                for fallback in item.get("palette_fallbacks", []):
                    fallback_texture_index = int(fallback["texture_index"])
                    fallback_baseline_indices = archive_texture_indices(
                        baseline, config, fallback_texture_index
                    )
                    fallback_dump_path = dump_dir / str(fallback["dump"])
                    if not fallback_dump_path.is_file():
                        raise FileNotFoundError(
                            f"required PPSSPP palette fallback dump is missing: {fallback_dump_path}"
                        )
                    with Image.open(fallback_dump_path) as fallback_dump:
                        fallback_mapping, fallback_confidence = derive_rgba_palette(
                            fallback_baseline_indices, fallback_dump
                        )
                    fallback_indices_added.extend(merge_palette_fallback(
                        mapping, confidence, fallback_mapping, fallback_confidence
                    ))
                replacement = render_replacement(
                    baseline_indices,
                    candidate_indices,
                    mapping,
                    dump,
                    forced_positions,
                )
            output_path = replacement_dir / name
            replacement.save(output_path)
            outputs.append({
                "texture_index": texture_index,
                "dump": dump_path.as_posix(),
                "output": output_path.as_posix(),
                "size": list(replacement.size),
                "changed_index_pixels": changed_pixels,
                "managed_output_pixels": len(forced_positions),
                "minimum_palette_confidence": min(confidence.values()),
                "palette_fallback_indices": sorted(set(fallback_indices_added)),
                "sha256": sha256(output_path.read_bytes()),
            })

    texture_aliases = write_texture_aliases(dump_dir, replacement_dir, outputs)

    work_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": 1,
        "status": "PASS: tutorial PPSSPP replacement textures generated",
        "profile_id": manifest["profile_id"],
        "game_id": manifest["game_id"],
        "baseline": manifest["baseline"],
        "candidate_archive_sha256": build_report["output"]["sha256"],
        "outputs": outputs,
        "texture_aliases": texture_aliases,
        "requires_iso_rebuild": False,
        "runtime_gate": "Restart PPSSPP and inspect the tutorial pages with the v3 baseline ISO",
    }
    report_path = work_dir / "tutorial_live_preview_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("config", type=Path)
    parser.add_argument("original_archive", type=Path)
    parser.add_argument("baseline_archive", type=Path)
    parser.add_argument("font", type=Path)
    parser.add_argument("dump_dir", type=Path)
    parser.add_argument("replacement_dir", type=Path)
    parser.add_argument("work_dir", type=Path)
    args = parser.parse_args()
    report = build(
        args.manifest,
        args.config,
        args.original_archive,
        args.baseline_archive,
        args.font,
        args.dump_dir,
        args.replacement_dir,
        args.work_dir,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
