#!/usr/bin/env python3
"""Export strict NUL-terminated CP932 strings from the Prinny executable.

This is a survey artifact, not automatic proof that every candidate is drawn
as UI text.  Stable byte offsets and slot capacities make selected candidates
safe to promote into the reviewed BOOT UI translation table.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from audit_cp932_allocation import candidate_runs


def export(source: Path) -> dict[str, object]:
    data = source.read_bytes()
    runs = candidate_runs(
        data,
        minimum_strong_japanese=1,
        minimum_strong_ratio=0.15,
        maximum_run_bytes=256,
        require_nul_boundaries=True,
        exclude_utf8_japanese=True,
    )
    entries = [
        {
            "offset": f"0x{int(run['offset']):06X}",
            "source_bytes": bytes(run["raw"]).hex().upper(),
            "source": str(run["text"]),
            "payload_bytes": int(run["length"]),
            "slot_size": ((int(run["length"]) + 1 + 3) // 4) * 4,
        }
        for run in runs
    ]
    return {
        "schema_version": 1,
        "source": str(source.resolve()),
        "candidate_count": len(entries),
        "policy": (
            "strict NUL-bounded CP932 runs; survey candidates only until a "
            "runtime screen or code consumer promotes an entry"
        ),
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = export(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"OK: {report['candidate_count']} candidates -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
