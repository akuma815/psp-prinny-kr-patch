"""Approve an exact Demo00 review-queue snapshot without touching protected fields."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path


REVIEW_ONLY_FLAGS = {
    "draft",
    "deferred_review",
    "meaning_review_required",
    "expression_review_required",
    "term_review_required",
    "speaker_style_review_required",
    "culture_review_required",
    "idiom_review_required",
    "control_review_required",
}
REVIEW_STATUSES = {"needs_review", "needs_human_review"}
TECHNICAL_REVIEW_FLAGS = {"consumer_review_required"}


def approve_snapshot(artifact: dict, queue: dict, terminology: dict, date: str) -> dict:
    if artifact.get("source") != queue.get("source_identity"):
        raise ValueError("queue source identity does not match the translation artifact")
    if queue.get("item_count") != len(queue.get("items", [])):
        raise ValueError("queue item_count does not match its items")

    artifact_by_id = {entry["entry_id"]: entry for entry in artifact["entries"]}
    queue_ids: list[str] = []
    preserved_technical_flags: dict[str, list[str]] = {}
    for item in queue["items"]:
        entry_id = item["entry_id"]
        if entry_id in queue_ids:
            raise ValueError(f"duplicate queue entry: {entry_id}")
        queue_ids.append(entry_id)
        if entry_id not in artifact_by_id:
            raise ValueError(f"queue entry missing from artifact: {entry_id}")
        current = artifact_by_id[entry_id]["translation"]
        queued = item["translation"]
        if current != queued:
            raise ValueError(f"stale queue translation: {entry_id}")
        if current["status"] not in REVIEW_STATUSES:
            raise ValueError(f"queue entry is not reviewable: {entry_id}")

        current["status"] = "complete"
        current["flags"] = [
            flag
            for flag in current.get("flags", [])
            if flag not in REVIEW_ONLY_FLAGS
            and not (
                flag.endswith("_review_required")
                and flag not in TECHNICAL_REVIEW_FLAGS
            )
        ]
        for flag in ("meaning_reviewed", "user_approved"):
            if flag not in current["flags"]:
                current["flags"].append(flag)
        technical = [flag for flag in current["flags"] if flag.endswith("_review_required")]
        if technical:
            preserved_technical_flags[entry_id] = technical
        approval_note = f"{date} 사용자 검토 큐 승인."
        current["notes"] = (
            f"{current.get('notes', '').rstrip()} {approval_note}".strip()
        )

    approved_terms = 0
    for decision in terminology.get("decisions", []):
        if decision.get("status") != "needs_human_review":
            continue
        decision["status"] = "approved"
        decision["approval"] = {
            "date": date,
            "basis": "사용자가 현행 review queue 번역 전체를 검토하고 해당 버전을 승인",
        }
        approved_terms += 1

    return {
        "schema_version": 1,
        "gate_id": "DEMO00-REVIEW-APPROVAL-001",
        "status": "PASS: exact queued translations approved",
        "approval_date": date,
        "approved_entry_count": len(queue_ids),
        "approved_term_decision_count": approved_terms,
        "preserved_technical_flags": preserved_technical_flags,
    }


def write_json_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("queue", type=Path)
    parser.add_argument("terminology", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--date", required=True)
    parser.add_argument("--expected-count", type=int, required=True)
    args = parser.parse_args()

    artifact = json.loads(args.artifact.read_text(encoding="utf-8"))
    queue = json.loads(args.queue.read_text(encoding="utf-8"))
    terminology = json.loads(args.terminology.read_text(encoding="utf-8"))
    if queue.get("item_count") != args.expected_count:
        raise ValueError(
            f"expected {args.expected_count} queue items, got {queue.get('item_count')}"
        )
    report = approve_snapshot(artifact, queue, terminology, args.date)
    write_json_atomic(args.artifact, artifact)
    write_json_atomic(args.terminology, terminology)
    write_json_atomic(args.report, report)
    print(
        f"OK: approved entries={report['approved_entry_count']} "
        f"terms={report['approved_term_decision_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
