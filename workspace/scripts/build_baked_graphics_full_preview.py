#!/usr/bin/env python3
"""Build the remaining first-pass baked-text translations for PPSSPP review.

This deliberately produces replacement PNGs only.  It never rebuilds an ISO.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


MONTAGE_LINES = [
    ["어, 거짓말……", "이런 허술한 주인공이라니……!?"],
    ["누구나 반할 멋진 주인공이", "되고 싶었는데……!"],
    ["역시 여긴 위험해!", "어서 도망치자!"],
    ["그렇구나……", "제법 훌륭하잖아."],
    ["……이제 됐어.", "주인공이 되는 건 포기할래."],
    ["그렇게 말하지 마!", "동료가 곤란할 땐 도와야지!"],
    ["조금만 더 버텨!", "반드시 길을 열겠어!"],
    ["기다려 주세요!!"],
    ["선생님, 정말 고마웠어요.", "이제 안심하고 쉬세요!"],
    ["해냈습니다, 선생님!", "저도 끝까지 해낼게요!"],
    ["뭐야, 이 녀석들은!?", "전부 덤벼!"],
    ["대천사님……", "맞죠……?"],
    ["우리도 끝까지 싸울게요.", "마지막 희망을 지켜야 해!"],
    ["코스튬 대장이 돌아왔다!", "각오해라!"],
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def face(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size=size)


def centered(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str,
             font: ImageFont.FreeTypeFont, fill, stroke_width: int = 0,
             stroke_fill=None) -> None:
    x0, y0, x1, y1 = box
    bounds = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    x = x0 + (x1 - x0 - width) / 2 - bounds[0]
    y = y0 + (y1 - y0 - height) / 2 - bounds[1]
    draw.text((x, y), text, font=font, fill=fill, stroke_width=stroke_width,
              stroke_fill=stroke_fill)


def fitted_face(draw: ImageDraw.ImageDraw, font_path: Path, text: str,
                box: tuple[int, int, int, int], maximum: int,
                minimum: int = 5, stroke_width: int = 0) -> ImageFont.FreeTypeFont:
    """Return the largest font that keeps every translated pixel in ``box``."""
    width = box[2] - box[0]
    height = box[3] - box[1]
    for size in range(maximum, minimum - 1, -1):
        candidate = face(font_path, size)
        bounds = draw.multiline_textbbox(
            (0, 0), text, font=candidate, spacing=1, align="center",
            stroke_width=stroke_width,
        )
        if bounds[2] - bounds[0] <= width and bounds[3] - bounds[1] <= height:
            return candidate
    return face(font_path, minimum)


def fitted_centered(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int],
                    text: str, font_path: Path, maximum: int, fill,
                    minimum: int = 5, stroke_width: int = 0,
                    stroke_fill=None) -> None:
    font = fitted_face(draw, font_path, text, box, maximum, minimum, stroke_width)
    bounds = draw.multiline_textbbox(
        (0, 0), text, font=font, spacing=1, align="center",
        stroke_width=stroke_width,
    )
    x = box[0] + (box[2] - box[0] - (bounds[2] - bounds[0])) / 2 - bounds[0]
    y = box[1] + (box[3] - box[1] - (bounds[3] - bounds[1])) / 2 - bounds[1]
    draw.multiline_text(
        (x, y), text, font=font, fill=fill, spacing=1, align="center",
        stroke_width=stroke_width, stroke_fill=stroke_fill,
    )


def erase_text_pixels(
    image: Image.Image,
    box: tuple[int, int, int, int],
    *,
    bright: bool,
    threshold: int,
    dilation: int = 1,
) -> None:
    """Remove glyph-coloured pixels without replacing the underlying panel.

    The first-pass builders used opaque rectangles, which destroyed portraits,
    bubble outlines and textured panels.  This conservative local reconstruction
    only touches bright/dark glyph pixels inside a tightly scoped text box.
    """
    x0, y0, x1, y1 = box
    source = image.copy().convert("RGBA")
    mask = Image.new("L", image.size, 0)
    pixels = source.load()
    mask_pixels = mask.load()
    for y in range(max(0, y0), min(image.height, y1)):
        for x in range(max(0, x0), min(image.width, x1)):
            r, g, b, a = pixels[x, y]
            luminance = (r * 299 + g * 587 + b * 114) // 1000
            if a and ((bright and luminance >= threshold) or
                      (not bright and luminance <= threshold)):
                mask_pixels[x, y] = 255
    if dilation:
        mask = mask.filter(ImageFilter.MaxFilter(dilation * 2 + 1))
    masked = mask.load()
    out = image.load()
    # Rebuild only glyph pixels from clean pixels on the same scanline.  This
    # retains the source panel's gradients, paper grain and horizontal rules;
    # unlike a solid rectangle it cannot overwrite the surrounding artwork.
    for y in range(max(0, y0), min(image.height, y1)):
        for x in range(max(0, x0), min(image.width, x1)):
            if not masked[x, y]:
                continue
            left = next(
                (xx for xx in range(x - 1, max(x0 - 1, x - 33), -1)
                 if not masked[xx, y]), None
            )
            right = next(
                (xx for xx in range(x + 1, min(x1, x + 33))
                 if not masked[xx, y]), None
            )
            if left is not None and right is not None:
                span = right - left
                a = source.getpixel((left, y))
                b = source.getpixel((right, y))
                out[x, y] = tuple(
                    (a[channel] * (right - x) + b[channel] * (x - left)) // span
                    for channel in range(4)
                )
            elif left is not None:
                out[x, y] = source.getpixel((left, y))
            elif right is not None:
                out[x, y] = source.getpixel((right, y))


def restore_text_window(
    image: Image.Image,
    box: tuple[int, int, int, int],
    *,
    minimum_luminance: int,
) -> None:
    """Rebuild a text inset from its own source paper pixels, row by row.

    Every replacement colour is copied from the same row of the original
    texture.  This keeps scanlines and paper grain while guaranteeing that no
    source glyph survives.  The tightly scoped box never reaches portraits,
    borders or the scene background.
    """
    x0, y0, x1, y1 = box
    source = image.copy().convert("RGBA")
    out = image.load()
    for y in range(max(0, y0), min(image.height, y1)):
        candidates = []
        for x in range(max(0, x0), min(image.width, x1)):
            pixel = source.getpixel((x, y))
            r, g, b, a = pixel
            luminance = (r * 299 + g * 587 + b * 114) // 1000
            if a and luminance >= minimum_luminance:
                candidates.append(pixel)
        if not candidates:
            continue
        for offset, x in enumerate(range(max(0, x0), min(image.width, x1))):
            out[x, y] = candidates[offset % len(candidates)]


def draw_callout(
    image: Image.Image,
    box: tuple[int, int, int, int],
    text: str,
    font_path: Path,
    size: int,
    *,
    bright_text: bool = False,
) -> None:
    erase_text_pixels(image, box, bright=bright_text,
                      threshold=175 if bright_text else 105, dilation=1)
    draw = ImageDraw.Draw(image)
    centered(draw, box, text, face(font_path, size),
             (255, 255, 255, 255) if bright_text else (34, 30, 25, 255),
             1 if bright_text else 0,
             (64, 20, 24, 255) if bright_text else None)


def build_base_menu(source: Path, output: Path, regular: Path) -> None:
    """Rough full-atlas fallback; the validated base-menu builder remains canonical."""
    im = Image.open(source).convert("RGBA")
    draw = ImageDraw.Draw(im)
    labels = [
        ((3, 4, 146, 38), "음악 상점"),
        ((157, 4, 300, 38), "럭키 교수"),
        ((310, 4, 455, 38), "야반도주점"),
        ((3, 52, 146, 86), "기록 상점"),
        ((157, 52, 300, 86), "리플레이 상점"),
        ((3, 101, 146, 135), "시공의 나그네"),
        ((157, 101, 300, 135), "저장 상점"),
        ((3, 150, 146, 184), "난이도 설정"),
        ((157, 150, 300, 184), "튜토리얼 상점"),
    ]
    for box, text in labels:
        draw.rectangle(box, fill=(91, 54, 29, 255))
        centered(draw, box, text, face(regular, 17), (248, 246, 238, 255),
                 1, (35, 24, 28, 255))
    # Clear and rebuild the compact list copies.
    draw.rectangle((0, 192, 225, 255), fill=(0, 0, 0, 0))
    draw.rectangle((356, 188, 512, 256), fill=(0, 0, 0, 0))
    compact = ["야반도주점", "럭키 교수", "리플레이 상점", "저장 상점", "튜토리얼 상점"]
    for index, text in enumerate(compact):
        draw.text((2, 193 + index * 12), text, font=face(regular, 10),
                  fill=(248, 246, 238, 255), stroke_width=1,
                  stroke_fill=(35, 24, 28, 255))
        draw.text((362, 193 + index * 12), text, font=face(regular, 10),
                  fill=(248, 246, 238, 255), stroke_width=1,
                  stroke_fill=(35, 24, 28, 255))
    im.save(output)


def build_system1(source: Path, output: Path, regular: Path, bold: Path) -> None:
    """Keep this shared English glyph atlas unchanged per reviewer decision."""
    Image.open(source).convert("RGBA").save(output)


def build_trial_warning(source: Path, output: Path, regular: Path) -> None:
    im = Image.open(source).convert("RGBA")
    draw = ImageDraw.Draw(im)
    draw.rectangle((35, 64, 455, 203), fill=(16, 16, 16, 255))
    lines = [
        "이 소프트웨어는 체험판입니다.",
        "제품판과 사양이 다르며 예기치 않은 문제가",
        "발생하거나 정상적으로 동작하지 않을 수 있습니다.",
        "조작 방법과 제품판 사양은 달라질 수 있습니다.",
        "미리 양해해 주십시오.",
    ]
    font = face(regular, 17)
    for row, text in enumerate(lines):
        draw.text((54, 75 + row * 24), text, font=font, fill=(245, 245, 245, 255))
    im.save(output)


def build_trial_controls(source: Path, output: Path, regular: Path, bold: Path) -> None:
    im = Image.open(source).convert("RGBA")
    dark = (34, 30, 25, 255)
    white = (255, 255, 255, 255)
    draw_callout(im, (190, 9, 290, 29), "조작 설명", bold, 11,
                 bright_text=True)
    callouts = [
        ((88, 43, 175, 63), "미사용", 8),
        ((205, 33, 312, 70), "R+방향키\n화면 이동", 7),
        ((350, 40, 436, 66), "들기·던지기", 8),
        ((18, 69, 117, 91), "프리니 이동", 8),
        ((369, 87, 456, 112), "프리니 회전", 8),
        ((18, 141, 112, 160), "미사용", 9),
        ((384, 127, 456, 154), "점프", 9),
        ((349, 166, 468, 204), "베기 공격\n공중: 프리니 연사", 7),
        ((106, 182, 234, 207), "시스템 메뉴 표시", 7),
        ((252, 182, 337, 206), "미사용", 8),
    ]
    for box, text, size in callouts:
        erase_text_pixels(im, box, bright=False, threshold=105, dilation=1)
        draw = ImageDraw.Draw(im)
        fitted_centered(draw, box, text, regular, size, dark)
    # Blue button-name pills contain white text.
    pills = [
        ((149, 58, 190, 78), "L", 8),
        ((282, 59, 324, 78), "R", 8),
        ((337, 61, 374, 80), "△", 8),
        ((359, 80, 394, 99), "○", 8),
        ((82, 87, 135, 107), "방향키", 7),
        ((57, 124, 114, 145), "아날로그", 6),
        ((351, 109, 392, 128), "×", 8),
        ((350, 146, 392, 166), "○", 8),
        ((165, 165, 240, 184), "SELECT", 6),
        ((250, 165, 329, 184), "START", 6),
    ]
    for box, text, size in pills:
        erase_text_pixels(im, box, bright=True, threshold=175, dilation=1)
        draw = ImageDraw.Draw(im)
        fitted_centered(draw, box, text, regular, size, white,
                        stroke_width=1, stroke_fill=(15, 74, 102, 255))

    draw_callout(im, (23, 207, 454, 226), "특수 액션", bold, 9,
                 bright_text=True)
    erase_text_pixels(im, (23, 230, 454, 247),
                      bright=False, threshold=105, dilation=1)
    draw = ImageDraw.Draw(im)
    fitted_centered(draw, (23, 230, 454, 247),
                    "대시   ○를 누른 채 방향키 좌우",
                    regular, 8, dark)
    erase_text_pixels(im, (23, 248, 454, 264),
                      bright=False, threshold=105, dilation=1)
    draw = ImageDraw.Draw(im)
    fitted_centered(draw, (23, 248, 454, 264),
                    "엉덩이 찍기   공중에서 방향키 아래+○",
                    regular, 8, dark)
    im.save(output)


def build_trial_thanks(source: Path, output: Path, regular: Path, bold: Path) -> None:
    im = Image.open(source).convert("RGBA")
    # Remove only the original white glyphs; the illustration and dark patterned
    # background remain byte-local instead of being covered by an opaque panel.
    # The company mark occupies x=438..475 at the top.  Split the erase range
    # so it remains untouched.
    erase_text_pixels(im, (179, 10, 433, 34), bright=True, threshold=155, dilation=2)
    erase_text_pixels(im, (179, 34, 473, 198), bright=True, threshold=155, dilation=2)
    draw = ImageDraw.Draw(im)
    lines = [
        "체험판을 플레이해 주셔서",
        "감사합니다.",
        "",
        "이번 체험판에서는 액션 게임의",
        "재미를 맛볼 수 있도록",
        "여러 난이도의 스테이지를",
        "준비했습니다.",
        "",
        "제품판도 기대해 주세요!",
    ]
    for row, text in enumerate(lines):
        font = face(bold if row in (0, 1, 8) else regular, 13)
        draw.text((186, 15 + row * 20), text, font=font,
                  fill=(250, 250, 250, 255), stroke_width=2,
                  stroke_fill=(15, 18, 28, 255))
    erase_text_pixels(im, (184, 203, 468, 261),
                      bright=False, threshold=105, dilation=1)
    centered(draw, (188, 207, 464, 225),
             "프리니 ~제가 주인공해도 되겠슴까?~",
             face(bold, 11), (35, 40, 48, 255))
    centered(draw, (188, 227, 464, 243), "출시일: 2008년 11월 20일",
             face(regular, 9), (46, 50, 56, 255))
    centered(draw, (188, 244, 464, 260), "가격: 4,980엔",
             face(regular, 9), (46, 50, 56, 255))
    im.save(output)


MONTAGE_TEXT_BOXES = [
    (158, 66, 394, 108), (158, 65, 402, 108),
    (204, 66, 392, 108), (230, 65, 402, 108),
    (159, 66, 403, 108), (190, 64, 412, 108),
    (169, 65, 399, 108), (230, 66, 395, 106),
    (159, 66, 400, 108), (159, 65, 402, 108),
    (160, 66, 394, 108), (205, 65, 398, 108),
    (160, 65, 403, 108), (198, 65, 404, 108),
]

MONTAGE_NAME_BOXES = [
    (158, 35, 226, 63), (158, 35, 226, 63),
    (204, 35, 272, 63), (204, 35, 272, 63),
    (159, 35, 227, 63), (198, 34, 267, 63),
    (169, 22, 232, 48), (229, 34, 297, 63),
    (159, 35, 227, 63), (159, 35, 227, 63),
    (158, 35, 226, 63), (204, 35, 272, 63),
    (158, 35, 226, 63), (198, 34, 250, 63),
]


def build_montage_frame(source: Path, output: Path, regular: Path,
                        lines: list[str], index: int) -> None:
    """Replace the baked dialogue inside an ending montage screenshot."""
    im = Image.open(source).convert("RGBA")
    box = MONTAGE_TEXT_BOXES[index - 10]
    name_box = MONTAGE_NAME_BOXES[index - 10]
    # Several montage frames start their first Japanese line above the measured
    # Korean layout box.  Rebuild that whole source-text band, then paste the
    # untouched name plate back so its irregular border is preserved exactly.
    name_plate = im.crop(name_box)
    source_text_box = (max(0, box[0] - 4), 40, box[2], box[3])
    restore_text_window(im, source_text_box, minimum_luminance=195)
    im.paste(name_plate, name_box[:2], name_plate)
    # The name plate is a separate outlined bubble.  Touch only its inset glyph
    # area, never the full plate bounds.
    name_glyph_box = (
        name_box[0] + 6, name_box[1] + 4,
        name_box[2] - 6, name_box[3] - 5,
    )
    restore_text_window(im, name_glyph_box, minimum_luminance=175)
    draw = ImageDraw.Draw(im)
    centered(draw, name_glyph_box, "아사기", face(regular, 9), (58, 42, 30, 255))
    fitted_centered(draw, box, "\n".join(lines), regular,
                    13 if len(lines) == 1 else 12,
                    (58, 42, 30, 255), minimum=8)
    im.save(output)


def make_contact_sheet(paths: list[Path], output: Path) -> None:
    thumb_width = 240
    label_height = 22
    columns = 4
    thumbs: list[tuple[str, Image.Image]] = []
    max_height = 1
    for path in paths:
        image = Image.open(path).convert("RGBA")
        scale = min(1.0, thumb_width / image.width)
        size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
        thumb = image.resize(size, Image.Resampling.NEAREST)
        max_height = max(max_height, thumb.height)
        thumbs.append((path.name, thumb))
    rows = (len(thumbs) + columns - 1) // columns
    sheet = Image.new("RGBA", (thumb_width * columns, (max_height + label_height) * rows),
                      (34, 37, 43, 255))
    draw = ImageDraw.Draw(sheet)
    label_font = ImageFont.load_default()
    for index, (name, thumb) in enumerate(thumbs):
        x = (index % columns) * thumb_width
        y = (index // columns) * (max_height + label_height)
        sheet.alpha_composite(thumb, (x + (thumb_width - thumb.width) // 2, y + label_height))
        draw.text((x + 4, y + 4), name, fill=(255, 255, 255, 255), font=label_font)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.project_root.resolve()
    repo = root.parent.parent
    regular = repo / "Font" / "HancomMalangMalang-Regular.ttf"
    bold = repo / "Font" / "HancomMalangMalang-Bold.ttf"
    analysis = root / "work" / "analysis" / "graphics"
    output_dir = root / "work" / "live" / "baked_graphics_full" / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)

    jobs: list[tuple[str, Path, Path, object, tuple[object, ...]]] = [
        ("start.dat/system1.txp",
         analysis / "start" / "system1.png",
         output_dir / "start_system1_ui.png",
         build_system1, (regular, bold)),
        ("start.dat/anime00.dat/record-82/texture-0",
         analysis / "start_anime" / "anime00_r82_t00.png",
         output_dir / "start_anime00_r82_t00_base_menu.png",
         build_base_menu, (regular,)),
        ("BG.DAT/bg9801.txp", analysis / "bg" / "bg9801.png",
         output_dir / "bg9801_trial_warning.png", build_trial_warning, (regular,)),
        ("BG.DAT/bg9802.txp", analysis / "bg" / "bg9802.png",
         output_dir / "bg9802_trial_controls.png", build_trial_controls, (regular, bold)),
        ("BG.DAT/bg9803.txp", analysis / "bg" / "bg9803.png",
         output_dir / "bg9803_trial_thanks.png", build_trial_thanks, (regular, bold)),
    ]

    for anime in ("anime92", "anime93"):
        # Both archives contain their own consumer copies of the same montage.
        for index, lines in enumerate(MONTAGE_LINES, start=10):
            jobs.append((
                f"ANIME.DAT/{anime}.dat/record-{'1' if anime == 'anime92' else '2'}/texture-{index}",
                analysis / "anime" / f"{anime}_r{'01' if anime == 'anime92' else '02'}_t{index:02d}.png",
                output_dir / f"{anime}_montage_t{index:02d}.png",
                build_montage_frame, (regular, lines, index),
            ))

    report: dict[str, object] = {
        "schema_version": 1,
        "iso_built": False,
        "workflow": "PPSSPP replacement texture",
        "generated": [],
    }
    for asset_id, source, output, builder, extra in jobs:
        if not source.is_file():
            raise FileNotFoundError(source)
        builder(source, output, *extra)
        with Image.open(source) as src, Image.open(output) as dst:
            if src.size != dst.size:
                raise RuntimeError(f"dimension changed: {source.name}: {src.size} -> {dst.size}")
            size = list(src.size)
        report["generated"].append({
            "asset_id": asset_id,
            "source": str(source),
            "output": str(output),
            "dimensions": size,
            "sha256": sha256(output),
        })

    report_path = output_dir.parent / "build_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    bulk_dir = root / "work" / "live" / "baked_graphics_bulk" / "generated"
    all_outputs = sorted(bulk_dir.glob("*.png")) + sorted(output_dir.glob("*.png"))
    make_contact_sheet(all_outputs, output_dir.parent / "first_pass_all_contact_sheet.png")
    print(json.dumps({"generated": len(jobs), "report": str(report_path)},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
