#!/usr/bin/env python3
"""Compare text glyph draws and atlas cells across PPSSPP GE frame dumps."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from inspect_ppsspp_gpu_dump import TYPE_NAMES, read_block


def parse_dump(path: Path) -> list[dict[str, object]]:
    raw = path.read_bytes()
    magic, _version, _game_id = struct.unpack_from("<8sI9s", raw, 0)
    if magic != b"PPSSPPGE":
        raise ValueError(f"{path}: not a PPSSPP GE dump")
    command_count, push_size = struct.unpack_from("<II", raw, 24)
    commands_raw, offset = read_block(raw, 32, command_count * 9)
    pushbuf, _offset = read_block(raw, offset, push_size)
    commands: list[dict[str, object]] = []
    for index in range(command_count):
        type_id, size, pointer = struct.unpack_from("<BII", commands_raw, index * 9)
        payload = pushbuf[pointer : pointer + size]
        commands.append(
            {
                "index": index,
                "type": TYPE_NAMES.get(type_id, f"UNKNOWN_{type_id:02X}"),
                "size": size,
                "payload": payload,
            }
        )
    return commands


def glyph_draws(commands: list[dict[str, object]]) -> list[dict[str, object]]:
    atlas: bytes | None = None
    atlas_index: int | None = None
    result: list[dict[str, object]] = []
    for command in commands:
        command_type = command["type"]
        payload = command["payload"]
        assert isinstance(payload, bytes)
        if command_type == "TEXTURE0" and command["size"] == 32768:
            atlas = payload
            atlas_index = int(command["index"])
            continue
        if command_type != "VERTICES" or command["size"] != 40 or atlas is None:
            continue
        vertices = [
            struct.unpack_from("<5H", payload, offset)
            for offset in range(0, 40, 10)
        ]
        u_values = [vertex[0] for vertex in vertices]
        v_values = [vertex[1] for vertex in vertices]
        x_values = [vertex[2] for vertex in vertices]
        y_values = [vertex[3] for vertex in vertices]
        u0, u1 = min(u_values), max(u_values)
        v0, v1 = min(v_values), max(v_values)
        if u0 % 2 or u1 - u0 != 20 or v1 - v0 != 14:
            cell = b""
        else:
            byte_x = u0 // 2
            cell = b"".join(
                atlas[(v0 + row) * 128 + byte_x : (v0 + row) * 128 + byte_x + 10]
                for row in range(14)
            )
        result.append(
            {
                "vertex_index": command["index"],
                "atlas_index": atlas_index,
                "atlas_sha256": hashlib.sha256(atlas).hexdigest(),
                "cell_sha256": hashlib.sha256(cell).hexdigest() if cell else None,
                "uv": [u0, v0, u1, v1],
                "xy": [min(x_values), min(y_values), max(x_values), max(y_values)],
            }
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dumps", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    frames: list[dict[str, object]] = []
    for path in args.dumps:
        draws = glyph_draws(parse_dump(path))
        description = [
            draw for draw in draws
            if 235 <= int(draw["xy"][1]) <= 250
        ]
        frames.append(
            {
                "path": str(path),
                "glyph_draw_count": len(draws),
                "description_draw_count": len(description),
                "description": description,
                "description_cell_hashes": [
                    draw["cell_sha256"] for draw in description
                ],
                "description_uvs": [draw["uv"] for draw in description],
                "description_atlas_hashes": sorted(
                    {str(draw["atlas_sha256"]) for draw in description}
                ),
            }
        )

    report = {"schema_version": 1, "frames": frames}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            [
                {
                    "path": frame["path"],
                    "description_draw_count": frame["description_draw_count"],
                    "description_atlas_hashes": frame["description_atlas_hashes"],
                    "description_cell_hashes": frame["description_cell_hashes"],
                }
                for frame in frames
            ],
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
