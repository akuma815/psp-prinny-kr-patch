#!/usr/bin/env python3
"""Boot a PSP ISO in PPSSPPHeadless and retain bounded loader evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path


EVIDENCE_PATTERNS = {
    "version": "PPSSPP v",
    "game_id": "ULJS00150",
    "eboot": "Loading disc0:/PSP_GAME/SYSDIR/EBOOT.BIN",
    "module": "Module Disgaea:",
    "system_dat": 'OpenFile "disc0:/PSP_GAME/USRDIR/SYSTEM.DAT"',
    "stage_dat": 'OpenFile "disc0:/PSP_GAME/USRDIR/STAGE.DAT"',
    "timeout": "TIMEOUT",
}
IGNORED_ERROR_PATTERNS = (
    "SCE_KERNEL_ERROR_AUDIO_CHANNEL_BUSY",
)
KNOWN_WARNING_PATTERNS = (
    "Missing filesystem for 'lang/.ini'",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def input_description(path: Path) -> dict[str, object]:
    if path.is_file():
        return {"path": path.as_posix(), "kind": "file", "size": path.stat().st_size, "sha256": sha256_file(path)}
    files = sorted(item for item in path.rglob("*") if item.is_file())
    digest = hashlib.sha256()
    size = 0
    for item in files:
        relative = item.relative_to(path).as_posix().encode("utf-8")
        item_hash = sha256_file(item)
        digest.update(relative + b"\0" + item_hash.encode("ascii") + b"\n")
        size += item.stat().st_size
    return {
        "path": path.as_posix(),
        "kind": "directory",
        "file_count": len(files),
        "size": size,
        "tree_sha256": digest.hexdigest(),
    }


def classify_line(line: str) -> tuple[list[str], bool, bool]:
    evidence = [key for key, pattern in EVIDENCE_PATTERNS.items() if pattern in line]
    stripped = line.lstrip()
    known_warning = any(pattern in line for pattern in KNOWN_WARNING_PATTERNS)
    meaningful_error = stripped.startswith(("E ", "F ")) and not known_warning and not any(
        pattern in line for pattern in IGNORED_ERROR_PATTERNS
    )
    return evidence, meaningful_error, known_warning


def run(executable: Path, iso: Path, report_path: Path, duration: int) -> dict[str, object]:
    executable = executable.resolve()
    iso = iso.resolve()
    command = [
        str(executable),
        str(iso),
        f"--timeout={duration}",
        "-l",
        "-v",
        "--graphics=software",
    ]
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=executable.parent,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    evidence: dict[str, str] = {}
    errors: list[str] = []
    warnings: list[str] = []
    line_count = 0
    assert process.stdout is not None
    for raw in process.stdout:
        line_count += 1
        line = raw.rstrip("\r\n")
        keys, meaningful_error, known_warning = classify_line(line)
        for key in keys:
            evidence.setdefault(key, line[-1000:])
        if meaningful_error and len(errors) < 50:
            errors.append(line[-1000:])
        if known_warning and len(warnings) < 50:
            warnings.append(line[-1000:])
    return_code = process.wait()
    elapsed = time.monotonic() - started

    required = {"version", "game_id", "eboot", "module", "system_dat", "stage_dat", "timeout"}
    missing = sorted(required - evidence.keys())
    passed = not missing and not errors and return_code == 0
    report = {
        "schema_version": 1,
        "gate_id": "POC-PPSSPP-BOOT-001",
        "status": "PASS: PoC input reached the running game loop" if passed else "FAIL",
        "command": command,
        "working_directory": executable.parent.as_posix(),
        "ppsspp_executable": {
            "path": executable.as_posix(),
            "size": executable.stat().st_size,
            "sha256": sha256_file(executable),
        },
        "input": input_description(iso),
        "duration_seconds": duration,
        "elapsed_seconds": round(elapsed, 3),
        "return_code": return_code,
        "log_line_count": line_count,
        "evidence": evidence,
        "meaningful_errors": errors,
        "known_environment_warnings": warnings,
        "missing_evidence": missing,
        "proved": [
            "PPSSPP identified ULJS00150 from the PoC ISO",
            "EBOOT.BIN loaded and the Disgaea module started",
            "the game opened disc0:/PSP_GAME/USRDIR/SYSTEM.DAT",
            "the game opened disc0:/PSP_GAME/USRDIR/STAGE.DAT",
            "the emulated game loop remained active until the planned timeout",
        ] if passed else [],
        "not_proved": [
            "the replaced start.lzs/font.txp reached the dialogue glyph cache",
            "the Hangul glyph is visible in a dialogue containing the replaced character",
            "physical PSP compatibility",
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if not passed:
        raise RuntimeError(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("iso", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--duration", type=int, default=15)
    args = parser.parse_args()
    report = run(args.executable, args.iso, args.report, args.duration)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
