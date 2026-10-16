"""Build a BOOT UI diagnostic artifact with exact source-byte-length strings.

Only the four title-settings descriptions are changed.  Every replacement
character occupies exactly two runtime bytes, and IDEOGRAPHIC SPACE padding
makes each replacement exactly as long as its CP932 source.
"""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path


REPLACEMENTS = {
    "0x0ED624": "【일반】게임내효과음음량을변경합니다。",
    "0x0ED650": "【일반】게임내배경음음량을변경합니다。",
    "0x0ED680": "【이벤트】음성메시지음량을변경합니다。",
    "0x0ED6B4": "【전투】연사때카메라회전여부를설정합니다。",
}
PADDING = "\u3000"


def runtime_size(character: str) -> int:
    if len(character) != 1:
        raise ValueError("runtime_size expects one character")
    if "\uac00" <= character <= "\ud7a3":
        return 2
    return len(character.encode("cp932"))


def text_runtime_size(text: str) -> int:
    return sum(runtime_size(character) for character in text)


def exact_length_translation(source: str, replacement: str) -> str:
    source_size = len(source.encode("cp932"))
    replacement_size = text_runtime_size(replacement)
    if replacement_size > source_size:
        raise ValueError(
            f"replacement is longer than source: {replacement_size} > {source_size}"
        )
    difference = source_size - replacement_size
    padding_size = runtime_size(PADDING)
    if difference % padding_size:
        raise ValueError(f"cannot pad an odd byte difference: {difference}")
    result = replacement + PADDING * (difference // padding_size)
    if text_runtime_size(result) != source_size:
        raise AssertionError("exact-length construction failed")
    if any(runtime_size(character) != 2 for character in result):
        raise AssertionError("control text contains a non-two-byte character")
    return result


def build(source_path: Path, output_path: Path, report_path: Path) -> dict:
    original_bytes = source_path.read_bytes()
    artifact = json.loads(original_bytes.decode("utf-8"))
    output = deepcopy(artifact)
    rows = []
    found = set()

    for entry in output["entries"]:
        offset = str(entry["offset"]).upper().replace("X", "x")
        if offset not in REPLACEMENTS:
            continue
        found.add(offset)
        source = str(entry["source"])
        before = str(entry["translation"])
        after = exact_length_translation(source, REPLACEMENTS[offset])
        entry["translation"] = after
        rows.append(
            {
                "offset": offset,
                "source": source,
                "before": before,
                "after": after,
                "source_cp932_bytes": len(source.encode("cp932")),
                "before_runtime_bytes": text_runtime_size(before),
                "after_runtime_bytes": text_runtime_size(after),
                "after_characters": len(after),
                "padding_characters": len(after) - len(REPLACEMENTS[offset]),
                "all_after_characters_two_bytes": all(
                    runtime_size(character) == 2 for character in after
                ),
            }
        )

    missing = sorted(set(REPLACEMENTS) - found)
    if missing:
        raise ValueError(f"target offsets missing from artifact: {missing}")
    if source_path.read_bytes() != original_bytes:
        raise AssertionError("canonical source artifact changed during control build")

    output["artifact_id"] = "boot-ui-runtime-exact-source-length-control-20260727"
    output.setdefault("rules", {})["diagnostic_control"] = (
        "four title-settings descriptions only; exact source byte length; "
        "two runtime bytes per character"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    report = {
        "status": "PASS",
        "source_artifact": str(source_path.resolve()),
        "output_artifact": str(output_path.resolve()),
        "canonical_unchanged": source_path.read_bytes() == original_bytes,
        "changed_entries": len(rows),
        "rows": rows,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            build(args.source, args.output, args.report),
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
