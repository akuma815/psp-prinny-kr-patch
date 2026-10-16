"""Generate or apply the Demo00 speaker-length review queue.

The game preserves the original speaker-box style byte, so a Korean speaker label
that contains more Unicode code points than the Japanese source is treated as an
overflow risk.  Generation never modifies the translation SSOT.  Apply mode only
changes ``entries[].translation.speaker`` after validating every queued snapshot.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import tempfile
from collections import defaultdict
from datetime import date
from pathlib import Path


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def overlength_groups(artifact: dict) -> list[dict]:
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for entry in artifact["entries"]:
        source = entry.get("protected", {}).get("source", {}).get("speaker", "")
        current = entry.get("translation", {}).get("speaker", "")
        if source and current and len(current) > len(source):
            groups[(source, current)].append(entry["entry_id"])

    ordered = sorted(
        groups.items(),
        key=lambda pair: (
            -(len(pair[0][1]) - len(pair[0][0])),
            pair[0][0],
            pair[0][1],
        ),
    )
    items = []
    for number, ((source, current), entry_ids) in enumerate(ordered, start=1):
        items.append(
            {
                "review_id": f"SPEAKER-LEN-{number:03d}",
                "source_speaker": source,
                "source_length": len(source),
                "current_translation": current,
                "current_length": len(current),
                "excess": len(current) - len(source),
                "replacement_speaker": current,
                "affected_entry_count": len(entry_ids),
                "affected_entry_ids": entry_ids,
                "status": "pending",
                "review_note": "",
            }
        )
    return items


def generate(artifact_path: Path, queue_path: Path, markdown_path: Path) -> dict:
    artifact = read_json(artifact_path)
    items = overlength_groups(artifact)
    queue = {
        "schema_version": 1,
        "review_id": "DEMO00-SPEAKER-LENGTH-001",
        "generated_on": date.today().isoformat(),
        "source_artifact": str(artifact_path).replace("\\", "/"),
        "source_artifact_sha256": sha256(artifact_path),
        "comparison_policy": {
            "unit": "Unicode code points including spaces and punctuation",
            "condition": "len(current_translation) > len(source_speaker)",
            "grouping": "identical source_speaker + current_translation pairs",
            "edit_field": "items[].replacement_speaker",
            "protected_until_apply": [
                "source_speaker",
                "source_length",
                "current_translation",
                "current_length",
                "affected_entry_ids",
            ],
        },
        "summary": {
            "affected_entry_count": sum(i["affected_entry_count"] for i in items),
            "unique_review_item_count": len(items),
        },
        "items": items,
    }
    write_json_atomic(queue_path, queue)
    write_markdown(markdown_path, queue, queue_path)
    return queue


def markdown_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def write_markdown(path: Path, queue: dict, queue_path: Path) -> None:
    lines = [
        "# Demo00 화자명 길이 초과 검토 목록",
        "",
        f"- 영향 엔트리: {queue['summary']['affected_entry_count']}개",
        f"- 중복을 묶은 수정 항목: {queue['summary']['unique_review_item_count']}개",
        "- 판정 기준: 공백과 문장부호를 포함한 유니코드 글자 수가 원문보다 긴 화자명",
        f"- 실제 수정 파일: `{str(queue_path).replace(chr(92), '/')}`의 `replacement_speaker`",
        "- 아래 표는 확인용이며 원본 번역본에는 아직 반영되지 않음",
        "",
        "| ID | 원문 | 원문 길이 | 현재 번역 | 번역 길이 | 초과 | 적용 건수 |",
        "| --- | --- | ---: | --- | ---: | ---: | ---: |",
    ]
    for item in queue["items"]:
        lines.append(
            "| {review_id} | {source} | {source_length} | {current} | "
            "{current_length} | +{excess} | {count} |".format(
                review_id=item["review_id"],
                source=markdown_escape(item["source_speaker"]),
                source_length=item["source_length"],
                current=markdown_escape(item["current_translation"]),
                current_length=item["current_length"],
                excess=item["excess"],
                count=item["affected_entry_count"],
            )
        )
    lines.extend(["", "## 영향 엔트리", ""])
    for item in queue["items"]:
        lines.append(
            f"- `{item['review_id']}`: "
            + ", ".join(f"`{entry_id}`" for entry_id in item["affected_entry_ids"])
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def apply_queue(
    artifact_path: Path,
    queue_path: Path,
    report_path: Path,
    review_date: str,
) -> dict:
    artifact = read_json(artifact_path)
    queue = read_json(queue_path)
    if queue.get("review_id") != "DEMO00-SPEAKER-LENGTH-001":
        raise ValueError("unsupported speaker-length review queue")
    if queue.get("summary", {}).get("unique_review_item_count") != len(
        queue.get("items", [])
    ):
        raise ValueError("queue summary does not match item count")

    original_protected = {
        entry["entry_id"]: copy.deepcopy(entry["protected"])
        for entry in artifact["entries"]
    }
    entries = {entry["entry_id"]: entry for entry in artifact["entries"]}
    seen: set[str] = set()
    changes = []

    for item in queue["items"]:
        source = item["source_speaker"]
        current = item["current_translation"]
        replacement = item["replacement_speaker"]
        if not replacement:
            raise ValueError(f"empty replacement: {item['review_id']}")
        if len(replacement) > len(source):
            raise ValueError(
                f"replacement still exceeds source length: {item['review_id']} "
                f"({len(replacement)} > {len(source)})"
            )
        entry_ids = item["affected_entry_ids"]
        if item["affected_entry_count"] != len(entry_ids):
            raise ValueError(f"affected count mismatch: {item['review_id']}")
        for entry_id in entry_ids:
            if entry_id in seen:
                raise ValueError(f"duplicate affected entry: {entry_id}")
            seen.add(entry_id)
            if entry_id not in entries:
                raise ValueError(f"missing affected entry: {entry_id}")
            entry = entries[entry_id]
            actual_source = entry["protected"]["source"]["speaker"]
            actual_current = entry["translation"]["speaker"]
            if actual_source != source or actual_current != current:
                raise ValueError(f"stale queue snapshot: {entry_id}")
            entry["translation"]["speaker"] = replacement
            if replacement != current:
                changes.append(
                    {
                        "entry_id": entry_id,
                        "source_speaker": source,
                        "before": current,
                        "after": replacement,
                    }
                )

    for entry in artifact["entries"]:
        if entry["protected"] != original_protected[entry["entry_id"]]:
            raise ValueError(f"protected field changed: {entry['entry_id']}")

    remaining_groups = overlength_groups(artifact)
    report = {
        "schema_version": 1,
        "gate_id": "DEMO00-SPEAKER-LENGTH-APPLY-001",
        "applied_on": review_date,
        "source_queue": str(queue_path).replace("\\", "/"),
        "changed_entry_count": len(changes),
        "remaining_overlength_entry_count": sum(
            item["affected_entry_count"] for item in remaining_groups
        ),
        "remaining_overlength_group_count": len(remaining_groups),
        "changes": changes,
    }
    write_json_atomic(artifact_path, artifact)
    write_json_atomic(report_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser("generate")
    generate_parser.add_argument("artifact", type=Path)
    generate_parser.add_argument("queue", type=Path)
    generate_parser.add_argument("markdown", type=Path)

    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("artifact", type=Path)
    apply_parser.add_argument("queue", type=Path)
    apply_parser.add_argument("report", type=Path)
    apply_parser.add_argument("--date", required=True)

    args = parser.parse_args()
    if args.command == "generate":
        queue = generate(args.artifact, args.queue, args.markdown)
        print(
            "OK: affected entries={affected_entry_count} unique items={unique_review_item_count}".format(
                **queue["summary"]
            )
        )
        return 0

    report = apply_queue(args.artifact, args.queue, args.report, args.date)
    print(
        f"OK: changed entries={report['changed_entry_count']} "
        f"remaining entries={report['remaining_overlength_entry_count']} "
        f"groups={report['remaining_overlength_group_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
