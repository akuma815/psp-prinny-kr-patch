#!/usr/bin/env python3
"""Capture BaseTalk loader state through PPSSPP's WebSocket debugger."""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path
from typing import Any

import websocket


LOADER_BREAK = 0x0888B32C
COUNT_GLOBAL = 0x08A54BDC
POINTER_GLOBAL = 0x08A54BE0


class Debugger:
    def __init__(self, uri: str, timeout: float) -> None:
        self.ws = websocket.create_connection(
            uri,
            subprotocols=["debugger.ppsspp.org"],
            timeout=timeout,
            http_proxy_host=None,
        )
        self.next_ticket = 1
        self.pending: list[dict[str, Any]] = []

    def close(self) -> None:
        self.ws.close()

    def send(self, event: str, **params: Any) -> str:
        ticket = str(self.next_ticket)
        self.next_ticket += 1
        self.ws.send(json.dumps({"event": event, "ticket": ticket, **params}))
        return ticket

    def receive(self, deadline: float) -> dict[str, Any]:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("PPSSPP debugger response timed out")
        self.ws.settimeout(remaining)
        return json.loads(self.ws.recv())

    def request(self, event: str, **params: Any) -> dict[str, Any]:
        ticket = self.send(event, **params)
        deadline = time.monotonic() + self.ws.gettimeout()
        while True:
            message = self.receive(deadline)
            if message.get("ticket") == ticket:
                if message.get("event") == "error":
                    raise RuntimeError(message.get("message", "PPSSPP debugger error"))
                return message
            self.pending.append(message)

    def wait_event(self, event: str, timeout: float) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while True:
            for index, message in enumerate(self.pending):
                if message.get("event") == event:
                    return self.pending.pop(index)
            message = self.receive(deadline)
            if message.get("event") == event:
                return message
            self.pending.append(message)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uri", required=True, help="Example: ws://192.168.0.10:15100/debugger")
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--dump-size",
        type=int,
        default=844,
        help="Records plus footer; the global pointer skips the 4-byte header",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    debugger = Debugger(args.uri, args.timeout)
    breakpoint_added = False
    cpu_stopped = False
    try:
        version = debugger.request(
            "version", name="prinny-basetalk-probe", version="1.0.0"
        )
        game_before = debugger.request("game.status")
        debugger.request(
            "cpu.breakpoint.add", address=LOADER_BREAK, enabled=True, log=False
        )
        breakpoint_added = True
        debugger.request("game.reset")

        stop = debugger.wait_event("cpu.stepping", args.timeout)
        cpu_stopped = True
        if stop.get("pc") != LOADER_BREAK:
            raise RuntimeError(
                f"unexpected stop PC 0x{stop.get('pc', 0):08X}; "
                f"expected 0x{LOADER_BREAK:08X}"
            )

        count_response = debugger.request("memory.read_u32", address=COUNT_GLOBAL)
        pointer_response = debugger.request("memory.read_u32", address=POINTER_GLOBAL)
        pointer = pointer_response["value"]
        dump_response = debugger.request(
            "memory.read", address=pointer, size=args.dump_size
        )
        data = base64.b64decode(dump_response["base64"])

        result = {
            "tool": "ppsspp_basetalk_probe.py",
            "ppsspp": version,
            "game_before_reset": game_before,
            "stop": stop,
            "addresses": {
                "loader_break": LOADER_BREAK,
                "count_global": COUNT_GLOBAL,
                "pointer_global": POINTER_GLOBAL,
            },
            "count_word": count_response["value"],
            "pointer": pointer,
            "dump_size": len(data),
            "dump_base64": base64.b64encode(data).decode("ascii"),
        }
        rendered = json.dumps(result, ensure_ascii=False, indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered + "\n", encoding="utf-8")
        print(rendered)
        return 0
    finally:
        if breakpoint_added:
            try:
                debugger.request("cpu.breakpoint.remove", address=LOADER_BREAK)
            except Exception as exc:
                print(f"warning: could not remove breakpoint: {exc}", file=sys.stderr)
        if cpu_stopped:
            try:
                debugger.send("cpu.resume")
                debugger.wait_event("cpu.resume", 5.0)
            except Exception as exc:
                print(f"warning: could not resume CPU: {exc}", file=sys.stderr)
        debugger.close()


if __name__ == "__main__":
    raise SystemExit(main())
