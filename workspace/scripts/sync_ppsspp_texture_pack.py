#!/usr/bin/env python3
"""Synchronize every installed exact PNG with PPSSPP textures.ini."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_aliases(path: Path) -> dict[str, str]:
    aliases: dict[str, str] = {}
    section = ""
    if not path.is_file():
        return aliases
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            section = line.lower()
            continue
        if section == "[hashes]" and "=" in line:
            key, value = (part.strip() for part in line.split("=", 1))
            if key and value:
                aliases[key.lower()] = value
    return aliases


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--texture-dir",
        type=Path,
        default=Path(r"H:\ppsspp\memstick\PSP\TEXTURES\ULJS00150"),
    )
    parser.add_argument(
        "--backup",
        type=Path,
        default=PROJECT_ROOT
        / "backups/texture_pack_before_runtime_sync_20260726/textures.ini",
    )
    parser.add_argument(
        "--restore-dir",
        type=Path,
        default=PROJECT_ROOT / "work/live/runtime_text_atlas_preview/generated",
        help="project output containing exact PNGs that may be missing from install",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_ROOT / "work/reports/ppsspp_texture_pack_sync.json",
    )
    args = parser.parse_args()

    texture_dir = args.texture_dir.resolve()
    ini_path = texture_dir / "textures.ini"
    if not ini_path.is_file():
        raise FileNotFoundError(ini_path)
    args.backup.parent.mkdir(parents=True, exist_ok=True)
    if not args.backup.exists():
        shutil.copy2(ini_path, args.backup)

    aliases = read_aliases(ini_path)
    installed = sorted(texture_dir.glob("*.png"))
    added: list[str] = []
    for png in installed:
        key = png.stem.lower()
        if key not in aliases:
            aliases[key] = png.name
            added.append(key)

    missing_targets = sorted(
        {
            value
            for value in aliases.values()
            if not (texture_dir / value).is_file()
        }
    )
    restored: list[str] = []
    for name in missing_targets:
        source = args.restore_dir / name
        if source.is_file():
            shutil.copy2(source, texture_dir / name)
            restored.append(name)
    missing_targets = sorted(
        {
            value
            for value in aliases.values()
            if not (texture_dir / value).is_file()
        }
    )
    if missing_targets:
        raise ValueError(f"textures.ini has missing targets: {missing_targets}")
    installed = sorted(texture_dir.glob("*.png"))

    lines = [
        "[options]",
        "version = 1",
        "hash = quick",
        "ignoreAddress = false",
        "",
        "[hashes]",
    ]
    lines.extend(f"{key} = {aliases[key]}" for key in sorted(aliases))
    ini_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    report = {
        "status": "PASS",
        "texture_dir": str(texture_dir),
        "installed_png_count": len(installed),
        "alias_count": len(aliases),
        "added_direct_alias_count": len(added),
        "added_direct_aliases": added,
        "restored_target_count": len(restored),
        "restored_targets": restored,
        "missing_targets": missing_targets,
        "textures_ini": str(ini_path),
        "textures_ini_sha256": sha256(ini_path),
        "backup": str(args.backup.resolve()),
        "backup_sha256": sha256(args.backup),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
