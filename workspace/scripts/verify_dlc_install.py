#!/usr/bin/env python3
"""Verify a PPSSPP Prinny DLC install against the supported original baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import export_dlc_text


PARAM_PBP = {
    "size": 23971,
    "sha256": "b4d52c1fd59d46ae9a9f6b0d4a01dbb95f79d51e78fe7901d6a3e8051fb62b16",
}


def identity(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {
        "path": path.as_posix(),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def verify(source_dir: Path, ppsspp_root: Path) -> dict[str, object]:
    target_dir = ppsspp_root / "memstick/PSP/GAME/ULJS00150"
    expected = {
        name: {"size": values["size"], "sha256": values["sha256"]}
        for name, values in export_dlc_text.EXPECTED_SOURCES.items()
    }
    expected["PARAM.PBP"] = PARAM_PBP
    files: list[dict[str, object]] = []
    for name, baseline in expected.items():
        source = identity(source_dir / name)
        installed = identity(target_dir / name)
        source_ok = source["size"] == baseline["size"] and source["sha256"] == baseline["sha256"]
        installed_ok = installed["size"] == baseline["size"] and installed["sha256"] == baseline["sha256"]
        same = source["sha256"] == installed["sha256"] and source["size"] == installed["size"]
        files.append(
            {
                "name": name,
                "expected": baseline,
                "source": source,
                "installed": installed,
                "source_ok": source_ok,
                "installed_ok": installed_ok,
                "source_equals_installed": same,
            }
        )
    passed = all(
        row["source_ok"] and row["installed_ok"] and row["source_equals_installed"]
        for row in files
    )
    return {
        "schema_version": 1,
        "scope": "PPSSPP original Prinny DLC install baseline",
        "ppsspp_root": ppsspp_root.as_posix(),
        "target_dir": target_dir.as_posix(),
        "files": files,
        "status": "PASS" if passed else "FAIL",
        "not_proved": [
            "PPSSPP has loaded the DLC files",
            "the DLC menu and stages are runtime-reachable",
            "DCLT or DCHR text is displayed",
            "the current Korean font preserves all untranslated DLC glyphs",
        ],
    }


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    project = script_dir.parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=project / "original/Prinny DLC",
    )
    parser.add_argument(
        "--ppsspp-root",
        type=Path,
        default=Path(r"H:\ppsspp_stable_1.19.3"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=project / "work/analysis/dlc_install_baseline.json",
    )
    args = parser.parse_args()
    report = verify(args.source_dir, args.ppsspp_root)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if report["status"] != "PASS":
        raise SystemExit(f"FAIL: DLC install does not match supported baseline; see {args.report}")
    print(f"PASS: four original DLC files match at {report['target_dir']}")
    print(f"report={args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
