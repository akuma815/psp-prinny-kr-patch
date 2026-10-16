#!/usr/bin/env python3
"""Dump one or more PSP memory ranges through PPSSPP's WebSocket debugger."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path

from ppsspp_basetalk_probe import Debugger


def range_value(text: str) -> tuple[int, int]:
    address, size = text.split(":", 1)
    return int(address, 0), int(size, 0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uri", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--range", dest="ranges", action="append", type=range_value, required=True)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--live",
        action="store_true",
        help="read while the CPU is running (use for immutable texture buffers)",
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    debugger = Debugger(args.uri, args.timeout)
    rows = []
    was_running = False
    try:
        version = debugger.request("version", name="prinny-memory-dump", version="1.0.0")
        game = debugger.request("game.status")
        status = debugger.request("cpu.status")
        was_running = not status["stepping"]
        if was_running and not args.live:
            debugger.send("cpu.stepping")
            debugger.wait_event("cpu.stepping", args.timeout)
        for address, size in args.ranges:
            response = debugger.request("memory.read", address=address, size=size)
            data = base64.b64decode(response["base64"])
            if len(data) != size:
                raise ValueError(f"short memory read at 0x{address:08X}: {len(data)} != {size}")
            destination = args.output_dir / f"memory_{address:08x}_{size:x}.bin"
            destination.write_bytes(data)
            rows.append({
                "address": f"0x{address:08X}",
                "size": size,
                "path": str(destination),
                "sha256": hashlib.sha256(data).hexdigest(),
            })
        report = {"ppsspp": version, "game": game, "ranges": rows}
        report_path = args.output_dir / "memory_dump.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        if was_running and not args.live:
            debugger.send("cpu.resume")
            debugger.wait_event("cpu.resume", args.timeout)
        debugger.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
