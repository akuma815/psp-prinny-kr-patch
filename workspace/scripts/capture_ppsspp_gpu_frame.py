#!/usr/bin/env python3
"""Capture a live PPSSPP screenshot and the next GE frame dump."""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

from ppsspp_basetalk_probe import Debugger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uri", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=60.0)
    return parser.parse_args()


def decode_data_uri(uri: str) -> bytes:
    prefix, encoded = uri.split(",", 1)
    if ";base64" not in prefix:
        raise ValueError(f"Unsupported data URI: {prefix}")
    return base64.b64decode(encoded)


def main() -> int:
    args = parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    debugger = Debugger(args.uri, args.timeout)
    try:
        debugger.request("version", name="Codex GPU frame capture", version="1.0.0")

        screenshot_path = args.output_dir / "screenshot.png"
        screenshot_error = None
        status = debugger.request("cpu.status")
        was_running = not status["stepping"]
        if was_running:
            debugger.send("cpu.stepping")
            debugger.wait_event("cpu.stepping", args.timeout)
        try:
            screenshot = debugger.request("gpu.buffer.screenshot", type="uri")
            screenshot_path.write_bytes(decode_data_uri(screenshot["uri"]))
        except RuntimeError as exc:
            screenshot_error = str(exc)
        finally:
            debugger.send("cpu.resume")
            debugger.wait_event("cpu.resume", args.timeout)

        dump = debugger.request("gpu.record.dump")
        dump_path = args.output_dir / "frame.ppdmp"
        dump_path.write_bytes(decode_data_uri(dump["uri"]))

        manifest = {
            "uri": args.uri,
            "screenshot": str(screenshot_path),
            "screenshot_bytes": (
                screenshot_path.stat().st_size if screenshot_path.exists() else None
            ),
            "screenshot_error": screenshot_error,
            "gpu_dump": str(dump_path),
            "gpu_dump_bytes": dump_path.stat().st_size,
        }
        manifest_path = args.output_dir / "capture.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0
    finally:
        debugger.close()


if __name__ == "__main__":
    raise SystemExit(main())
