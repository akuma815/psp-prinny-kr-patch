"""Patch selected BOOT UI slots into an existing, mapping-complete build.

This preserves the template font and its full character map.  It is intended
for controlled text experiments where rebuilding every UI string would change
the font population and confound the runtime result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def slot_size(source: str) -> int:
    payload = len(source.encode("cp932")) + 1
    return (payload + 3) & ~3


def mapping_table(mapping: dict) -> dict[str, bytes]:
    return {
        str(entry["character"]): bytes.fromhex(str(entry["cp932_hex"]))
        for entry in mapping["entries"]
    }


def encode_text(text: str, character_map: dict[str, bytes]) -> bytes:
    output = bytearray()
    for character in text:
        if character in character_map:
            output.extend(character_map[character])
        else:
            output.extend(character.encode("cp932", errors="strict"))
    return bytes(output)


def build(
    template_dir: Path,
    artifact_path: Path,
    offsets: set[str],
    output_dir: Path,
) -> dict:
    template_dir = template_dir.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(template_dir, output_dir)

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    mapping = json.loads(
        (template_dir / "hangul_mapping.json").read_text(encoding="utf-8")
    )
    character_map = mapping_table(mapping)
    before = (template_dir / "BOOT.BIN").read_bytes()
    patched = bytearray(before)
    rows = []
    found = set()

    for entry in artifact["entries"]:
        offset_text = str(entry["offset"]).upper().replace("X", "x")
        if offset_text not in offsets:
            continue
        found.add(offset_text)
        start = int(offset_text, 16)
        size = slot_size(str(entry["source"]))
        encoded = encode_text(str(entry["translation"]), character_map)
        if len(encoded) + 1 > size:
            raise ValueError(
                f"{offset_text}: encoded text does not fit {len(encoded)} + NUL > {size}"
            )
        patched[start:start + size] = encoded + bytes(size - len(encoded))
        rows.append(
            {
                "offset": offset_text,
                "slot_size": size,
                "source_cp932_bytes": len(str(entry["source"]).encode("cp932")),
                "translation_encoded_bytes": len(encoded),
            }
        )

    missing = sorted(offsets - found)
    if missing:
        raise ValueError(f"target offsets missing from artifact: {missing}")

    result = bytes(patched)
    (output_dir / "BOOT.BIN").write_bytes(result)
    (output_dir / "EBOOT.BIN").write_bytes(result)
    report_path = output_dir / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["status"] = "PASS: exact-length control slots over mapping-complete template"
    report["output_boot"]["sha256"] = sha256(result)
    report["output_boot"]["changed_bytes"] = sum(
        left != right for left, right in zip(before, result)
    )
    report["diagnostic_control"] = {
        "template_dir": str(template_dir),
        "artifact": str(artifact_path.resolve()),
        "patched_slots": rows,
        "all_translation_lengths_equal_source": all(
            row["translation_encoded_bytes"] == row["source_cp932_bytes"]
            for row in rows
        ),
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("template_dir", type=Path)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("offset", nargs="+")
    args = parser.parse_args()
    offsets = {text.upper().replace("X", "x") for text in args.offset}
    report = build(args.template_dir, args.artifact, offsets, args.output_dir)
    print(
        json.dumps(
            {
                "status": report["status"],
                "output_boot": report["output_boot"],
                "diagnostic_control": report["diagnostic_control"],
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
