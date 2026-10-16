#!/usr/bin/env python3
"""Capture the visible PPSSPP window while moving a menu selection."""

from __future__ import annotations

import argparse
import ctypes
import json
import sys
import time
from pathlib import Path
from typing import Any

from PIL import Image, ImageGrab

from ppsspp_basetalk_probe import Debugger


class Rect(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uri", required=True)
    parser.add_argument("--pid", required=True, type=int)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--steps", type=int, default=8)
    parser.add_argument("--button", default="down")
    parser.add_argument("--press-seconds", type=float, default=0.05)
    parser.add_argument("--settle-seconds", type=float, default=0.20)
    parser.add_argument("--timeout", type=float, default=10.0)
    return parser.parse_args()


def request(
    debugger: Debugger, timeout: float, event: str, **params: Any
) -> dict[str, Any]:
    debugger.ws.settimeout(timeout)
    return debugger.request(event, **params)


def window_handle_for_pid(pid: int) -> int:
    user32 = ctypes.windll.user32
    found: list[int] = []
    enum_proc = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p
    )

    @enum_proc
    def callback(hwnd: int, _lparam: int) -> bool:
        process_id = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        if process_id.value == pid and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
            return False
        return True

    user32.EnumWindows(callback, 0)
    if not found:
        raise RuntimeError(f"No visible window for PID {pid}")
    return found[0]


def capture_window(hwnd: int, path: Path) -> tuple[int, int, int, int]:
    user32 = ctypes.windll.user32
    user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.08)
    rect = Rect()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        raise ctypes.WinError()
    bounds = (rect.left, rect.top, rect.right, rect.bottom)
    image: Image.Image = ImageGrab.grab(bbox=bounds, all_screens=True)
    image.save(path)
    return bounds


def main() -> int:
    args = parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    hwnd = window_handle_for_pid(args.pid)
    debugger = Debugger(args.uri, args.timeout)
    captures: list[dict[str, Any]] = []
    try:
        request(
            debugger,
            args.timeout,
            "version",
            name="Prinny visual transition capture",
            version="1.0.0",
        )
        status = request(debugger, args.timeout, "cpu.status")
        if status["stepping"]:
            debugger.send("cpu.resume")
            debugger.wait_event("cpu.resume", args.timeout)
        time.sleep(args.settle_seconds)

        before = args.output_dir / "frame_00_before.png"
        captures.append(
            {
                "index": 0,
                "path": str(before),
                "bounds": capture_window(hwnd, before),
            }
        )

        for index in range(1, args.steps + 1):
            request(
                debugger,
                args.timeout,
                "input.buttons.send",
                buttons={args.button: True},
            )
            time.sleep(args.press_seconds)
            request(
                debugger,
                args.timeout,
                "input.buttons.send",
                buttons={args.button: False},
            )
            time.sleep(args.settle_seconds)
            path = args.output_dir / f"frame_{index:02d}_{args.button}.png"
            captures.append(
                {
                    "index": index,
                    "path": str(path),
                    "bounds": capture_window(hwnd, path),
                }
            )
            print(f"captured {path.name}", flush=True)

        manifest = {
            "schema_version": 1,
            "pid": args.pid,
            "uri": args.uri,
            "button": args.button,
            "steps": args.steps,
            "captures": captures,
        }
        (args.output_dir / "capture.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return 0
    finally:
        try:
            request(
                debugger,
                args.timeout,
                "input.buttons.send",
                buttons={args.button: False},
            )
        except Exception:
            pass
        debugger.close()


if __name__ == "__main__":
    raise SystemExit(main())
