#!/usr/bin/env python3
"""Create and safely merge reviewable Demo00 translation batches."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any


ALLOWED_STATUSES = {
    "untranslated",
    "in_progress",
    "needs_review",
    "needs_human_review",
    "complete",
}


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def create_batch(
    artifact: dict[str, Any],
    batch_id: str,
    entry_ids: list[str],
    context: dict[str, Any],
) -> dict[str, Any]:
    if not batch_id or not entry_ids:
        raise ValueError("batch ID and at least one entry ID are required")
    by_id = {entry["entry_id"]: entry for entry in artifact["entries"]}
    if len(by_id) != len(artifact["entries"]):
        raise ValueError("artifact contains duplicate entry IDs")
    if len(set(entry_ids)) != len(entry_ids):
        raise ValueError("batch contains duplicate entry IDs")
    missing = [entry_id for entry_id in entry_ids if entry_id not in by_id]
    if missing:
        raise ValueError(f"unknown entry IDs: {missing}")
    entries = []
    for entry_id in entry_ids:
        entry = by_id[entry_id]
        entries.append({
            "entry_id": entry_id,
            "protected_snapshot": copy.deepcopy(entry["protected"]),
            "base_translation": copy.deepcopy(entry["translation"]),
            "proposed_translation": copy.deepcopy(entry["translation"]),
        })
    return {
        "schema_version": 1,
        "batch_id": batch_id,
        "table_id": artifact["table_id"],
        "source_identity": copy.deepcopy(artifact["source"]),
        "artifact_schema_version": artifact["schema_version"],
        "artifact_snapshot_sha256": canonical_hash(artifact),
        "context": context,
        "constraints": {
            "speaker_payload_bytes": artifact["layout"]["speaker_size"] - 1,
            "line_payload_bytes": artifact["layout"]["line_size"] - 1,
            "hangul_projection_bytes_per_syllable": 2,
            "production_encoding_approved": False,
            "protected_fields_editable": False,
        },
        "entries": entries,
    }


def projected_bytes(text: str) -> int:
    total = 0
    for character in text:
        if "가" <= character <= "힣":
            total += 2
            continue
        try:
            total += len(character.encode("cp932", errors="strict"))
        except UnicodeEncodeError as error:
            raise ValueError(
                f"projection has unsupported non-Hangul character U+{ord(character):04X}"
            ) from error
    return total


def _validate_translation(translation: dict[str, Any], entry_id: str) -> None:
    speaker = translation.get("speaker")
    lines = translation.get("lines")
    status = translation.get("status")
    if not isinstance(speaker, str):
        raise ValueError(f"speaker must be text for {entry_id}")
    if not isinstance(lines, list) or len(lines) != 3 or not all(
        isinstance(line, str) for line in lines
    ):
        raise ValueError(f"lines must contain three strings for {entry_id}")
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"invalid status for {entry_id}")
    if not isinstance(translation.get("notes"), str):
        raise ValueError(f"notes must be text for {entry_id}")
    flags = translation.get("flags")
    if not isinstance(flags, list) or not all(isinstance(flag, str) for flag in flags):
        raise ValueError(f"flags must be a text list for {entry_id}")
    if status == "untranslated" and (speaker or any(lines)):
        raise ValueError(f"untranslated entry has target text: {entry_id}")


def merge_batch(
    artifact: dict[str, Any], batch: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    if batch.get("schema_version") != 1:
        raise ValueError("unsupported batch schema")
    if batch.get("table_id") != artifact.get("table_id"):
        raise ValueError("batch table identity is stale")
    if batch.get("source_identity") != artifact.get("source"):
        raise ValueError("batch source identity is stale")
    by_id = {entry["entry_id"]: entry for entry in artifact["entries"]}
    merged = copy.deepcopy(artifact)
    merged_by_id = {entry["entry_id"]: entry for entry in merged["entries"]}
    seen: set[str] = set()
    fit_entries = []
    hangul: set[str] = set()
    for item in batch.get("entries", []):
        entry_id = item.get("entry_id")
        if entry_id in seen:
            raise ValueError(f"duplicate batch entry: {entry_id}")
        seen.add(entry_id)
        if entry_id not in by_id:
            raise ValueError(f"unknown batch entry: {entry_id}")
        current = by_id[entry_id]
        if item.get("protected_snapshot") != current["protected"]:
            raise ValueError(f"protected snapshot is stale for {entry_id}")
        if item.get("base_translation") != current["translation"]:
            raise ValueError(f"translation conflict for {entry_id}")
        proposed = item.get("proposed_translation")
        if not isinstance(proposed, dict):
            raise ValueError(f"proposed translation is missing for {entry_id}")
        _validate_translation(proposed, entry_id)
        speaker_bytes = projected_bytes(proposed["speaker"])
        line_bytes = [projected_bytes(line) for line in proposed["lines"]]
        speaker_limit = int(batch["constraints"]["speaker_payload_bytes"])
        line_limit = int(batch["constraints"]["line_payload_bytes"])
        fits = speaker_bytes <= speaker_limit and all(
            value <= line_limit for value in line_bytes
        )
        fit_entries.append({
            "entry_id": entry_id,
            "speaker_projected_bytes": speaker_bytes,
            "line_projected_bytes": line_bytes,
            "speaker_limit": speaker_limit,
            "line_limit": line_limit,
            "projected_fixed_slot_fit": fits,
        })
        for character in proposed["speaker"] + "".join(proposed["lines"]):
            if "가" <= character <= "힣":
                hangul.add(character)
        merged_by_id[entry_id]["translation"] = copy.deepcopy(proposed)
    if not seen:
        raise ValueError("batch has no entries")
    translation_review_complete = all(
        merged_by_id[entry_id]["translation"]["status"] == "complete"
        for entry_id in seen
    )
    report = {
        "schema_version": 1,
        "gate_id": "DEMO00-BATCH-MERGE-001",
        "batch_id": batch["batch_id"],
        "status": (
            "PASS: protected merge; translation review complete"
            if translation_review_complete
            else "PASS: protected merge; human review still required"
        ),
        "merged_entry_count": len(seen),
        "entries": fit_entries,
        "all_entries_projected_fixed_slot_fit": all(
            item["projected_fixed_slot_fit"] for item in fit_entries
        ),
        "batch_unique_hangul_count": len(hangul),
        "batch_unique_hangul": "".join(sorted(hangul)),
        "translation_review_complete": translation_review_complete,
        "production_encoding_approved": False,
        "build_eligible": False,
    }
    return merged, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("artifact", type=Path)
    create.add_argument("output", type=Path)
    create.add_argument("batch_id")
    create.add_argument("entry_ids", nargs="+")
    create.add_argument("--scene", required=True)
    create.add_argument("--evidence", action="append", default=[])
    merge = subparsers.add_parser("merge")
    merge.add_argument("artifact", type=Path)
    merge.add_argument("batch", type=Path)
    merge.add_argument("report", type=Path)
    args = parser.parse_args()

    artifact = json.loads(args.artifact.read_text(encoding="utf-8"))
    if args.command == "create":
        batch = create_batch(
            artifact,
            args.batch_id,
            args.entry_ids,
            {"scene": args.scene, "evidence": args.evidence},
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"OK: created {args.batch_id} with {len(batch['entries'])} entries")
        return 0

    batch = json.loads(args.batch.read_text(encoding="utf-8"))
    merged, report = merge_batch(artifact, batch)
    args.artifact.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
