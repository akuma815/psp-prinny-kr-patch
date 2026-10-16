#!/usr/bin/env python3
"""Trace settings-menu description selection, copying, and glyph resolution."""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path
from typing import Any

import websocket

from ppsspp_basetalk_probe import Debugger
from ppsspp_nsf_trace import gpr_values


STRING_SETTER = 0x08896898
RENDERER = 0x08899698
GLYPH_READY = 0x088999E0
RENDERER_EXIT = 0x08899B60
RETURN_PCS = {0x088ABAF0, 0x088ABB04, 0x088ABB18, 0x088ABB2C}
GLOBAL_PAGE = 0x08A541D4
GLOBAL_COUNT = 0x08A5421C

DESCRIPTION_POINTERS = {
    0x088F15D0: "SE",
    0x088F15FC: "BGM",
    0x088F162C: "VOICE",
    0x088F1660: "CAMERA",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uri", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration", type=float, default=120.0)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--max-selections", type=int, default=12)
    parser.add_argument(
        "--auto-cycle",
        action="store_true",
        help="Press d-pad down after arming and after each captured selection.",
    )
    return parser.parse_args()


def read_bytes(debugger: Debugger, address: int, size: int) -> bytes:
    response = debugger.request("memory.read", address=address, size=size)
    return base64.b64decode(response["base64"])


def read_c_string(debugger: Debugger, address: int, limit: int = 256) -> bytes:
    data = read_bytes(debugger, address, limit)
    return data.split(b"\0", 1)[0]


def u32(debugger: Debugger, address: int) -> int:
    return debugger.request("memory.read_u32", address=address)["value"]


def hex_address(value: int) -> str:
    return f"0x{value:08X}"


def string_record(data: bytes) -> dict[str, Any]:
    record: dict[str, Any] = {"length": len(data), "hex": data.hex()}
    try:
        record["cp932"] = data.decode("cp932")
    except UnicodeDecodeError:
        record["cp932"] = None
    return record


def set_breakpoint(
    debugger: Debugger,
    address: int,
    added: set[int],
    *,
    enabled: bool = True,
    condition: str | None = None,
) -> None:
    params: dict[str, Any] = {
        "address": address,
        "enabled": enabled,
        "log": False,
    }
    if condition is not None:
        params["condition"] = condition
    debugger.request("cpu.breakpoint.add", **params)
    added.add(address)


def update_breakpoint(
    debugger: Debugger,
    address: int,
    *,
    enabled: bool,
    condition: str | None = None,
) -> None:
    params: dict[str, Any] = {"address": address, "enabled": enabled}
    if condition is not None:
        params["condition"] = condition
    debugger.request("cpu.breakpoint.update", **params)


def resume(debugger: Debugger) -> None:
    # Do not wait for cpu.resume or poll until stepping becomes false here.
    # The target can run from the setter to the return breakpoint before the
    # broadcaster observes an intermediate running state.  In that case the
    # next cpu.stepping event is the data we need, not a failed resume.
    debugger.send("cpu.resume")


