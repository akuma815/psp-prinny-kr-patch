#!/usr/bin/env python3
"""Compress the confirmed NIS LZS variant and verify a self-roundtrip."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import deque
from pathlib import Path

from decompress_nis_lzs import HEADER, decompress


MIN_DISTANCE = 4
MAX_DISTANCE = 254
MAX_LENGTH = 254
MIN_MATCH = 4


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _distance_code(distance: int, flag: int) -> int:
    if not 1 <= distance <= MAX_DISTANCE:
        raise ValueError(f"distance is outside 1..{MAX_DISTANCE}: {distance}")
    code = distance + 1 if distance >= flag else distance
    if code == flag or code > 0xFF:
        raise ValueError("distance cannot be represented with the selected flag")
    return code


def compress_payload(data: bytes, flag: int) -> tuple[bytes, dict[str, int]]:
    if not 1 <= flag <= 0xFF:
        raise ValueError("flag must fit in one nonzero byte")

    output = bytearray()
    positions: dict[bytes, deque[int]] = {}
    literals = 0
    escaped_literals = 0
    matches = 0
    matched_bytes = 0
    maximum_distance = 0
    maximum_length = 0

    def advance(position: int) -> None:
        expired = position - MAX_DISTANCE - 1
        if expired >= 0 and expired + 3 <= len(data):
            expired_key = data[expired:expired + 3]
            queue = positions.get(expired_key)
            if queue and queue[0] == expired:
                queue.popleft()
                if not queue:
                    del positions[expired_key]
        if position + 3 <= len(data):
            positions.setdefault(data[position:position + 3], deque()).append(position)

    cursor = 0
    while cursor < len(data):
        best_distance = 0
        best_length = 0
        if cursor + MIN_MATCH <= len(data):
            candidates = positions.get(data[cursor:cursor + 3], ())
            global_limit = min(MAX_LENGTH, len(data) - cursor)
            for candidate in reversed(candidates):
                distance = cursor - candidate
                if not MIN_DISTANCE <= distance <= MAX_DISTANCE:
                    continue
                # The observed Prinny stream and the public reference encoder
                # only copy from bytes completed before the token starts.
                limit = min(MAX_LENGTH, len(data) - cursor, distance)
                length = 3
                while length < limit and data[cursor + length] == data[cursor + length - distance]:
                    length += 1
                if length > best_length:
                    best_distance = distance
                    best_length = length
                    if length == global_limit:
                        break

        if best_length >= MIN_MATCH:
            output.extend((flag, _distance_code(best_distance, flag), best_length))
            matches += 1
            matched_bytes += best_length
            maximum_distance = max(maximum_distance, best_distance)
            maximum_length = max(maximum_length, best_length)
            for position in range(cursor, cursor + best_length):
                advance(position)
            cursor += best_length
            continue

        value = data[cursor]
        output.append(value)
        literals += 1
        if value == flag:
            output.append(flag)
            escaped_literals += 1
        advance(cursor)
        cursor += 1

    return bytes(output), {
        "literal_tokens": literals,
        "escaped_flag_literals": escaped_literals,
        "match_tokens": matches,
        "matched_input_bytes": matched_bytes,
        "maximum_distance": maximum_distance,
        "maximum_length": maximum_length,
        "overlapping_matches": 0,
    }


def compress(
    data: bytes, extension: str = "dat", flag: int = 0xD5
) -> tuple[bytes, dict[str, int]]:
    try:
        extension_raw = extension.encode("ascii")
    except UnicodeEncodeError as error:
        raise ValueError("extension must be ASCII") from error
    if not extension_raw or len(extension_raw) > 3:
        raise ValueError("extension must contain 1..3 ASCII bytes")
    payload, stats = compress_payload(data, flag)
    stored_size = 12 + len(payload)
    header = HEADER.pack(extension_raw.ljust(4, b"\0"), len(data), stored_size, flag)
    result = header + payload
    restored, restored_extension = decompress(result)
    if restored != data or restored_extension != extension:
        raise ValueError("compressor self-roundtrip failed")
    return result, stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--extension", default="dat")
    parser.add_argument("--flag", type=lambda value: int(value, 0), default=0xD5)
    parser.add_argument("--report", type=Path)
    parser.add_argument(
        "--reference",
        type=Path,
        help="optional compressed stream to compare byte-for-byte",
    )
    args = parser.parse_args()

    source = args.input.read_bytes()
    result, stats = compress(source, args.extension, args.flag)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(result)
    reference = None
    if args.reference:
        reference_data = args.reference.read_bytes()
        reference = {
            "path": args.reference.as_posix(),
            "size": len(reference_data),
            "sha256": sha256(reference_data),
            "byte_identical": reference_data == result,
        }
    not_proved = [
        "game-loader compatibility",
        "SYSTEM.DAT and ISO container compatibility",
    ]
    if reference is None:
        not_proved.insert(0, "byte-identical reproduction of an original compressed stream")
    report = {
        "schema_version": 1,
        "status": "PASS: compressor self-roundtrip",
        "input": {
            "path": args.input.as_posix(),
            "size": len(source),
            "sha256": sha256(source),
        },
        "output": {
            "path": args.output.as_posix(),
            "size": len(result),
            "sha256": sha256(result),
            "extension": args.extension,
            "flag": f"0x{args.flag:02X}",
        },
        "tokens": stats,
        "reference": reference,
        "not_proved": not_proved,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
