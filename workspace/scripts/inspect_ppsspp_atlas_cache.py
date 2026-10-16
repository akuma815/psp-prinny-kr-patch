#!/usr/bin/env python3
"""Read Prinny's atlas-cache diagnostic state from a running PPSSPP process."""

from __future__ import annotations

import argparse
import ctypes
import json
import struct
from ctypes import wintypes
from pathlib import Path


ELF_BASE = 0x08804000
ELF_FILE_OFFSET = 0x54
CODE_CAVE_VA = 0x088D0DCC
PAGE_POINTER_VA = 0x08A541D4
PAGE_POINTERS_VA = 0x08A54214
GLOBAL_COUNT_VA = 0x08A5421C
PAGE0_COUNT_VA = 0x088D10CC
PAGE1_COUNT_VA = 0x088D10D0
PAGE0_CACHE_VA = 0x088D10D4
PAGE1_CACHE_VA = 0x088D1284
ATLAS_CAPACITY = 216

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
PAGE_NOACCESS = 0x01
PAGE_GUARD = 0x100


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wintypes.DWORD),
        ("PartitionId", wintypes.WORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
    ]


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.VirtualQueryEx.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.POINTER(MEMORY_BASIC_INFORMATION),
    ctypes.c_size_t,
]
kernel32.VirtualQueryEx.restype = ctypes.c_size_t
kernel32.ReadProcessMemory.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
kernel32.ReadProcessMemory.restype = wintypes.BOOL


def read_memory(handle: int, address: int, size: int) -> bytes | None:
    buffer = ctypes.create_string_buffer(size)
    read = ctypes.c_size_t()
    if not kernel32.ReadProcessMemory(
        handle, ctypes.c_void_p(address), buffer, size, ctypes.byref(read)
    ):
        return None
    return buffer.raw[: read.value]


def find_needle(handle: int, needle: bytes) -> int:
    address = 0
    mbi = MEMORY_BASIC_INFORMATION()
    chunk_size = 64 * 1024
    overlap = len(needle) - 1
    while kernel32.VirtualQueryEx(
        handle, ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi)
    ):
        base = int(mbi.BaseAddress or 0)
        size = int(mbi.RegionSize)
        readable = (
            mbi.State == MEM_COMMIT
            and not (mbi.Protect & PAGE_NOACCESS)
            and not (mbi.Protect & PAGE_GUARD)
        )
        if readable:
            offset = 0
            tail = b""
            while offset < size:
                amount = min(chunk_size, size - offset)
                data = read_memory(handle, base + offset, amount)
                if data is None:
                    # A large committed PPSSPP reservation can contain
                    # individually unreadable subpages.  Keep scanning later
                    # chunks instead of abandoning the entire region.
                    tail = b""
                    offset += amount
                    continue
                combined = tail + data
                hit = combined.find(needle)
                if hit >= 0:
                    return base + offset - len(tail) + hit
                tail = combined[-overlap:] if overlap else b""
                offset += amount
        next_address = base + size
        if next_address <= address:
            break
        address = next_address
    raise RuntimeError("patched BOOT marker was not found in PPSSPP memory")


def read_exact(handle: int, base: int, va: int, size: int) -> bytes:
    data = read_memory(handle, base + va, size)
    if data is None or len(data) != size:
        raise RuntimeError(f"could not read PSP address 0x{va:08X}")
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pid", type=int)
    parser.add_argument("boot", type=Path)
    parser.add_argument(
        "--regions",
        action="store_true",
        help="list large committed host regions before locating PSP RAM",
    )
    args = parser.parse_args()

    boot = args.boot.read_bytes()
    marker_offset = ELF_FILE_OFFSET + CODE_CAVE_VA - ELF_BASE
    marker = boot[marker_offset : marker_offset + 64]
    if len(marker) != 64 or not any(marker):
        raise SystemExit("BOOT marker is absent or invalid")

    handle = kernel32.OpenProcess(
        PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, args.pid
    )
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if args.regions:
            address = 0
            mbi = MEMORY_BASIC_INFORMATION()
            while kernel32.VirtualQueryEx(
                handle,
                ctypes.c_void_p(address),
                ctypes.byref(mbi),
                ctypes.sizeof(mbi),
            ):
                base = int(mbi.BaseAddress or 0)
                size = int(mbi.RegionSize)
                if mbi.State == MEM_COMMIT and size >= 0x01000000:
                    print(
                        json.dumps(
                            {
                                "host_base": f"0x{base:016X}",
                                "size": f"0x{size:X}",
                                "protect": f"0x{mbi.Protect:X}",
                                "type": f"0x{mbi.Type:X}",
                            }
                        )
                    )
                next_address = base + size
                if next_address <= address:
                    break
                address = next_address
        marker_host = find_needle(handle, marker)
        psp_host_base = marker_host - CODE_CAVE_VA
        page_pointer, page0_pointer, page1_pointer, global_count = struct.unpack(
            "<4I",
            read_exact(handle, psp_host_base, PAGE_POINTER_VA, 4)
            + read_exact(handle, psp_host_base, PAGE_POINTERS_VA, 12),
        )
        page0_count, page1_count = struct.unpack(
            "<2I", read_exact(handle, psp_host_base, PAGE0_COUNT_VA, 8)
        )
        page0_cache = struct.unpack(
            f"<{ATLAS_CAPACITY}H",
            read_exact(handle, psp_host_base, PAGE0_CACHE_VA, ATLAS_CAPACITY * 2),
        )
        page1_cache = struct.unpack(
            f"<{ATLAS_CAPACITY}H",
            read_exact(handle, psp_host_base, PAGE1_CACHE_VA, ATLAS_CAPACITY * 2),
        )
        result = {
            "pid": args.pid,
            "marker_host_address": f"0x{marker_host:016X}",
            "psp_host_base": f"0x{psp_host_base:016X}",
            "page_pointer": f"0x{page_pointer:08X}",
            "page0_pointer": f"0x{page0_pointer:08X}",
            "page1_pointer": f"0x{page1_pointer:08X}",
            "global_count": global_count,
            "page0_count": page0_count,
            "page1_count": page1_count,
            "page0_cache_prefix": list(page0_cache[: min(page0_count, 64)]),
            "page1_cache_prefix": list(page1_cache[: min(page1_count, 64)]),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        kernel32.CloseHandle(handle)


if __name__ == "__main__":
    main()