def save_result(
    path: Path,
    *,
    version: dict[str, Any],
    game: dict[str, Any],
    started: float,
    selections: list[dict[str, Any]],
    complete: bool,
) -> None:
    result = {
        "schema_version": 1,
        "tool": "trace_ppsspp_settings_ui.py",
        "ppsspp": version,
        "game": game,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "selection_count": len(selections),
        "complete": complete,
        "selections": selections,
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    debugger = Debugger(args.uri, args.timeout)
    added: set[int] = set()
    stopped = False
    pending: dict[str, Any] | None = None
    active_render: dict[str, Any] | None = None
    selections: list[dict[str, Any]] = []
    ignored_stops: list[dict[str, Any]] = []
    version: dict[str, Any] = {}
    game: dict[str, Any] = {}
    started = time.monotonic()

    pointer_condition = " || ".join(
        f"a1==0x{pointer:08x}" for pointer in DESCRIPTION_POINTERS
    )

    try:
        version = debugger.request(
            "version", name="prinny-settings-ui-trace", version="1.0.0"
        )
        game = debugger.request("game.status")
        set_breakpoint(
            debugger,
            STRING_SETTER,
            added,
            condition=pointer_condition,
        )
        set_breakpoint(debugger, RENDERER, added, enabled=False)
        set_breakpoint(debugger, GLYPH_READY, added, enabled=False)
        set_breakpoint(debugger, RENDERER_EXIT, added, enabled=False)

        print(
            "TRACE_ARMED: open settings and move through SE/BGM/VOICE/CAMERA. "
            f"Capturing up to {args.max_selections} selections.",
            flush=True,
        )
        if args.auto_cycle:
            debugger.send("input.buttons.press", button="down", duration=2)
        next_auto_input = time.monotonic() + 1.5
        deadline = started + args.duration
        while len(selections) < args.max_selections:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            now = time.monotonic()
            if args.auto_cycle and now >= next_auto_input:
                debugger.send("input.buttons.press", button="down", duration=2)
                next_auto_input = now + 1.5
            try:
                stop = debugger.wait_event(
                    "cpu.stepping",
                    min(remaining, 0.5 if args.auto_cycle else args.timeout),
                )
            except (TimeoutError, websocket.WebSocketTimeoutException):
                continue

            stopped = True
            pc = stop.get("pc", 0)
            # wait_event() narrows the socket timeout to its remaining deadline.
            # Do not leak that nearly-expired timeout into register/memory queries.
            debugger.ws.settimeout(args.timeout)
            regs = gpr_values(debugger.request("cpu.getAllRegs"))

            if pc == STRING_SETTER:
                source = regs["a1"]
                destination = regs["a0"] + 0x0C
                source_data = read_c_string(debugger, source)
                before_data = read_c_string(debugger, destination)
                pending = {
                    "index": len(selections),
                    "label": DESCRIPTION_POINTERS[source],
                    "source_pointer": hex_address(source),
                    "destination_pointer": hex_address(destination),
                    "source": string_record(source_data),
                    "destination_before": string_record(before_data),
                    "setter_ticks": stop.get("ticks"),
                    "return_pc_dynamic": hex_address(regs["ra"]),
                }
                # Adding this while the CPU is stopped reliably invalidates the
                # active JIT block.  Pre-arming these return PCs can be missed.
                set_breakpoint(debugger, regs["ra"], added)
                print(
                    f"SET {pending['index']}: {pending['label']} "
                    f"src={pending['source_pointer']} dst={pending['destination_pointer']}",
                    flush=True,
                )

            elif (
                pending is not None
                and pc == int(pending["return_pc_dynamic"], 16)
            ):
                destination = int(pending["destination_pointer"], 16)
                copied_data = read_c_string(debugger, destination)
                pending["destination_after"] = string_record(copied_data)
                pending["copy_matches_source"] = (
                    copied_data.hex() == pending["source"]["hex"]
                )
                pending["return_pc"] = hex_address(pc)
                debugger.request("cpu.breakpoint.remove", address=pc)
                added.discard(pc)
                condition = f"t0==0x{destination:08x}"
                update_breakpoint(
                    debugger, RENDERER, enabled=True, condition=condition
                )

            elif pc == RENDERER and pending is not None:
                destination = regs["t0"]
                render_data = read_c_string(debugger, destination)
                pending["renderer_input"] = string_record(render_data)
                pending["renderer_matches_source"] = (
                    render_data.hex() == pending["source"]["hex"]
                )
                pending["page_at_entry"] = u32(debugger, GLOBAL_PAGE)
                pending["count_at_entry"] = u32(debugger, GLOBAL_COUNT)
                pending["glyphs"] = []
                active_render = pending
                update_breakpoint(debugger, RENDERER, enabled=False)
                update_breakpoint(debugger, GLYPH_READY, enabled=True)
                update_breakpoint(debugger, RENDERER_EXIT, enabled=True)

            elif pc == GLYPH_READY and active_render is not None:
                active_render["glyphs"].append(
                    {
                        "glyph_id": regs["a0"],
                        "glyph_id_hex": f"0x{regs['a0']:04X}",
                        "source_cursor": hex_address(regs["s3"]),
                        "page": u32(debugger, GLOBAL_PAGE),
                        "count": u32(debugger, GLOBAL_COUNT),
                    }
                )

            elif pc == RENDERER_EXIT and active_render is not None:
                active_render["page_at_exit"] = u32(debugger, GLOBAL_PAGE)
                active_render["count_at_exit"] = u32(debugger, GLOBAL_COUNT)
                selections.append(active_render)
                print(
                    f"DONE {active_render['index']}: {active_render['label']} "
                    f"copy={active_render['copy_matches_source']} "
                    f"render={active_render['renderer_matches_source']} "
                    f"glyphs={len(active_render['glyphs'])}",
                    flush=True,
                )
                save_result(
                    args.output,
                    version=version,
                    game=game,
                    started=started,
                    selections=selections,
                    complete=False,
                )
                active_render = None
                pending = None
                update_breakpoint(debugger, GLYPH_READY, enabled=False)
                update_breakpoint(debugger, RENDERER_EXIT, enabled=False)

            else:
                ignored_stops.append(
                    {
                        "pc": hex_address(pc),
                        "ticks": stop.get("ticks"),
                    }
                )
                print(f"IGNORED_STOP: 0x{pc:08X}", flush=True)
                debugger.send("cpu.resume")
                stopped = False
                continue

            resume(debugger)
            stopped = False
            if args.auto_cycle and selections and active_render is None and pending is None:
                debugger.send("input.buttons.press", button="down", duration=2)
                next_auto_input = time.monotonic() + 1.5
    finally:
        for address in sorted(added):
            try:
                debugger.ws.settimeout(args.timeout)
                debugger.request("cpu.breakpoint.remove", address=address)
            except Exception as exc:
                print(
                    f"warning: could not remove breakpoint 0x{address:08X}: {exc}",
                    file=sys.stderr,
                )
        if stopped:
            try:
                resume(debugger)
            except Exception as exc:
                print(f"warning: could not resume CPU: {exc}", file=sys.stderr)
        debugger.close()

    save_result(
        args.output,
        version=version,
        game=game,
        started=started,
        selections=selections,
        complete=True,
    )
    rendered = args.output.read_text(encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
