#!/usr/bin/env python3
"""Trace executed NSF message commands through PPSSPP's WebSocket debugger."""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path
from typing import Any

import demo00
import nsf_links
import nsf_messages
import websocket
from ppsspp_basetalk_probe import Debugger


HANDLERS = {
    0x08879060: 1,
    0x08879100: 2,
    0x08879238: 3,
}
VM_PC_OFFSET = 0x48


def decode_message_head(opcode: int, data: bytes) -> dict[str, Any]:
    """Decode the channel and message operand at a message-handler entry."""
    if len(data) < 2:
        raise ValueError("message head is truncated")
    channel = int.from_bytes(data[:1], "little", signed=True)
    if opcode == 1:
        operand, _ = nsf_messages.parse_operand(data, 1)
        return {
            "channel": channel,
            "message_id": operand.value,
            "message_operand": {
                "tag": operand.tag,
                "raw_hex": operand.raw.hex(),
                "value": operand.value,
            },
        }
    if opcode not in (2, 3):
        raise ValueError(f"unsupported message opcode 42 {opcode:02X}")
    if len(data) < 5:
        raise ValueError("literal message ID is truncated")
    return {
        "channel": channel,
        "message_id": int.from_bytes(data[1:5], "little"),
        "message_operand": None,
    }


def gpr_values(response: dict[str, Any]) -> dict[str, int]:
    for category in response["categories"]:
        if category["name"] == "GPR":
            return dict(zip(category["registerNames"], category["uintValues"]))
    raise ValueError("PPSSPP response has no GPR category")


def read_bytes(debugger: Debugger, address: int, size: int) -> bytes:
    response = debugger.request("memory.read", address=address, size=size)
    return base64.b64decode(response["base64"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("nsf", type=Path)
    parser.add_argument("demo00", type=Path)
    parser.add_argument("--uri", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--max-events", type=int, default=500)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--auto-advance",
        action="store_true",
        help="Press title/menu confirmation buttons periodically during the trace",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    nsf = nsf_links.parse_nsf(args.nsf.read_bytes())
    table = demo00.parse(args.demo00.read_bytes())
    references = nsf_messages.scan(nsf, table)
    by_offset = {reference.logical_offset: reference for reference in references}

    debugger = Debugger(args.uri, args.timeout)
    added: list[int] = []
    stopped = False
    events: list[dict[str, Any]] = []
    inputs: list[dict[str, Any]] = []
    try:
        version = debugger.request("version", name="prinny-nsf-trace", version="1.0.0")
        game = debugger.request("game.status")
        for address in HANDLERS:
            debugger.request(
                "cpu.breakpoint.add", address=address, enabled=True, log=False
            )
            added.append(address)

        debugger.request("game.reset")
        started = time.monotonic()
        deadline = time.monotonic() + args.duration
        next_input = started + 3.0
        input_index = 0
        auto_buttons = ("start", "circle", "circle", "circle", "cross")
        while len(events) < args.max_events:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            now = time.monotonic()
            if args.auto_advance and now >= next_input:
                button = auto_buttons[input_index % len(auto_buttons)]
                debugger.send("input.buttons.press", button=button, duration=2)
                inputs.append({"elapsed_seconds": round(now - started, 3), "button": button})
                input_index += 1
                next_input += 2.0
            try:
                wait = min(remaining, args.timeout, 0.5 if args.auto_advance else args.timeout)
                stop = debugger.wait_event("cpu.stepping", wait)
            except (TimeoutError, websocket.WebSocketTimeoutException):
                continue
            stopped = True
            pc = stop.get("pc", 0)
            opcode = HANDLERS.get(pc)
            if opcode is None:
                raise RuntimeError(f"unexpected stop PC 0x{pc:08X}")

            regs = gpr_values(debugger.request("cpu.getAllRegs"))
            vm = regs["a1"]
            code_base = regs["a3"]
            saved_pc = debugger.request(
                "memory.read_u32", address=vm + VM_PC_OFFSET
            )["value"]
            logical_offset = (saved_pc - 2) & 0xFFFFFFFF
            head = read_bytes(debugger, code_base + saved_pc, 8)
            decoded = decode_message_head(opcode, head)
            reference = by_offset.get(logical_offset)
            events.append(
                {
                    "ticks": stop.get("ticks"),
                    "handler": f"0x{pc:08X}",
                    "opcode": f"42 {opcode:02X}",
                    "vm": f"0x{vm:08X}",
                    "code_base": f"0x{code_base:08X}",
                    "saved_pc": f"0x{saved_pc:08X}",
                    "logical_offset": f"0x{logical_offset:08X}",
                    "raw_head_hex": head.hex(),
                    **decoded,
                    "catalog_match": reference is not None,
                    "catalog_status": reference.status if reference else None,
                }
            )
            debugger.send("cpu.resume")
            debugger.wait_event("cpu.resume", 5.0)
            stopped = False

        unique_offsets = sorted({event["logical_offset"] for event in events})
        result = {
            "schema_version": 1,
            "tool": "ppsspp_nsf_trace.py",
            "ppsspp": version,
            "game": game,
            "duration_seconds": args.duration,
            "max_events": args.max_events,
            "handlers": {f"0x{key:08X}": f"42 {value:02X}" for key, value in HANDLERS.items()},
            "event_count": len(events),
            "unique_logical_offsets": unique_offsets,
            "automated_inputs": inputs,
            "events": events,
            "interpretation": (
                "Positive hits prove execution only for the captured run; absent offsets are not proof of dead code."
            ),
        }
        rendered = json.dumps(result, ensure_ascii=False, indent=2)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(rendered)
        return 0
    finally:
        for address in added:
            try:
                debugger.request("cpu.breakpoint.remove", address=address)
            except Exception as exc:
                print(f"warning: could not remove breakpoint 0x{address:08X}: {exc}", file=sys.stderr)
        if stopped:
            try:
                debugger.send("cpu.resume")
                debugger.wait_event("cpu.resume", 5.0)
            except Exception as exc:
                print(f"warning: could not resume CPU: {exc}", file=sys.stderr)
        debugger.close()


if __name__ == "__main__":
    raise SystemExit(main())
