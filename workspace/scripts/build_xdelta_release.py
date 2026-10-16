#!/usr/bin/env python3
"""Build and reverse-verify the separate main/DLC xdelta distribution."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
TOOLS = PROJECT.parent.parent / "Tools/xdelta3-3.2.0-windows-x86_64"
ISO_SOURCE = PROJECT / "original/Prinny - Ore ga Shujinkou de Iinsuka (Japan, Korea).iso"
ISO_TARGET = PROJECT / "work/production/Prinny_ULJS00150_KR_Final_20260803.iso"
DLC_SOURCE = PROJECT / "original/Prinny DLC"
DLC_BUILD = PROJECT / "work/builds/dlc_kr_20260803_r7_outline"
DLC_TARGET = DLC_BUILD / "memstick/PSP/GAME/ULJS00150"
TEMPLATES = PROJECT / "workspace/release"
BOOT_PROBE = PROJECT / "work/probes/final_xdelta_applied_20260803_boot.json"
RELEASE_DATE = "20260803"

SOURCE_HASHES = {
    "ISO": "af0d2873a96c5fe6f95b3fc2fb3e8702f98bba67e32f2f78c5c3d1bdaa8b9d03",
    "DL0000": "a0209702de5210b2f35c57e7c12bfddbeb691200de06769b615ca50254d48c1b",
    "DL0001": "86b48d56b6ba853f09ffb0a524ccebf4f601c78cb0f4937cb885ec8815bdb7a7",
    "DL0002": "3fbc26ed99c1b3f474e50dd5290eb0497e61f0a7e8e9268fb82980a426079be9",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_xdelta(exe: Path, *args: str | Path) -> None:
    subprocess.run([str(exe), *(str(arg) for arg in args)], check=True)


def build(output: Path, xdelta: Path) -> dict[str, object]:
    if output.exists():
        raise ValueError(f"output already exists: {output}")
    iso_report = json.loads(ISO_TARGET.with_suffix(".iso.report.json").read_text(encoding="utf-8"))
    dlc_report = json.loads((DLC_BUILD / "report.json").read_text(encoding="utf-8"))
    targets = [
        ("ISO", ISO_SOURCE, ISO_TARGET, f"Prinny_ULJS00150_KR_{RELEASE_DATE}.xdelta"),
        *[
            (
                name,
                DLC_SOURCE / f"{name}.EDAT",
                DLC_TARGET / f"{name}.EDAT",
                f"Prinny_DLC_{name}_KR_{RELEASE_DATE}.xdelta",
            )
            for name in ("DL0000", "DL0001", "DL0002")
        ],
    ]
    expected_targets = {
        "ISO": str(iso_report["output"]["sha256"]),
        **{
            name: str(dlc_report["dlc"][f"{name}.EDAT"]["output_sha256"])
            for name in ("DL0000", "DL0001", "DL0002")
        },
    }
    for key, source, target, _ in targets:
        if sha256(source) != SOURCE_HASHES[key]:
            raise ValueError(f"unsupported {key} source")
        if sha256(target) != expected_targets[key]:
            raise ValueError(f"{key} target does not match its build report")

    staging = output.with_name(output.name + ".tmp")
    if staging.exists():
        raise ValueError(f"staging path already exists: {staging}")
    staging.mkdir(parents=True)
    patch_rows: list[dict[str, object]] = []
    try:
        with tempfile.TemporaryDirectory(dir=PROJECT / "work") as temporary:
            verify_root = Path(temporary)
            for key, source, target, patch_name in targets:
                patch = staging / patch_name
                decoded = verify_root / target.name
                run_xdelta(xdelta, "-e", "-f", "-s", source, target, patch)
                run_xdelta(xdelta, "-d", "-f", "-s", source, patch, decoded)
                decoded_hash = sha256(decoded)
                if decoded_hash != expected_targets[key] or decoded.stat().st_size != target.stat().st_size:
                    raise ValueError(f"{key} xdelta reverse verification failed")
                patch_rows.append({
                    "id": key,
                    "patch": patch.name,
                    "patch_size": patch.stat().st_size,
                    "patch_sha256": sha256(patch),
                    "source_size": source.stat().st_size,
                    "source_sha256": SOURCE_HASHES[key],
                    "target_size": target.stat().st_size,
                    "target_sha256": expected_targets[key],
                    "reverse_verification": "PASS",
                })

        for name in (
            "README_적용방법.txt",
            "apply_main.cmd",
            "apply_main.ps1",
            "apply_dlc.cmd",
            "apply_dlc.ps1",
        ):
            shutil.copy2(TEMPLATES / name, staging / name)
        tool_output = staging / "tools"
        tool_output.mkdir()
        shutil.copy2(xdelta, tool_output / "xdelta3.exe")
        shutil.copy2(TOOLS / "README.md", tool_output / "README_xdelta3.md")

        boot_probe = json.loads(BOOT_PROBE.read_text(encoding="utf-8"))
        if not str(boot_probe["status"]).startswith("PASS"):
            raise ValueError("final xdelta boot probe is not PASS")
        probe_input = boot_probe.get("input", boot_probe.get("iso"))
        if not isinstance(probe_input, dict):
            raise ValueError("final xdelta boot probe has no input description")
        if str(probe_input["sha256"]) != expected_targets["ISO"]:
            raise ValueError("final xdelta boot probe used a different ISO")
        report = {
            "schema_version": 1,
            "status": "PASS: four independent xdelta patches reverse-verified",
            "distribution_policy": "main ISO patch plus optional per-DLC EDAT patches",
            "contains_original_game_files": False,
            "patches": patch_rows,
            "font_dependency": "DLC patches require the 998-character font in the main patch",
            "runtime": {
                "direct_run": (
                    "main, native stage HUD, result-time spacing, and R7 DLC "
                    "verified in PPSSPP 1.19.3 before packaging"
                ),
                "xdelta_applied_iso_boot_probe": "PASS",
                "probe_report": BOOT_PROBE.resolve().as_posix(),
                "graphical_boot": "PASS: PPSSPP 1.19.3 opened ULJS00150",
            },
        }
        (staging / "release_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        files = sorted(path for path in staging.rglob("*") if path.is_file())
        lines = [f"{sha256(path).upper()}  {path.relative_to(staging).as_posix()}" for path in files]
        (staging / "SHA256.txt").write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
        staging.replace(output)
        return report
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=PROJECT / f"dist/Prinny_KR_Patch_{RELEASE_DATE}")
    parser.add_argument("--xdelta", type=Path, default=TOOLS / "xdelta3.exe")
    args = parser.parse_args()
    report = build(args.output, args.xdelta)
    print(report["status"])
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
