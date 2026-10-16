#!/usr/bin/env python3
"""Export deferred Demo00 translation-review items with their batch context."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


REVIEW_STATUSES = ("needs_review", "needs_human_review")


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def batch_contexts(batch_dir: Path) -> dict[str, list[dict[str, object]]]:
    contexts: dict[str, list[dict[str, object]]] = defaultdict(list)
    for path in sorted(batch_dir.glob("*.json")):
        batch = load_json(path)
        context = batch.get("context", {})
        for entry in batch.get("entries", []):
            contexts[entry["entry_id"]].append(
                {
                    "batch_id": batch.get("batch_id"),
                    "scene": context.get("scene"),
                    "evidence": context.get("evidence", []),
                }
            )
    return contexts


def build_queue(artifact: dict[str, object], batch_dir: Path) -> dict[str, object]:
    contexts = batch_contexts(batch_dir)
    items = []
    for entry in artifact.get("entries", []):
        translation = entry["translation"]
        if translation["status"] not in REVIEW_STATUSES:
            continue
        items.append(
            {
                "review_id": f"review/{entry['entry_id']}",
                "entry_id": entry["entry_id"],
                "coordinates": entry.get("coordinates"),
                "source": entry["protected"]["source"],
                "translation": translation,
                "contexts": contexts.get(entry["entry_id"], []),
            }
        )
    counts = Counter(item["translation"]["status"] for item in items)
    return {
        "schema_version": 1,
        "queue_id": "demo00/deferred-final-review",
        "source_identity": artifact.get("source"),
        "policy": {
            "needs_review": "전체 번역 후 교차검토할 일반 초벌",
            "needs_human_review": "최종 사용자 판단이 필요한 용어·의역·문체 초벌",
            "complete": "기존 승인 완료 또는 최종 검토 통과 항목이며 이 큐에서 제외",
        },
        "counts": {status: counts.get(status, 0) for status in REVIEW_STATUSES},
        "item_count": len(items),
        "items": items,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("batch_dir", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    queue = build_queue(load_json(args.artifact), args.batch_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        "OK: deferred review queue "
        f"items={queue['item_count']} counts={queue['counts']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
