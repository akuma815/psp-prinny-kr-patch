#!/usr/bin/env python3
"""Build exact PPSSPP replacements for two runtime UI atlases.

The demo-skip atlas is emitted with one indexed pixel layout and three
different CLUT states.  The game does not draw either label as one rectangle:
it selects six 13x14 glyph cells and places those sprites independently.
Translations must therefore be rendered one Hangul syllable per original
cell.  Drawing a continuous Korean label makes every runtime sprite contain
only a clipped fragment.  All three replacement states use the same opaque
white/black glyph pixels so mixed CLUT sprite selection remains legible.

The deadline/timer atlas has four observed CLUT states.  Only the three
Japanese text bands are cleared and redrawn; numbers and all other pixels are
protected.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


DEMO_PREFIX = "091cd1e0"
# f4cbdbb1 is the first translated runtime atlas.  Once the same record was
# inserted into the native direct-run build, PPSSPP observed a different
# indexed content hash (6ceb80dc).  Both identities reach the same sprite
# consumer and therefore need their own three exact CLUT replacements.
DEMO_CONTENT_HASHES = ("f4cbdbb1", "6ceb80dc")
DEMO_SIZE = (128, 128)
DEMO_TEXT_BOUNDS = (6, 24, 84, 55)
DEMO_CELL_X = 6
DEMO_CELL_WIDTH = 13
DEMO_CELL_ROWS = (
    ((6, 24, 84, 39), "리플레이저장"),
    ((6, 41, 84, 55), "데모스킵  "),
)
DEMO_FILL = (255, 255, 255, 255)
DEMO_STROKE = (12, 12, 12, 255)

TIMER_PREFIX = "09596a50"
TIMER_CONTENT_HASH = "b5a34886"
TIMER_SIZE = (256, 256)
TIMER_TEXT_BANDS = (
    (3, 68, 253, 89),
    (70, 95, 193, 116),
    (3, 125, 114, 146),
)
TIMER_TEXTS = (
    "궁극의 디저트 완성까지",
    "남은 시간",
    "남은 시간",
)

# Each filename contains the observed CLUT address.  The fill/stroke pairs
# retain the visual role of the original Japanese glyphs for that state.
TIMER_STYLES = {
    "564378d0": ((221, 221, 221, 255), (3, 3, 3, 253)),
    "862c2386": ((0, 255, 0, 255), (111, 111, 111, 255)),
    "982610db": ((106, 85, 36, 255), (0, 0, 8, 129)),
    "a8d5f299": ((133, 125, 120, 255), (63, 63, 66, 255)),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def changed_pixel_counts(
    before: Image.Image,
    after: Image.Image,
    allowed_bands: tuple[tuple[int, int, int, int], ...],
) -> tuple[int, int]:
    before_bytes = before.tobytes()
    after_bytes = after.tobytes()
    width, height = before.size
    inside = 0
    outside = 0
    for index in range(width * height):
        offset = index * 4
        if before_bytes[offset : offset + 4] == after_bytes[offset : offset + 4]:
            continue
        x = index % width
        y = index // width
        allowed = any(x0 <= x < x1 and y0 <= y < y1 for x0, y0, x1, y1 in allowed_bands)
        if allowed:
            inside += 1
        else:
            outside += 1
    return inside, outside


def fit_font(
    draw: ImageDraw.ImageDraw,
    font_path: Path,
    text: str,
    bounds: tuple[int, int, int, int],
) -> ImageFont.FreeTypeFont:
    x0, y0, x1, y1 = bounds
    for size in range(18, 9, -1):
        font = ImageFont.truetype(str(font_path), size)
        box = draw.textbbox((0, 0), text, font=font, stroke_width=1)
        if box[2] - box[0] <= x1 - x0 and box[3] - box[1] <= y1 - y0:
            return font
    raise RuntimeError(f"text does not fit {bounds}: {text}")


def draw_centered(
    draw: ImageDraw.ImageDraw,
    font_path: Path,
    text: str,
    bounds: tuple[int, int, int, int],
    fill: tuple[int, int, int, int],
    stroke_fill: tuple[int, int, int, int],
) -> dict[str, object]:
    x0, y0, x1, y1 = bounds
    font = fit_font(draw, font_path, text, bounds)
    box = draw.textbbox((0, 0), text, font=font, stroke_width=1)
    width = box[2] - box[0]
    height = box[3] - box[1]
    x = (x0 + x1 - width) // 2 - box[0]
    y = (y0 + y1 - height) // 2 - box[1]
    draw.text(
        (x, y),
        text,
        font=font,
        fill=fill,
        stroke_width=1,
        stroke_fill=stroke_fill,
    )
    return {
        "text": text,
        "bounds": list(bounds),
        "draw_xy": [x, y],
        "bbox": list(box),
        "font_size": font.size,
        "fill": list(fill),
        "stroke_fill": list(stroke_fill),
    }


def fit_demo_cell_font(
    draw: ImageDraw.ImageDraw,
    font_path: Path,
    characters: str,
    cell_height: int,
) -> ImageFont.FreeTypeFont:
    for size in range(14, 7, -1):
        font = ImageFont.truetype(str(font_path), size)
        if all(
            (
                (box := draw.textbbox((0, 0), character, font=font, stroke_width=1))[2]
                - box[0]
                <= DEMO_CELL_WIDTH
                and box[3] - box[1] <= cell_height
            )
            for character in characters
            if character != " "
        ):
            return font
    raise RuntimeError("demo-skip glyphs do not fit the original sprite cells")


def render_demo_cells(
    image: Image.Image,
    font_path: Path,
) -> list[dict[str, object]]:
    image.paste((0, 0, 0, 0), DEMO_TEXT_BOUNDS)
    draw = ImageDraw.Draw(image)
    rendered: list[dict[str, object]] = []
    for row_bounds, characters in DEMO_CELL_ROWS:
        _, y0, _, y1 = row_bounds
        font = fit_demo_cell_font(draw, font_path, characters, y1 - y0)
        for index, character in enumerate(characters):
            cell = (
                DEMO_CELL_X + index * DEMO_CELL_WIDTH,
                y0,
                DEMO_CELL_X + (index + 1) * DEMO_CELL_WIDTH,
                y1,
            )
            if character == " ":
                continue
            box = draw.textbbox((0, 0), character, font=font, stroke_width=1)
            width = box[2] - box[0]
            height = box[3] - box[1]
            x = (cell[0] + cell[2] - width) // 2 - box[0]
            y = (cell[1] + cell[3] - height) // 2 - box[1]
            draw.text(
                (x, y),
                character,
                font=font,
                fill=DEMO_FILL,
                stroke_width=1,
                stroke_fill=DEMO_STROKE,
            )
            rendered.append(
                {
                    "character": character,
                    "cell_index": index,
                    "cell": list(cell),
                    "draw_xy": [x, y],
                    "font_size": font.size,
                }
            )
    return rendered


def build_demo(
    source_path: Path,
    output_path: Path,
    font_path: Path,
) -> dict[str, object]:
    source = Image.open(source_path).convert("RGBA")
    if source.size != DEMO_SIZE:
        raise ValueError(f"unexpected demo atlas size: {source_path} {source.size}")

    output = source.copy()
    rendered = render_demo_cells(output, font_path)
    changed_inside, changed_outside = changed_pixel_counts(
        source, output, (DEMO_TEXT_BOUNDS,)
    )
    if changed_outside:
        raise RuntimeError(
            f"protected demo pixels changed outside text bounds: {changed_outside}"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.save(output_path)
    return {
        "source": str(source_path.resolve()),
        "output": str(output_path.resolve()),
        "source_sha256": sha256(source_path),
        "output_sha256": sha256(output_path),
        "cell_bounds": list(DEMO_TEXT_BOUNDS),
        "cell_width": DEMO_CELL_WIDTH,
        "rendered": rendered,
        "changed_pixels_inside": changed_inside,
        "changed_pixels_outside": changed_outside,
    }


def timer_style(source_path: Path) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    name = source_path.stem.lower()
    for clut_address, style in TIMER_STYLES.items():
        if clut_address in name:
            return style
    raise ValueError(f"unknown timer CLUT state: {source_path.name}")


def build_timer(source_path: Path, output_path: Path, font_path: Path) -> dict[str, object]:
    source = Image.open(source_path).convert("RGBA")
    if source.size != TIMER_SIZE:
        raise ValueError(f"unexpected timer atlas size: {source_path} {source.size}")

    output = source.copy()
    for bounds in TIMER_TEXT_BANDS:
        output.paste((0, 0, 0, 0), bounds)

    fill, stroke_fill = timer_style(source_path)
    draw = ImageDraw.Draw(output)
    rendered = [
        draw_centered(draw, font_path, text, bounds, fill, stroke_fill)
        for text, bounds in zip(TIMER_TEXTS, TIMER_TEXT_BANDS, strict=True)
    ]

    changed_inside, changed_outside = changed_pixel_counts(source, output, TIMER_TEXT_BANDS)
    if changed_outside:
        raise RuntimeError(
            f"protected timer pixels changed outside text bands: {changed_outside}"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.save(output_path)
    return {
        "source": str(source_path.resolve()),
        "output": str(output_path.resolve()),
        "source_sha256": sha256(source_path),
        "output_sha256": sha256(output_path),
        "changed_pixels_inside": changed_inside,
        "changed_pixels_outside": changed_outside,
        "rendered": rendered,
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
    parser.add_argument("--font", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--install-dir", type=Path)
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument(
        "--demo-only",
        action="store_true",
        help="build/install only the demo-skip variants; leave timer assets untouched",
    )
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    if args.font is None or not args.font.is_file():
        raise SystemExit(f"font not found: {args.font}")

    demo_sources_by_hash = {
        content_hash: sorted(
            args.source_dir.glob(f"{DEMO_PREFIX}*{content_hash}.png")
        )
        for content_hash in DEMO_CONTENT_HASHES
    }
    demo_sources = [
        source
        for content_hash in DEMO_CONTENT_HASHES
        for source in demo_sources_by_hash[content_hash]
    ]
    timer_sources = sorted(args.source_dir.glob(f"{TIMER_PREFIX}*{TIMER_CONTENT_HASH}.png"))
    invalid_demo_counts = {
        content_hash: len(sources)
        for content_hash, sources in demo_sources_by_hash.items()
        if len(sources) != 3
    }
    if invalid_demo_counts:
        raise SystemExit(
            "expected 3 demo CLUT states for every supported content hash, "
            f"found {invalid_demo_counts}"
        )
    if not args.demo_only and len(timer_sources) != 4:
        raise SystemExit(f"expected 4 timer CLUT states, found {len(timer_sources)}")

    demo_results = [
        build_demo(source, args.output_dir / source.name, args.font)
        for source in demo_sources
    ]
    timer_results = []
    if not args.demo_only:
        assert args.font is not None
        timer_results = [
            build_timer(source, args.output_dir / source.name, args.font)
            for source in timer_sources
        ]

    all_sources = demo_sources if args.demo_only else demo_sources + timer_sources
    installed: list[str] = []
    textures_ini = None
    backups: list[str] = []
    if args.install_dir:
        args.install_dir.mkdir(parents=True, exist_ok=True)
        if args.backup_dir:
            args.backup_dir.mkdir(parents=True, exist_ok=True)
            backup_candidates = [
                args.install_dir / source.name for source in all_sources
            ]
            backup_candidates.append(args.install_dir / "textures.ini")
            for current in backup_candidates:
                if not current.is_file():
                    continue
                backup = args.backup_dir / current.name
                if not backup.exists():
                    shutil.copy2(current, backup)
                backups.append(str(backup.resolve()))
        for source in all_sources:
            built = args.output_dir / source.name
            destination = args.install_dir / source.name
            shutil.copy2(built, destination)
            installed.append(str(destination.resolve()))
        textures_ini = merge_texture_aliases(
            args.install_dir, [source.name for source in all_sources]
        )

    report = {
        "status": (
            "PASS: exact demo-skip runtime variants generated; timer skipped"
            if args.demo_only
            else "PASS: exact demo-skip and timer runtime variants generated"
        ),
        "demo_skip": {
            "content_hashes": list(DEMO_CONTENT_HASHES),
            "size": list(DEMO_SIZE),
            "variant_count": len(demo_results),
            "policy": (
                "render one Hangul syllable per original 13x14 sprite cell with "
                "identical opaque white/black pixels in all three CLUT states"
            ),
            "cell_bounds": list(DEMO_TEXT_BOUNDS),
            "cell_width": DEMO_CELL_WIDTH,
            "rows": [characters for _, characters in DEMO_CELL_ROWS],
            "variants": demo_results,
        },
        "timer": {
            "content_hash": TIMER_CONTENT_HASH,
            "size": list(TIMER_SIZE),
            "variant_count": len(timer_results),
            "status": "SKIPPED (--demo-only)" if args.demo_only else "GENERATED",
            "protected_text_bands": [list(bounds) for bounds in TIMER_TEXT_BANDS],
            "translations": list(TIMER_TEXTS),
            "variants": timer_results,
        },
        "installed": installed,
        "backups": backups,
        "textures_ini": textures_ini,
        "iso_built": False,
        "runtime_verification": "PENDING",
        "overlap_resolution": (
            "Runtime screenshot confirms six independent glyph sprites are composed. "
            "Each replacement now carries complete Hangul syllables inside the original "
            "sprite cells, with identical RGBA and alpha pixels in all three states."
        ),
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
