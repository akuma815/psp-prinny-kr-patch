#!/usr/bin/env python3
"""Trace one Demo00 message-ID candidate at the shared NSF message handlers."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import websocket
from ppsspp_basetalk_probe import Debugger
from ppsspp_nsf_trace import (
    HANDLERS,
    VM_PC_OFFSET,
    decode_message_head,
    gpr_values,
    read_bytes,
)


DEFAULT_TARGET_ID = 0x00E6
DEFAULT_EXPECTED_OFFSET = 0x0001851C


def parse_int(value: str) -> int:
    return int(value, 0)


def classify_hits(
    hits: list[dict[str, Any]], target_id: int, expected_offset: int | None
) -> dict[str, Any]:
    """Classify positive evidence without treating absence as dead-code proof."""
    exact = [hit for hit in hits if hit["logical_offset_value"] == expected_offset]
    if exact:
        return {
            "status": "POSITIVE_EXACT",
            "target_id": f"0x{target_id:04X}",
            "exact_hit_count": len(exact),
            "conclusion": (
                "The target ID was decoded at the expected NSF logical offset during this run."
            ),
        }
    if hits:
        return {
            "status": "POSITIVE_ID_OTHER_OFFSET",
            "target_id": f"0x{target_id:04X}",
            "exact_hit_count": 0,
            "conclusion": (
                "The target ID was decoded, but not at the expected static candidate offset."
            ),
        }
    return {
        "status": "INCONCLUSIVE_NO_HIT",
        "target_id": f"0x{target_id:04X}",
        "exact_hit_count": 0,
        "conclusion": (
            "No target hit was observed in this bounded run; this is not evidence of dead code."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uri", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target-id", type=parse_int, default=DEFAULT_TARGET_ID)
    parser.add_argument(
        "--expected-offset", type=parse_int, default=DEFAULT_EXPECTED_OFFSET
    )
    parser.add_argument("--duration", type=float, default=120.0)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--max-handler-events", type=int, default=5000)
    parser.add_argument(
        "--reset", action="store_true", help="Reset the current game before tracing"
    )
    parser.add_argument(
        "--auto-advance",
        action="store_true",
        help="Press title/menu confirmation buttons periodically",
    )
    parser.add_argument(
        "--stop-on-exact-hit", action="store_true", help="Stop after the first exact hit"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    debugger = Debugger(args.uri, args.timeout)
    added: list[int] = []
    stopped = False
    hits: list[dict[str, Any]] = []
    observed: Counter[str] = Counter()
    inputs: list[dict[str, Any]] = []
    handler_events = 0
    started = time.monotonic()
    version: dict[str, Any] = {}
    game: dict[str, Any] = {}
    try:
        version = debugger.request(
            "version", name="prinny-demo00-target-trace", version="1.0.0"
        )
        game = debugger.request("game.status")
        for address in HANDLERS:
            debugger.request(
                "cpu.breakpoint.add", address=address, enabled=True, log=False
            )
            added.append(address)
        if args.reset:
            debugger.request("game.reset")

        started = time.monotonic()
        deadline = started + args.duration
        next_input = started + 3.0
        input_index = 0
        auto_buttons = ("start", "circle", "circle", "circle", "cross")
        while handler_events < args.max_handler_events:
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
            handler_events += 1
            message_id = decoded["message_id"]
            observed["dynamic" if message_id is None else f"0x{message_id & 0xFFFFFFFF:08X}"] += 1
            if message_id == args.target_id:
                instruction = read_bytes(debugger, code_base + logical_offset, 12)
                hits.append(
                    {
                        "ticks": stop.get("ticks"),
                        "elapsed_seconds": round(time.monotonic() - started, 3),
                        "handler": f"0x{pc:08X}",
                        "opcode": f"42 {opcode:02X}",
                        "vm": f"0x{vm:08X}",
                        "code_base": f"0x{code_base:08X}",
                        "saved_pc": f"0x{saved_pc:08X}",
                        "logical_offset": f"0x{logical_offset:08X}",
                        "logical_offset_value": logical_offset,
                        "instruction_hex": instruction.hex(),
                        **decoded,
                        "expected_offset_match": logical_offset == args.expected_offset,
                    }
                )
            debugger.send("cpu.resume")
            debugger.wait_event("cpu.resume", 5.0)
            stopped = False
            if hits and hits[-1]["expected_offset_match"] and args.stop_on_exact_hit:
                break
    finally:
        for address in added:
            try:
                debugger.request("cpu.breakpoint.remove", address=address)
            except Exception as exc:
                print(
                    f"warning: could not remove breakpoint 0x{address:08X}: {exc}",
                    file=sys.stderr,
                )
        if stopped:
            try:
                debugger.send("cpu.resume")
                debugger.wait_event("cpu.resume", 5.0)
            except Exception as exc:
                print(f"warning: could not resume CPU: {exc}", file=sys.stderr)
        debugger.close()

    interpretation = classify_hits(hits, args.target_id, args.expected_offset)
    result = {
        "schema_version": 1,
        "tool": "ppsspp_demo00_target_trace.py",
        "ppsspp": version,
        "game": game,
        "target_id": f"0x{args.target_id:04X}",
        "expected_logical_offset": f"0x{args.expected_offset:08X}",
        "duration_seconds": args.duration,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "reset": args.reset,
        "handler_event_count": handler_events,
        "observed_message_ids": dict(sorted(observed.items())),
        "target_hit_count": len(hits),
        "automated_inputs": inputs,
        "target_hits": hits,
        "interpretation": interpretation,
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
