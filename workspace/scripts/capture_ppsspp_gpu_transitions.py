#!/usr/bin/env python3
"""Capture consecutive PPSSPP GE frames while moving a menu selection."""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path

from ppsspp_basetalk_probe import Debugger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uri", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=8)
    parser.add_argument("--button", default="down")
    parser.add_argument("--press-seconds", type=float, default=0.05)
    parser.add_argument("--settle-seconds", type=float, default=0.08)
    parser.add_argument("--timeout", type=float, default=60.0)
    return parser.parse_args()


def decode_data_uri(uri: str) -> bytes:
    prefix, encoded = uri.split(",", 1)
    if ";base64" not in prefix:
        raise ValueError(f"Unsupported data URI: {prefix}")
    return base64.b64decode(encoded)


def request(
    debugger: Debugger, timeout: float, event: str, **params: object
) -> dict[str, object]:
    # Debugger.receive() narrows the socket timeout to the remaining request
    # time.  A large GE dump can otherwise leave the next request with only a
    # few milliseconds.
    debugger.ws.settimeout(timeout)
    return debugger.request(event, **params)


def capture(
    debugger: Debugger, timeout: float, path: Path
) -> dict[str, object]:
    response = request(debugger, timeout, "gpu.record.dump")
    data = decode_data_uri(response["uri"])
    path.write_bytes(data)
    return {"path": str(path), "bytes": len(data)}


def main() -> int:
    args = parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    debugger = Debugger(args.uri, args.timeout)
    captures: list[dict[str, object]] = []
    try:
        version = request(
            debugger,
            args.timeout,
            "version", name="Prinny GPU transition capture", version="1.0.0"
        )
        game = request(debugger, args.timeout, "game.status")
        status = request(debugger, args.timeout, "cpu.status")
        if status["stepping"]:
            debugger.send("cpu.resume")
            debugger.wait_event("cpu.resume", args.timeout)
            time.sleep(args.settle_seconds)

        captures.append(
            {
                "index": 0,
                "phase": "before_input",
                **capture(
                    debugger,
                    args.timeout,
                    args.output_dir / "frame_00_before.ppdmp",
                ),
            }
        )

        for index in range(1, args.steps + 1):
            request(
                debugger,
                args.timeout,
                "input.buttons.send", buttons={args.button: True}
            )
            time.sleep(args.press_seconds)
            request(
                debugger,
                args.timeout,
                "input.buttons.send", buttons={args.button: False}
            )
            time.sleep(args.settle_seconds)
            path = args.output_dir / f"frame_{index:02d}_{args.button}.ppdmp"
            captures.append(
                {
                    "index": index,
                    "phase": f"after_{args.button}",
                    **capture(debugger, args.timeout, path),
                }
            )
            print(f"captured {path.name}", flush=True)

        manifest = {
            "schema_version": 1,
            "uri": args.uri,
            "ppsspp": version,
            "game": game,
            "button": args.button,
            "steps": args.steps,
            "press_seconds": args.press_seconds,
            "settle_seconds": args.settle_seconds,
            "captures": captures,
        }
        manifest_path = args.output_dir / "capture.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0
    finally:
        try:
            request(
                debugger,
                args.timeout,
                "input.buttons.send", buttons={args.button: False}
            )
        except Exception:
            pass
        debugger.close()


if __name__ == "__main__":
    raise SystemExit(main())
