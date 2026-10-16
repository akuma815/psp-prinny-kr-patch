#!/usr/bin/env python3
"""Audit every GM3 and DAT/NFG20 entry in Prinny's STAGE.DAT."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import Counter, defaultdict
from pathlib import Path

import gm3_assets
import inspect_nispack


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage_dat", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()

    archive = args.stage_dat.read_bytes()
    entries = inspect_nispack.read_entries(args.stage_dat)
    geometry = Counter()
    version_counts = Counter()
    unknown_counts = Counter()
    texture_hash_owners: dict[str, list[str]] = defaultdict(list)
    gm3_rows = []
    dat_rows = []
    texture_total = 0
    roundtrip_total = 0

    for entry in entries:
        payload = archive[entry.offset:entry.offset + entry.size]
        if len(payload) != entry.size:
            raise ValueError(f"short STAGE.DAT entry read: {entry.name}")
        if entry.name.lower().endswith(".gm3"):
            parsed = gm3_assets.parse(payload)
            version_counts[parsed.version] += 1
            unknown_counts[parsed.unknown] += 1
            textures = []
            for texture in parsed.textures:
                indices = gm3_assets.decode_indices(payload, texture)
                rebuilt = gm3_assets.replace_texture_indices(payload, texture, indices)
                if rebuilt != payload:
                    raise ValueError(f"GM3 no-op roundtrip changed bytes: {entry.name} texture {texture.index}")
                roundtrip_total += 1
                image = gm3_assets.decode_texture(payload, texture)
                pixel_hash = sha256(image.tobytes())
                texture_hash_owners[pixel_hash].append(f"{entry.name}/texture-{texture.index}")
                geometry[(texture.width, texture.height)] += 1
                texture_total += 1
                textures.append({
                    "index": texture.index,
                    "offset": texture.offset,
                    "size": texture.size,
                    "width": texture.width,
                    "height": texture.height,
                    "palette_count": texture.palette_count,
                    "log2_width": texture.log2_width,
                    "log2_height": texture.log2_height,
                    "swizzled": texture.swizzled,
                    "flags": texture.flags,
                    "rgba_sha256": pixel_hash,
                })
            gm3_rows.append({
                "archive_index": entry.index,
                "name": entry.name,
                "archive_offset": entry.offset,
                "size": entry.size,
                "sha256": sha256(payload),
                "version": parsed.version,
                "table_count": parsed.table_count,
                "unknown": parsed.unknown,
                "header_extra": list(parsed.header_extra),
                "model_offset": parsed.model_offset,
                "model_offsets": list(parsed.model_offsets),
                "model_size": parsed.texture_offsets[0] - parsed.model_offset,
                "texture_count": parsed.texture_count,
                "textures": textures,
            })
        else:
            magic = payload[:8].rstrip(b"\0").decode("ascii", errors="replace")
            words = list(struct.unpack_from("<8I", payload)) if len(payload) >= 32 else []
            dat_rows.append({
                "archive_index": entry.index,
                "name": entry.name,
                "archive_offset": entry.offset,
                "size": entry.size,
                "sha256": sha256(payload),
                "magic": magic,
                "head_u32": words,
            })

    duplicate_groups = [
        {"rgba_sha256": key, "owners": owners}
        for key, owners in sorted(texture_hash_owners.items())
        if len(owners) > 1
    ]
    nfg20_count = sum(row["magic"] == "NFG20" for row in dat_rows)
    report = {
        "schema_version": 1,
        "status": "PASS: complete STAGE.DAT GM3 corpus parsed and no-op round-tripped",
        "stage_dat": {
            "path": args.stage_dat.resolve().as_posix(),
            "size": len(archive),
            "sha256": sha256(archive),
            "entry_count": len(entries),
        },
        "summary": {
            "gm3_entries": len(gm3_rows),
            "dat_entries": len(dat_rows),
            "nfg20_entries": nfg20_count,
            "gm3_textures": texture_total,
            "gm3_noop_roundtrips": roundtrip_total,
            "gm3_versions": {str(key): value for key, value in sorted(version_counts.items())},
            "gm3_unknown_values": len(unknown_counts),
            "texture_geometry": {
                f"{width}x{height}": count
                for (width, height), count in sorted(geometry.items())
            },
            "unique_rgba_textures": len(texture_hash_owners),
            "duplicate_rgba_groups": len(duplicate_groups),
        },
        "gm3": gm3_rows,
        "dat": dat_rows,
        "duplicate_textures": duplicate_groups,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(report["status"])
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"report={args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
