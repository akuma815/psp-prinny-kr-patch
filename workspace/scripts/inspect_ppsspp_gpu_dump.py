#!/usr/bin/env python3
"""Inspect PPSSPP GE frame dump command and payload structure."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path

import zstandard


TYPE_NAMES = {
    0: "INIT",
    1: "REGISTERS",
    2: "VERTICES",
    3: "INDICES",
    4: "CLUT",
    5: "TRANSFERSRC",
    6: "MEMSET",
    7: "MEMCPYDEST",
    8: "MEMCPYDATA",
    9: "DISPLAY",
    10: "CLUTADDR",
    11: "EDRAMTRANS",
    **{0x10 + i: f"TEXTURE{i}" for i in range(8)},
    **{0x18 + i: f"FRAMEBUF{i}" for i in range(8)},
}


def read_block(data: bytes, offset: int, expected: int) -> tuple[bytes, int]:
    compressed_size = struct.unpack_from("<I", data, offset)[0]
    offset += 4
    compressed = data[offset : offset + compressed_size]
    decoded = zstandard.ZstdDecompressor().decompress(
        compressed, max_output_size=expected
    )
    if len(decoded) != expected:
        raise ValueError(f"Decoded {len(decoded)} bytes, expected {expected}")
    return decoded, offset + compressed_size


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dump", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    raw = args.dump.read_bytes()
    magic, version, game_id = struct.unpack_from("<8sI9s", raw, 0)
    if magic != b"PPSSPPGE":
        raise ValueError("Not a PPSSPP GE dump")
    command_count, push_size = struct.unpack_from("<II", raw, 24)
    commands_raw, offset = read_block(raw, 32, command_count * 9)
    pushbuf, offset = read_block(raw, offset, push_size)

    commands = []
    for i in range(command_count):
        type_id, size, pointer = struct.unpack_from("<BII", commands_raw, i * 9)
        payload = pushbuf[pointer : pointer + size]
        entry = {
            "index": i,
            "type": TYPE_NAMES.get(type_id, f"UNKNOWN_{type_id:02X}"),
            "type_id": type_id,
            "size": size,
            "pointer": pointer,
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        if type_id == 2:
            entry["hex"] = payload.hex()
        elif type_id == 1:
            ops = list(struct.unpack(f"<{size // 4}I", payload))
            entry["ops"] = [f"0x{op:08X}" for op in ops]
            entry["opcodes"] = [op >> 24 for op in ops]
        commands.append(entry)

    focused = []
    for command in commands:
        if command["type"] == "VERTICES":
            i = command["index"]
            focused.append(
                {
                    **command,
                    "nearby": [
                        {
                            "index": other["index"],
                            "type": other["type"],
                            "size": other["size"],
                            **(
                                {"ops": other["ops"]}
                                if other["type"] == "REGISTERS"
                                else {}
                            ),
                        }
                        for other in commands[max(0, i - 3) : min(command_count, i + 5)]
                    ],
                }
            )

    report = {
        "header": {
            "version": version,
            "game_id": game_id.rstrip(b"\0").decode("ascii"),
            "command_count": command_count,
            "push_size": push_size,
            "trailing_bytes": len(raw) - offset,
        },
        "type_counts": dict(Counter(command["type"] for command in commands)),
        "vertex_size_counts": dict(
            Counter(
                str(command["size"])
                for command in commands
                if command["type"] == "VERTICES"
            )
        ),
        "texture_size_counts": dict(
            Counter(
                str(command["size"])
                for command in commands
                if command["type"].startswith("TEXTURE")
            )
        ),
        "vertices": focused,
        "commands": commands,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: report[key] for key in ("header", "type_counts", "vertex_size_counts", "texture_size_counts")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
