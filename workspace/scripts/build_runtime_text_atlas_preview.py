#!/usr/bin/env python3
"""Build exact PPSSPP replacements for observed runtime text atlases.

These files were identified from PPSSPP GE/Graphics Debugger `Hashfiles`
values.  They are dynamic RGBA snapshots rather than baked ANIME.DAT records,
so every observed address/CLUT/content-hash identity is emitted separately.

Only each atlas' active text rectangle is cleared.  Pixels outside that
rectangle are required to remain byte-for-byte identical.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


TRANSLATIONS = {
    "0955c100564378d0224f31a7.png": [
        "말을 걸어 보세요.",
        "거점의 세이브 담당에게 말을 걸면",
        "게임을 저장할 수 있습니다.",
        "왼쪽의 파란 영혼에게 다가가",
        "□ 버튼으로 대화하세요.",
    ],
    "0955c100a841f78d224f31a7.png": [
        "말을 걸어 보세요.",
        "거점의 세이브 담당에게 말을 걸면",
        "게임을 저장할 수 있습니다.",
        "왼쪽의 파란 영혼에게 다가가",
        "□ 버튼으로 대화하세요.",
    ],
    "09564140a841f78dc289a541.png": [
        "말을 걸어 보세요.",
        "거점의 세이브 담당에게 말을 걸면",
        "게임을 저장할 수 있습니다.",
        "왼쪽의 파란 영혼에게 다가가",
        "□ 버튼으로 대화하세요.",
    ],
    "09564140a841f78d8be4d068.png": [
        "튜토리얼 설명 확인",
        "튜토리얼 스테이지 1",
        "튜토리얼 스테이지 2",
        "TIPS 난이도 변경",
        "확인한 튜토리얼 설명을",
        "다시 볼 수 있습니다.",
    ],
    "09564140a841f78d88699e8f.png": [
        "[튜토리얼 데이터 저장]",
        "거점의 세이브 담당에게 말을 걸면",
        "게임을 저장할 수 있습니다.",
        "왼쪽의 파란 영혼에게 다가가",
        "□ 버튼으로 대화하세요.",
    ],
    "09564140a841f78dd10ef257.png": [
        "[튜토리얼 데이터 저장]",
        "거점의 세이브 담당에게 말을 걸면",
        "게임을 저장할 수 있습니다.",
        "왼쪽의 파란 영혼에게 다가가",
        "□ 버튼으로 대화하세요.",
    ],
    "09564140a841f78d830c4200.png": [
        "알현실로 들어가겠습니까?",
        "예",
        "아니요",
        "",
        "세이브 담당에게 말을 걸면",
        "게임을 저장할 수 있습니다.",
    ],
    "0955c100a841f78d24852a5e.png": [
        "설정 파일을 확인하시겠습니까?",
        "예",
        "아니요",
        "",
        "거점에서는 세이브 담당에게",
        "말을 걸어 저장할 수 있습니다.",
    ],
    "09564140a841f78dfc7541a2.png": [
        "설정",
        "타이틀 화면으로 돌아갑니다.",
        "현재 플레이 중인 데이터는",
        "저장되지 않습니다.",
        "정말 괜찮습니까?",
    ],
    "09564140a841f78d1f59463c.png": [
        "설정",
        "BGM 음량: 5",
        "음성 음량: 5",
        "게임 중 효과음의 음량을",
        "조절합니다.",
    ],
    "09564140a841f78dc872c67b.png": [
        "타이틀 화면으로 돌아갑니다.",
        "현재 플레이 중인 데이터는",
        "저장되지 않습니다.",
        "정말 괜찮습니까?",
    ],
}

TUTORIAL_NAMES = {
    "0955c100564378d0224f31a7.png",
    "0955c100a841f78d224f31a7.png",
    "09564140a841f78dc289a541.png",
    "09564140a841f78d8be4d068.png",
    "09564140a841f78d88699e8f.png",
    "09564140a841f78dd10ef257.png",
    "09564140a841f78d830c4200.png",
    "0955c100a841f78d24852a5e.png",
    "09564140a841f78dfc7541a2.png",
    "09564140a841f78d1f59463c.png",
    "09564140a841f78dc872c67b.png",
}

DEMO_OLD_NAME = "091cd1e0a8d5fd96af437712.png"
DEMO_TRANSLATED_NAME = "091cd1e0a8d5fd96f4cbdbb1.png"
PROTECTED_NAMES = {"0939d9b0b3dddb901557c943.png"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def changed_pixel_counts(
    before: Image.Image,
    after: Image.Image,
    bounds: tuple[int, int, int, int],
) -> tuple[int, int]:
    x0, y0, x1, y1 = bounds
    before_bytes = before.tobytes()
    after_bytes = after.tobytes()
    inside = 0
    outside = 0
    for index in range(before.width * before.height):
        offset = index * 4
        if before_bytes[offset : offset + 4] == after_bytes[offset : offset + 4]:
            continue
        x = index % before.width
        y = index // before.width
        if x0 <= x < x1 and y0 <= y < y1:
            inside += 1
        else:
            outside += 1
    return inside, outside


def select_font(
    draw: ImageDraw.ImageDraw,
    font_path: Path,
    lines: list[str],
    bounds: tuple[int, int, int, int],
) -> ImageFont.FreeTypeFont:
    x0, y0, x1, y1 = bounds
    for size in range(11, 6, -1):
        font = ImageFont.truetype(str(font_path), size)
        widths = [
            draw.textbbox((0, 0), line, font=font, stroke_width=1)[2]
            for line in lines
            if line
        ]
        line_height = size + 3
        if max(widths, default=0) <= x1 - x0 - 4 and len(lines) * line_height <= y1 - y0 - 4:
            return font
    raise RuntimeError(f"translation does not fit {bounds}: {lines}")


def build_text_atlas(
    source_path: Path,
    output_path: Path,
    font_path: Path,
    lines: list[str],
) -> dict[str, object]:
    source = Image.open(source_path).convert("RGBA")
    if source.size != (256, 256):
        raise ValueError(f"unexpected text atlas size: {source_path.name} {source.size}")

    if source_path.name in TUTORIAL_NAMES:
        bounds = (0, 0, 242, 142)
    else:
        bounds = (0, 0, 242, 185)

    output = source.copy()
    output.paste((0, 0, 0, 0), bounds)
    draw = ImageDraw.Draw(output)
    font = select_font(draw, font_path, lines, bounds)
    line_height = font.size + 3
    x = bounds[0] + 2
    y = bounds[1] + 1
    rendered = []
    for line in lines:
        if line:
            draw.text(
                (x, y),
                line,
                font=font,
                fill=(255, 255, 255, 255),
                stroke_width=1,
                stroke_fill=(24, 24, 24, 255),
            )
            rendered.append({"text": line, "xy": [x, y]})
        y += line_height

    changed_inside, changed_outside = changed_pixel_counts(source, output, bounds)
    if changed_outside:
        raise RuntimeError(
            f"protected pixels changed outside {bounds}: {source_path.name} {changed_outside}"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.save(output_path)
    return {
        "name": source_path.name,
        "source": str(source_path.resolve()),
        "output": str(output_path.resolve()),
        "source_sha256": sha256(source_path),
        "output_sha256": sha256(output_path),
        "bounds": list(bounds),
        "font_size": font.size,
        "rendered": rendered,
        "changed_pixels_inside": changed_inside,
        "changed_pixels_outside": changed_outside,
        "translation_status": "first-pass-runtime-review-pending",
    }


def merge_texture_aliases(install_dir: Path, texture_names: list[str]) -> dict[str, object]:
    ini_path = install_dir / "textures.ini"
    aliases: dict[str, str] = {}
    if ini_path.is_file():
        section = ""
        for raw in ini_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line.startswith("[") and line.endswith("]"):
                section = line.lower()
                continue
            if section == "[hashes]" and "=" in line:
                key, value = (part.strip() for part in line.split("=", 1))
                if key and value:
                    aliases[key] = value

    for name in texture_names:
        aliases[Path(name).stem] = name

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
    return {
        "path": str(ini_path.resolve()),
        "sha256": sha256(ini_path),
        "total_alias_count": len(aliases),
        "added_aliases": sorted(Path(name).stem for name in texture_names),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--font", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--install-dir", type=Path)
    args = parser.parse_args()

    if not args.font.is_file():
        raise SystemExit(f"font not found: {args.font}")

    expected = set(TRANSLATIONS) | {DEMO_OLD_NAME} | PROTECTED_NAMES
    missing = sorted(name for name in expected if not (args.source_dir / name).is_file())
    if missing:
        raise SystemExit(f"missing exact runtime textures: {missing}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for name, lines in TRANSLATIONS.items():
        results.append(
            build_text_atlas(
                args.source_dir / name,
                args.output_dir / name,
                args.font,
                lines,
            )
        )

    translated_demo = args.source_dir / DEMO_TRANSLATED_NAME
    if not translated_demo.is_file():
        raise SystemExit(f"translated demo reference not found: {translated_demo}")
    demo_output = args.output_dir / DEMO_OLD_NAME
    shutil.copy2(translated_demo, demo_output)
    demo_result = {
        "name": DEMO_OLD_NAME,
        "source": str((args.source_dir / DEMO_OLD_NAME).resolve()),
        "translated_reference": str(translated_demo.resolve()),
        "output": str(demo_output.resolve()),
        "source_sha256": sha256(args.source_dir / DEMO_OLD_NAME),
        "output_sha256": sha256(demo_output),
        "translation_status": "first-pass-runtime-review-pending",
        "note": "same CLUT address as the already translated f4cbdbb1 atlas",
    }

    generated_names = sorted([*TRANSLATIONS, DEMO_OLD_NAME])
    installed: list[str] = []
    textures_ini = None
    if args.install_dir:
        args.install_dir.mkdir(parents=True, exist_ok=True)
        for name in generated_names:
            destination = args.install_dir / name
            shutil.copy2(args.output_dir / name, destination)
            installed.append(str(destination.resolve()))
        textures_ini = merge_texture_aliases(args.install_dir, generated_names)

    report = {
        "schema_version": 1,
        "workflow": "ppsspp-exact-runtime-hash-replacement",
        "iso_built": False,
        "source_dir": str(args.source_dir.resolve()),
        "output_dir": str(args.output_dir.resolve()),
        "font": str(args.font.resolve()),
        "generated_count": len(generated_names),
        "generated_names": generated_names,
        "text_atlases": results,
        "demo_atlas": demo_result,
        "protected": [
            {
                "name": name,
                "reason": "shared numeric/HUD glyph atlas; Japanese translation is not applicable",
            }
            for name in sorted(PROTECTED_NAMES)
        ],
        "installed": installed,
        "textures_ini": textures_ini,
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
