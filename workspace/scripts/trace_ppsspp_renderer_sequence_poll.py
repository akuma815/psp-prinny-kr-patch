#!/usr/bin/env python3
"""Trace consecutive common-text renderer calls and atlas counters in PPSSPP."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

from ppsspp_basetalk_probe import Debugger
from trace_ppsspp_settings_ui_poll import (
    COUNT,
    PAGE,
    RENDERER,
    add_breakpoint,
    gprs,
    poll_stop,
    read_string,
    read_u32,
    remove_breakpoint,
    request,
    resume_and_reconnect,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uri", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--hits", type=int, default=80)
    parser.add_argument("--timeout", type=float, default=10.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    debugger = Debugger(args.uri, args.timeout)
    added: set[int] = set()
    rows: list[dict[str, Any]] = []
    version: dict[str, Any] = {}
    game: dict[str, Any] = {}
    try:
        version = request(
            debugger,
            args.timeout,
            "version",
            name="prinny-renderer-sequence-poll-trace",
            version="1.0.0",
        )
        game = request(debugger, args.timeout, "game.status")
        add_breakpoint(debugger, args.timeout, added, RENDERER)

        for index in range(args.hits):
            status, ignored = poll_stop(
                debugger,
                args.timeout,
                {RENDERER},
                deadline_seconds=15.0,
            )
            regs = gprs(debugger, args.timeout)
            source = read_string(debugger, args.timeout, regs["t0"])
            count = read_u32(debugger, args.timeout, COUNT)
            page = read_u32(debugger, args.timeout, PAGE)
            row = {
                "index": index,
                "pc": f"0x{status['pc']:08X}",
                "return_pc": f"0x{regs['ra']:08X}",
                "source_pointer": f"0x{regs['t0']:08X}",
                "source_length": len(source),
                "source_sha256": hashlib.sha256(source).hexdigest(),
                "source_hex": source.hex(),
                "count_at_entry": count,
                "page_at_entry": f"0x{page:08X}",
                "ignored_stops": [f"0x{pc:08X}" for pc in ignored],
            }
            rows.append(row)
            print(
                f"{index:03d} count={count:3d} page=0x{page:08X} "
                f"t0=0x{regs['t0']:08X} len={len(source):3d} "
                f"ra=0x{regs['ra']:08X}",
                flush=True,
            )
            debugger = resume_and_reconnect(
                debugger,
                args.uri,
                args.timeout,
                client_name="prinny-renderer-sequence-poll-trace-next",
            )

        report = {
            "schema_version": 1,
            "tool": Path(__file__).name,
            "ppsspp": version,
            "game": game,
            "complete": True,
            "hit_count": len(rows),
            "calls": rows,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
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
                name="prinny-renderer-sequence-poll-trace-cleanup",
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
