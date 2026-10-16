#!/usr/bin/env python3
"""Patch only the two stage-result time-format slots in a direct-run tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from build_boot_ui_runtime_patch import encode_text, mapping_from_rows


TARGETS = {
    "0x0EE2F8": "클리어 %02d:%02d:%02d",
    "0x0EE320": "최고 %02d:%02d:%02d",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def slot_size(source_size: int) -> int:
    return ((source_size + 1 + 3) // 4) * 4


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-direct-run", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--output-direct-run", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    if args.output_direct_run.exists():
        raise FileExistsError(f"output already exists: {args.output_direct_run}")

    artifact = json.loads(args.artifact.read_text(encoding="utf-8"))
    mapping_artifact = json.loads(args.mapping.read_text(encoding="utf-8"))
    character_map = mapping_from_rows(mapping_artifact["entries"])
    entries = {entry["offset"]: entry for entry in artifact["entries"]}
    if set(TARGETS) - set(entries):
        raise ValueError("stage-result time entries are missing from the artifact")

    shutil.copytree(args.base_direct_run, args.output_direct_run)
    reports: list[dict[str, object]] = []
    changed_files: list[dict[str, object]] = []
    for filename in ("BOOT.BIN", "EBOOT.BIN"):
        source_path = args.base_direct_run / "PSP_GAME" / "SYSDIR" / filename
        output_path = args.output_direct_run / "PSP_GAME" / "SYSDIR" / filename
        source = source_path.read_bytes()
        output = bytearray(source)

        for offset_text, old_translation in TARGETS.items():
            entry = entries[offset_text]
            offset = int(offset_text, 0)
            capacity = slot_size(len(entry["source"].encode("cp932")))
            old_payload = encode_text(old_translation, character_map)
            new_payload = encode_text(entry["translation"], character_map)
            old_slot = old_payload + bytes(capacity - len(old_payload))
            new_slot = new_payload + bytes(capacity - len(new_payload))
            if source[offset : offset + capacity] != old_slot:
                raise ValueError(f"{filename} {offset_text} does not contain the approved old slot")
            output[offset : offset + capacity] = new_slot
            reports.append(
                {
                    "file": filename,
                    "offset": offset_text,
                    "capacity": capacity,
                    "old_payload_bytes": len(old_payload),
                    "new_payload_bytes": len(new_payload),
                    "changed_bytes": sum(a != b for a, b in zip(old_slot, new_slot, strict=True)),
                }
            )

        output_path.write_bytes(output)
        diffs = [index for index, pair in enumerate(zip(source, output, strict=True)) if pair[0] != pair[1]]
        allowed = set()
        for offset_text in TARGETS:
            entry = entries[offset_text]
            offset = int(offset_text, 0)
            capacity = slot_size(len(entry["source"].encode("cp932")))
            allowed.update(range(offset, offset + capacity))
        if any(index not in allowed for index in diffs):
            raise RuntimeError(f"{filename} changed outside the two approved slots")
        changed_files.append(
            {
                "path": f"PSP_GAME/SYSDIR/{filename}",
                "source_sha256": sha256(source_path),
                "output_sha256": sha256(output_path),
                "changed_bytes": len(diffs),
            }
        )

    report = {
        "status": "PASS: only the two stage-result time slots were patched",
        "base_direct_run": str(args.base_direct_run),
        "output_direct_run": str(args.output_direct_run),
        "slots": reports,
        "changed_files": changed_files,
        "runtime_verification": "PENDING: stage-clear result screen",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
