#!/usr/bin/env python3
"""Export selected textures from a GM3 entry stored in STAGE.DAT."""

from __future__ import annotations

import argparse
from pathlib import Path

import gm3_assets
import inspect_nispack


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage_dat", type=Path)
    parser.add_argument("entry")
    parser.add_argument("texture", type=int, nargs="+")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    entry = next(
        (item for item in inspect_nispack.read_entries(args.stage_dat) if item.name == args.entry),
        None,
    )
    if entry is None:
        raise SystemExit(f"entry not found: {args.entry}")
    with args.stage_dat.open("rb") as stream:
        stream.seek(entry.offset)
        data = stream.read(entry.size)
    gm3 = gm3_assets.parse(data)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for index in args.texture:
        if not 0 <= index < len(gm3.textures):
            raise SystemExit(f"texture index outside {args.entry}: {index}")
        texture = gm3.textures[index]
        destination = args.output_dir / (
            f"{args.entry}_texture-{index}_{texture.width}x{texture.height}.png"
        )
        gm3_assets.decode_texture(data, texture).save(destination)
        print(f"OK: {args.entry}/texture-{index} -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
