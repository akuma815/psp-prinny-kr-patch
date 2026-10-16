#!/usr/bin/env python3
"""Decompress the NIS LZS variant used by start.lzs.

The input is never modified. The output is written only after the stream and
declared output size have been validated.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path


HEADER = struct.Struct("<4sIII")


def decompress(data: bytes) -> tuple[bytes, str]:
    if len(data) < HEADER.size:
        raise ValueError("input is shorter than the 16-byte LZS header")

    extension_raw, output_size, stored_size, flag_u32 = HEADER.unpack_from(data)
    if flag_u32 > 0xFF:
        raise ValueError(f"flag does not fit in one byte: 0x{flag_u32:08X}")
    if stored_size + 4 != len(data):
        raise ValueError(
            f"stored-size mismatch: header expects {stored_size + 4} bytes, "
            f"file has {len(data)} bytes"
        )

    flag = flag_u32
    source = HEADER.size
    source_end = len(data)
    output = bytearray()

    while source < source_end:
        value = data[source]
        if value != flag:
            output.append(value)
            source += 1
            continue

        if source + 1 >= source_end:
            raise ValueError("truncated escape at end of compressed stream")

        distance_code = data[source + 1]
        if distance_code == flag:
            output.append(flag)
            source += 2
            continue

        if source + 2 >= source_end:
            raise ValueError("truncated back-reference at end of compressed stream")

        distance = distance_code - 1 if distance_code > flag else distance_code
        length = data[source + 2]
        if distance == 0 or distance > len(output):
            raise ValueError(
                f"invalid back-reference at 0x{source:X}: "
                f"distance={distance}, output={len(output)}"
            )
        if len(output) + length > output_size:
            raise ValueError(
                f"back-reference at 0x{source:X} exceeds declared output size"
            )

        for _ in range(length):
            output.append(output[-distance])
        source += 3

    if len(output) != output_size:
        raise ValueError(
            f"decompressed-size mismatch: expected {output_size}, got {len(output)}"
        )

    extension = extension_raw.rstrip(b"\0").decode("ascii", errors="strict")
    return bytes(output), extension


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    result, extension = decompress(args.input.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(result)
    print(
        f"OK: {args.input} -> {args.output} "
        f"({len(result)} bytes, extension={extension!r})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
