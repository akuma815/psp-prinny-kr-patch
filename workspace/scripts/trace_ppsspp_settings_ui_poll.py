#!/usr/bin/env python3
"""Deterministically trace the four settings descriptions by polling CPU state."""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path
from typing import Any

from ppsspp_basetalk_probe import Debugger
from ppsspp_nsf_trace import gpr_values


SETTER = 0x08896898
RENDERER = 0x08899698
GLYPH = 0x088999E0
EXIT = 0x08899B60
PAGE = 0x08A541D4
COUNT = 0x08A5421C
POINTERS = {
    0x088F15D0: "SE",
    0x088F15FC: "BGM",
    0x088F162C: "VOICE",
    0x088F1660: "CAMERA",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uri", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--selections", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=10.0)
    return parser.parse_args()


def gprs(debugger: Debugger, timeout: float) -> dict[str, int]:
    debugger.ws.settimeout(timeout)
    return gpr_values(debugger.request("cpu.getAllRegs"))


def request(
    debugger: Debugger, timeout: float, event: str, **params: Any
) -> dict[str, Any]:
    debugger.ws.settimeout(timeout)
    return debugger.request(event, **params)


def read_bytes(
    debugger: Debugger, timeout: float, address: int, size: int
) -> bytes:
    response = request(debugger, timeout, "memory.read", address=address, size=size)
    return base64.b64decode(response["base64"])


def read_string(
    debugger: Debugger, timeout: float, address: int, limit: int = 256
) -> bytes:
    return read_bytes(debugger, timeout, address, limit).split(b"\0", 1)[0]


def read_u32(debugger: Debugger, timeout: float, address: int) -> int:
    return request(debugger, timeout, "memory.read_u32", address=address)["value"]


def record_string(data: bytes) -> dict[str, Any]:
    result: dict[str, Any] = {"length": len(data), "hex": data.hex()}
    try:
        result["cp932"] = data.decode("cp932")
    except UnicodeDecodeError:
        result["cp932"] = None
    return result


def poll_stop(
    debugger: Debugger,
    timeout: float,
    expected: set[int],
    *,
    deadline_seconds: float = 10.0,
) -> tuple[dict[str, Any], list[int]]:
    deadline = time.monotonic() + deadline_seconds
    ignored: list[int] = []
    while time.monotonic() < deadline:
        status = request(debugger, timeout, "cpu.status")
        if status["stepping"]:
            pc = status["pc"]
            if pc in expected:
                return status, ignored
            ignored.append(pc)
            debugger.send("cpu.resume")
        time.sleep(0.01)
    wanted = ", ".join(f"0x{address:08X}" for address in sorted(expected))
    raise TimeoutError(f"CPU did not stop at any of: {wanted}")


def wait_stop_event(
    debugger: Debugger,
    timeout: float,
    expected: set[int],
    *,
    resume_first: bool,
    deadline_seconds: float = 10.0,
) -> tuple[dict[str, Any], list[int]]:
    # A stepping notification for the stop we are currently servicing may
    # already be queued behind a synchronous response.  It must not be mistaken
    # for the next stop.
    debugger.pending = [
        message
        for message in debugger.pending
        if message.get("event") != "cpu.stepping"
    ]
    if resume_first:
        debugger.send("cpu.resume")

    deadline = time.monotonic() + deadline_seconds
    ignored: list[int] = []
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        stop = debugger.wait_event("cpu.stepping", remaining)
        pc = stop["pc"]
        if pc in expected:
            return stop, ignored
        ignored.append(pc)
        debugger.send("cpu.resume")

    wanted = ", ".join(f"0x{address:08X}" for address in sorted(expected))
    raise TimeoutError(f"CPU did not signal a stop at any of: {wanted}")


def resume_and_reconnect(
    debugger: Debugger,
    uri: str,
    timeout: float,
    *,
    client_name: str,
) -> Debugger:
    # PPSSPP can stop at the next breakpoint before answering a cpu.status
    # request queued on the same WebSocket.  A fresh debugger connection can
    # inspect that already-stopped state reliably, while breakpoints remain
    # owned by the PPSSPP debugger core.
    debugger.send("cpu.resume")
    debugger.close()
    time.sleep(0.03)
    replacement = Debugger(uri, timeout)
    request(
        replacement,
        timeout,
        "version",
        name=client_name,
        version="1.0.0",
    )
    return replacement


