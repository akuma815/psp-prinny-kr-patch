#!/usr/bin/env python3
"""Verify every declared BOOT UI translation against a built executable."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def mapping_from_rows(rows: list[dict[str, object]]) -> dict[str, bytes]:
    return {
        chr(int(str(row["codepoint"])[2:], 16)): bytes.fromhex(str(row["cp932_hex"]))
        for row in rows
    }


def encode_text(text: str, mapping: dict[str, bytes]) -> bytes:
    output = bytearray()
    for character in text:
        if character in mapping:
            output.extend(mapping[character])
        else:
            output.extend(character.encode("cp932", errors="strict"))
    return bytes(output)


def slot_size(source_size: int) -> int:
    return ((source_size + 1 + 3) // 4) * 4


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--boot", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    boot = args.boot.read_bytes()
    artifact = load_json(args.artifact)
    mapping_artifact = load_json(args.mapping)
    mapping = mapping_from_rows(list(mapping_artifact["entries"]))
    failures: list[dict[str, object]] = []
    source_payloads_remaining: list[str] = []

    for entry in artifact["entries"]:
        offset = int(str(entry["offset"]), 0)
        source = str(entry["source"]).encode("cp932")
        expected = encode_text(str(entry["translation"]), mapping)
        capacity = slot_size(len(source))
        actual = boot[offset:offset + capacity]
        expected_slot = expected + bytes(capacity - len(expected))
        if actual != expected_slot:
            failures.append({
                "offset": entry["offset"],
                "expected_hex": expected_slot.hex().upper(),
                "actual_hex": actual.hex().upper(),
            })
        if source and source in boot:
            source_payloads_remaining.append(str(entry["offset"]))

    report = {
        "status": "PASS" if not failures else "FAIL",
        "boot": str(args.boot),
        "boot_size": len(boot),
        "boot_sha256": hashlib.sha256(boot).hexdigest(),
        "declared_slots": len(artifact["entries"]),
        "verified_slots": len(artifact["entries"]) - len(failures),
        "failed_slots": failures,
        "declared_source_payloads_remaining_anywhere": source_payloads_remaining,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
