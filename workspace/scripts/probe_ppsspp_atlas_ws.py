#!/usr/bin/env python3
"""Read-only live probe for the Prinny dynamic Hangul atlas patch."""

from __future__ import annotations

import argparse
import base64
import json
import struct
import time
from pathlib import Path

import websocket


GLOBAL_PAGE = 0x08A541D4
GLOBAL_PAGE_POINTERS = 0x08A54214
GLOBAL_COUNT = 0x08A5421C
PATCH_STATE = 0x088D10CC
PATCH_STATE_SIZE = 0x368


class PPSSPPDebugger:
    def __init__(self, uri: str) -> None:
        self.ws = websocket.create_connection(
            uri,
            subprotocols=["debugger.ppsspp.org"],
            timeout=2,
        )
        self.ticket = 0

    def close(self) -> None:
        self.ws.close()

    def request(self, event: str, **params: object) -> dict[str, object]:
        self.ticket += 1
        ticket = f"probe-{self.ticket}"
        self.ws.send(json.dumps({"event": event, "ticket": ticket, **params}))
        while True:
            response = json.loads(self.ws.recv())
            if response.get("ticket") != ticket:
                continue
            if response.get("event") == "error":
                raise RuntimeError(str(response.get("message", response)))
            return response

    def read_u32(self, address: int) -> int:
        response = self.request("memory.read_u32", address=address)
        return int(response["value"])

    def read(self, address: int, size: int) -> bytes:
        response = self.request("memory.read", address=address, size=size)
        return base64.b64decode(str(response["base64"]))


def u32_words(data: bytes) -> list[int]:
    return list(struct.unpack(f"<{len(data) // 4}I", data))


def snapshot(debugger: PPSSPPDebugger) -> dict[str, object]:
    page = debugger.read_u32(GLOBAL_PAGE)
    pointers = u32_words(debugger.read(GLOBAL_PAGE_POINTERS, 8))
    global_count = debugger.read_u32(GLOBAL_COUNT)
    state = debugger.read(PATCH_STATE, PATCH_STATE_SIZE)
    page_counts = list(struct.unpack_from("<2I", state))
    cache0 = list(struct.unpack_from("<216H", state, 8))
    cache1 = list(struct.unpack_from("<216H", state, 8 + 216 * 2))
    return {
        "time": time.time(),
        "page": page,
        "page_pointers": pointers,
        "global_count": global_count,
        "page_counts": page_counts,
        "cache0": cache0,
        "cache1": cache1,
    }


def compact_change(previous: dict[str, object] | None, current: dict[str, object]) -> dict[str, object]:
    result = {
        "time": current["time"],
        "page": current["page"],
        "page_pointers": current["page_pointers"],
        "global_count": current["global_count"],
        "page_counts": current["page_counts"],
    }
    if previous is None:
        result["cache0_nonzero"] = [
            [i, value] for i, value in enumerate(current["cache0"]) if value
        ]
        result["cache1_nonzero"] = [
            [i, value] for i, value in enumerate(current["cache1"]) if value
        ]
        return result

    for name in ("cache0", "cache1"):
        before = previous[name]
        after = current[name]
        result[f"{name}_changes"] = [
            [i, before[i], after[i]]
            for i in range(len(after))
            if before[i] != after[i]
        ]
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", default="ws://127.0.0.1:2982/debugger")
    parser.add_argument("--seconds", type=float, default=90.0)
    parser.add_argument("--interval", type=float, default=0.05)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    debugger = PPSSPPDebugger(args.uri)
    output = args.output.open("w", encoding="utf-8") if args.output else None
    try:
        version = debugger.request("version", name="prinny-atlas-probe", version="1")
        print(json.dumps({"connected": version}, ensure_ascii=False))
        previous = None
        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline:
            current = snapshot(debugger)
            if previous is None or any(
                current[key] != previous[key]
                for key in ("page", "page_pointers", "global_count", "page_counts", "cache0", "cache1")
            ):
                change = compact_change(previous, current)
                line = json.dumps(change, ensure_ascii=False)
                print(line, flush=True)
                if output:
                    output.write(line + "\n")
                    output.flush()
                previous = current
            time.sleep(args.interval)
    finally:
        if output:
            output.close()
        debugger.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