def add_breakpoint(
    debugger: Debugger,
    timeout: float,
    added: set[int],
    address: int,
    *,
    condition: str | None = None,
) -> None:
    if address in added:
        return
    params: dict[str, Any] = {
        "address": address,
        "enabled": True,
        "log": False,
    }
    if condition is not None:
        params["condition"] = condition
    request(debugger, timeout, "cpu.breakpoint.add", **params)
    added.add(address)


def remove_breakpoint(
    debugger: Debugger, timeout: float, added: set[int], address: int
) -> None:
    if address not in added:
        return
    request(debugger, timeout, "cpu.breakpoint.remove", address=address)
    added.discard(address)


def write_report(
    path: Path,
    version: dict[str, Any],
    game: dict[str, Any],
    selections: list[dict[str, Any]],
    *,
    complete: bool,
) -> None:
    report = {
        "schema_version": 1,
        "tool": "trace_ppsspp_settings_ui_poll.py",
        "ppsspp": version,
        "game": game,
        "complete": complete,
        "selection_count": len(selections),
        "selections": selections,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    debugger = Debugger(args.uri, args.timeout)
    added: set[int] = set()
    results: list[dict[str, Any]] = []
    version: dict[str, Any] = {}
    game: dict[str, Any] = {}
    condition = " || ".join(f"a1==0x{p:08x}" for p in POINTERS)
    next_setter_status: dict[str, Any] | None = None

    try:
        version = request(
            debugger,
            args.timeout,
            "version",
            name="prinny-settings-ui-poll-trace",
            version="1.0.0",
        )
        game = request(debugger, args.timeout, "game.status")
        add_breakpoint(
            debugger, args.timeout, added, SETTER, condition=condition
        )
        initial_status = request(debugger, args.timeout, "cpu.status")
        if not initial_status["stepping"]:
            request(
                debugger,
                args.timeout,
                "input.buttons.send",
                buttons={"down": True},
            )
            time.sleep(0.05)
            request(
                debugger,
                args.timeout,
                "input.buttons.send",
                buttons={"down": False},
            )
            debugger.close()
            time.sleep(0.05)
            debugger = Debugger(args.uri, args.timeout)
            request(
                debugger,
                args.timeout,
                "version",
                name="prinny-settings-ui-poll-trace-initial-setter",
                version="1.0.0",
            )

        for index in range(args.selections):
            if next_setter_status is None:
                status, ignored = poll_stop(
                    debugger, args.timeout, {SETTER}, deadline_seconds=15.0
                )
            else:
                status = next_setter_status
                next_setter_status = None
                ignored = []
            regs = gprs(debugger, args.timeout)
            source_pointer = regs["a1"]
            destination_pointer = regs["a0"] + 0x0C
            source = read_string(
                debugger, args.timeout, source_pointer
            )
            before = read_string(
                debugger, args.timeout, destination_pointer
            )
            item: dict[str, Any] = {
                "index": index,
                "label": POINTERS[source_pointer],
                "source_pointer": f"0x{source_pointer:08X}",
                "destination_pointer": f"0x{destination_pointer:08X}",
                "source": record_string(source),
                "destination_before": record_string(before),
                "setter_pc": f"0x{status['pc']:08X}",
                "return_pc": f"0x{regs['ra']:08X}",
                "ignored_stops_before_setter": [
                    f"0x{pc:08X}" for pc in ignored
                ],
            }
            print(
                f"SET {index}: {item['label']} "
                f"src={item['source_pointer']} return={item['return_pc']}",
                flush=True,
            )

            return_pc = regs["ra"]
            add_breakpoint(
                debugger, args.timeout, added, return_pc
            )
            debugger = resume_and_reconnect(
                debugger,
                args.uri,
                args.timeout,
                client_name="prinny-settings-ui-poll-trace-return",
            )
            poll_stop(debugger, args.timeout, {return_pc})
            copied = read_string(
                debugger, args.timeout, destination_pointer
            )
            item["destination_after"] = record_string(copied)
            item["copy_matches_source"] = copied == source
            add_breakpoint(
                debugger,
                args.timeout,
                added,
                RENDERER,
                condition=f"t0==0x{destination_pointer:08x}",
            )
            debugger = resume_and_reconnect(
                debugger,
                args.uri,
                args.timeout,
                client_name="prinny-settings-ui-poll-trace-renderer",
            )
            poll_stop(debugger, args.timeout, {RENDERER})
            render_regs = gprs(debugger, args.timeout)
            renderer_input = read_string(
                debugger, args.timeout, render_regs["t0"]
            )
            item["renderer_input"] = record_string(renderer_input)
            item["renderer_matches_source"] = renderer_input == source
            item["page_at_entry"] = read_u32(
                debugger, args.timeout, PAGE
            )
            item["count_at_entry"] = read_u32(
                debugger, args.timeout, COUNT
            )
            add_breakpoint(debugger, args.timeout, added, GLYPH)
            add_breakpoint(debugger, args.timeout, added, EXIT)
            glyphs: list[dict[str, Any]] = []
            while True:
                debugger = resume_and_reconnect(
                    debugger,
                    args.uri,
                    args.timeout,
                    client_name="prinny-settings-ui-poll-trace-glyph",
                )
                glyph_status, _ = poll_stop(
                    debugger,
                    args.timeout,
                    {GLYPH, EXIT},
                    deadline_seconds=10.0,
                )
                if glyph_status["pc"] == EXIT:
                    break
                glyph_regs = gprs(debugger, args.timeout)
                glyphs.append(
                    {
                        "glyph_id": glyph_regs["a0"],
                        "glyph_id_hex": f"0x{glyph_regs['a0']:04X}",
                        "source_cursor": f"0x{glyph_regs['s3']:08X}",
                        "page": read_u32(
                            debugger, args.timeout, PAGE
                        ),
                        "count": read_u32(
                            debugger, args.timeout, COUNT
                        ),
                    }
                )
            item["glyphs"] = glyphs
            item["page_at_exit"] = read_u32(
                debugger, args.timeout, PAGE
            )
            item["count_at_exit"] = read_u32(
                debugger, args.timeout, COUNT
            )
            results.append(item)
            write_report(
                args.output, version, game, results, complete=False
            )
            print(
                f"DONE {index}: {item['label']} "
                f"copy={item['copy_matches_source']} "
                f"render={item['renderer_matches_source']} "
                f"glyphs={len(glyphs)}",
                flush=True,
            )

            # We are stopped at EXIT.  Remove every non-current trace
            # breakpoint before returning to the menu loop, then resume past
            # EXIT and remove it from a fresh connection.  Otherwise the
            # continuously redrawn description hits RENDERER again before the
            # synthetic d-pad input can be sampled.
            for address in sorted(added - {SETTER, EXIT}):
                remove_breakpoint(
                    debugger, args.timeout, added, address
                )
            debugger = resume_and_reconnect(
                debugger,
                args.uri,
                args.timeout,
                client_name="prinny-settings-ui-poll-trace-between-items",
            )
            remove_breakpoint(
                debugger, args.timeout, added, EXIT
            )

            if index + 1 < args.selections:
                time.sleep(0.05)
                request(
                    debugger,
                    args.timeout,
                    "input.buttons.send",
                    buttons={"down": True},
                )
                time.sleep(0.05)
                request(
                    debugger,
                    args.timeout,
                    "input.buttons.send",
                    buttons={"down": False},
                )
                debugger.close()
                time.sleep(0.05)
                debugger = Debugger(args.uri, args.timeout)
                request(
                    debugger,
                    args.timeout,
                    "version",
                    name="prinny-settings-ui-poll-trace-next-setter",
                    version="1.0.0",
                )
                next_setter_status, _ = poll_stop(
                    debugger, args.timeout, {SETTER}, deadline_seconds=15.0
                )

        write_report(args.output, version, game, results, complete=True)
        print(args.output.read_text(encoding="utf-8"))
        return 0
    finally:
        try:
            debugger.send("cpu.resume")
            debugger.close()
            time.sleep(0.05)
            debugger = Debugger(args.uri, args.timeout)
            request(
                debugger,
                args.timeout,
                "version",
                name="prinny-settings-ui-poll-trace-cleanup",
                version="1.0.0",
            )
            for address in sorted(added):
                try:
                    remove_breakpoint(
                        debugger, args.timeout, added, address
                    )
                except Exception as exc:
                    print(
                        f"warning: remove 0x{address:08X}: {exc}",
                        file=sys.stderr,
                    )
        except Exception as exc:
            print(f"warning: resume cleanup: {exc}", file=sys.stderr)
        try:
            debugger.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
