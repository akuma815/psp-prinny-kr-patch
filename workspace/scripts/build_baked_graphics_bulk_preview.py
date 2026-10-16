#!/usr/bin/env python3
"""Build first-pass Korean drafts for baked image text without rebuilding an ISO."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def read_existing_aliases(path: Path) -> dict[str, str]:
    """Read PPSSPP [hashes] mappings without disturbing other live previews."""
    if not path.is_file():
        return {}
    aliases: dict[str, str] = {}
    section = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            section = line.lower()
            continue
        if section == "[hashes]" and "=" in line and not line.startswith(("#", ";")):
            key, value = (part.strip() for part in line.split("=", 1))
            if key and value:
                aliases[key] = value
    return aliases


def write_aliases(path: Path, aliases: dict[str, str]) -> None:
    lines = [
        "[options]",
        "version = 1",
        "hash = quick",
        "ignoreAddress = false",
        "",
        "[hashes]",
    ]
    lines.extend(f"{key} = {aliases[key]}" for key in sorted(aliases))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def install_live_previews(
    output_dir: Path,
    jobs: list[tuple[str, str, object, Path, tuple[Path, ...]]],
    config: dict[str, object],
    destination: Path,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    """Install confirmed hashes and alias observed content-hash variants by prefix/size."""
    destination.mkdir(parents=True, exist_ok=True)
    dump_dir = destination / "new"
    assets = {str(item["id"]): item for item in config["assets"]}
    aliases = read_existing_aliases(destination / "textures.ini")
    installed: list[dict[str, object]] = []
    pending: list[dict[str, object]] = []

    for asset_id, name, _builder, _source, _extra in jobs:
        asset = assets[asset_id]
        dump_names = [str(value) for value in asset.get("dump_names", [])]
        if not dump_names:
            pending.append({"id": asset_id, "reason": "runtime-dump-name-unconfirmed"})
            continue

        generated = output_dir / name
        with Image.open(generated) as preview:
            expected_size = preview.size
        canonical = dump_names[0]
        canonical_path = destination / canonical
        shutil.copy2(generated, canonical_path)

        prefixes = {Path(value).stem[:16] for value in dump_names}
        observed: set[str] = set()
        if dump_dir.is_dir():
            for dump_path in dump_dir.glob("*.png"):
                if not any(dump_path.stem.startswith(prefix) for prefix in prefixes):
                    continue
                with Image.open(dump_path) as dump:
                    if dump.size == expected_size:
                        observed.add(dump_path.stem)
        observed.update(Path(value).stem for value in dump_names)
        for hash_name in observed:
            aliases[hash_name] = canonical
        installed.append({
            "id": asset_id,
            "canonical": canonical,
            "size": list(expected_size),
            "alias_count": len(observed),
            "sha256": sha256(canonical_path),
        })

    ini_path = destination / "textures.ini"
    write_aliases(ini_path, aliases)
    ini = {"path": str(ini_path), "alias_count": len(aliases), "sha256": sha256(ini_path)}
    return installed, pending, ini


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size=size)


def clear_alpha(image: Image.Image, box: tuple[int, int, int, int]) -> None:
    image.paste((0, 0, 0, 0), box)


def erase_sign_glyphs(image: Image.Image, box: tuple[int, int, int, int]) -> None:
    """Reconstruct white/red sign glyphs while retaining the wooden texture."""
    x0, y0, x1, y1 = box
    source = image.copy().convert("RGBA")
    pixels = source.load()
    mask = Image.new("L", image.size, 0)
    masked = mask.load()
    for y in range(y0, y1):
        for x in range(x0, x1):
            r, g, b, a = pixels[x, y]
            luminance = (r * 299 + g * 587 + b * 114) // 1000
            if a and (luminance >= 165 or (r >= 145 and r >= g + 35)):
                masked[x, y] = 255
    mask = mask.filter(ImageFilter.MaxFilter(3))
    masked = mask.load()
    out = image.load()
    pending = {
        (x, y)
        for y in range(y0, y1)
        for x in range(x0, x1)
        if masked[x, y]
    }
    while pending:
        updates = []
        for x, y in pending:
            neighbours = [
                out[xx, yy]
                for yy in range(max(y0, y - 1), min(y1, y + 2))
                for xx in range(max(x0, x - 1), min(x1, x + 2))
                if (xx, yy) != (x, y) and (xx, yy) not in pending
            ]
            if neighbours:
                updates.append((
                    x, y,
                    tuple(sum(c[channel] for c in neighbours) // len(neighbours)
                          for channel in range(4)),
                ))
        if not updates:
            break
        for x, y, colour in updates:
            out[x, y] = colour
            pending.remove((x, y))


def centered(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str,
             face: ImageFont.FreeTypeFont, fill, stroke_width: int = 0, stroke_fill=None) -> None:
    x0, y0, x1, y1 = box
    bounds = draw.textbbox((0, 0), text, font=face, stroke_width=stroke_width)
    w = bounds[2] - bounds[0]
    h = bounds[3] - bounds[1]
    x = x0 + (x1 - x0 - w) / 2 - bounds[0]
    y = y0 + (y1 - y0 - h) / 2 - bounds[1]
    draw.text((x, y), text, font=face, fill=fill, stroke_width=stroke_width,
              stroke_fill=stroke_fill)


def erase_text_pixels(
    image: Image.Image,
    box: tuple[int, int, int, int],
    *,
    bright: bool,
    threshold: int,
    dilation: int = 1,
) -> None:
    """Locally reconstruct glyph pixels while retaining the source artwork."""
    x0, y0, x1, y1 = box
    source = image.copy().convert("RGBA")
    pixels = source.load()
    mask = Image.new("L", image.size, 0)
    mp = mask.load()
    for y in range(max(0, y0), min(image.height, y1)):
        for x in range(max(0, x0), min(image.width, x1)):
            r, g, b, a = pixels[x, y]
            lum = (r * 299 + g * 587 + b * 114) // 1000
            if a and ((bright and lum >= threshold) or (not bright and lum <= threshold)):
                mp[x, y] = 255
    if dilation:
        mask = mask.filter(ImageFilter.MaxFilter(dilation * 2 + 1))
    mp = mask.load()
    out = image.load()
    for y in range(max(0, y0), min(image.height, y1)):
        for x in range(max(0, x0), min(image.width, x1)):
            if not mp[x, y]:
                continue
            left = next(
                (xx for xx in range(x - 1, max(x0 - 1, x - 33), -1)
                 if not mp[xx, y]), None
            )
            right = next(
                (xx for xx in range(x + 1, min(x1, x + 33))
                 if not mp[xx, y]), None
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
    predicate,
) -> None:
    """Rebuild a text inset only from accepted source pixels on the same row."""
    x0, y0, x1, y1 = box
    source = image.copy().convert("RGBA")
    out = image.load()
    for y in range(max(0, y0), min(image.height, y1)):
        candidates = [
            source.getpixel((x, y))
            for x in range(max(0, x0), min(image.width, x1))
            if predicate(source.getpixel((x, y)))
        ]
        if not candidates:
            continue
        for offset, x in enumerate(range(max(0, x0), min(image.width, x1))):
            out[x, y] = candidates[offset % len(candidates)]


def build_difficulty(source: Path, output: Path, regular: Path, bold: Path) -> None:
    im = Image.open(source).convert("RGBA")
    # Labels are independent atlas cells; erase only label pixels and keep all icons.
    cells = [
        ((0, 0, 126, 22), "스탠다드", 15),
        ((122, 0, 214, 22), "베이비", 15),
        ((210, 0, 357, 22), "마계 공식 룰", 14),
        ((350, 0, 462, 22), "스탠다드", 15),
    ]
    draw = ImageDraw.Draw(im)
    for box, text, size in cells:
        clear_alpha(im, box)
        draw = ImageDraw.Draw(im)
        centered(draw, box, text, font(bold, size), (244, 229, 191, 255), 2, (115, 71, 28, 255))

    # Rebuild the ribbon face so no Japanese edge pixels survive. The surrounding
    # bat-wing silhouette remains visible and will be checked in the later runtime pass.
    clear_alpha(im, (0, 76, 230, 186))
    draw = ImageDraw.Draw(im)
    ribbon = [(6, 154), (22, 121), (43, 112), (55, 94), (181, 94),
              (190, 105), (220, 120), (198, 136), (190, 158), (43, 158), (19, 172)]
    draw.polygon(ribbon, fill=(220, 191, 137, 255), outline=(72, 42, 21, 255))
    banner_box = (39, 110, 190, 157)
    centered(draw, banner_box, "마계 공인", font(bold, 25), (83, 48, 23, 255))
    im.save(output)


def build_replay(source: Path, output: Path, regular: Path) -> None:
    im = Image.open(source).convert("RGBA")
    # Both Japanese strings are independent transparent sprites.  Clear the
    # complete source cells so no antialiased residue survives.
    clear_alpha(im, (4, 22, 85, 37))
    clear_alpha(im, (4, 38, 79, 52))
    draw = ImageDraw.Draw(im)
    centered(draw, (4, 19, 84, 36), "리플레이 저장", font(regular, 10),
             (249, 245, 245, 255), 1, (38, 28, 42, 255))
    centered(draw, (4, 38, 72, 50), "저장 중…", font(regular, 8),
             (249, 245, 245, 255), 1, (38, 28, 42, 255))
    im.save(output)


def build_enemy_labels(source: Path, output: Path, regular: Path) -> None:
    """Create a readable first-pass label atlas while preserving every icon/HUD cell."""
    im = Image.open(source).convert("RGBA")
    draw = ImageDraw.Draw(im)
    # Preserve the original atlas topology: right-side rows, compact middle
    # cells and the two bottom rows.  The previous draft packed strings into
    # unrelated coordinates and therefore could not map to runtime quads.
    # Clear the actual text cells only.  The old broad middle rectangle erased
    # compass/HUD sprites and caused the translated quads to appear elsewhere.
    for box in [
        (164, 2, 256, 127),
        (43, 68, 160, 81),
        (85, 84, 160, 97),
        (1, 131, 256, 160),
    ]:
        clear_alpha(im, box)
    draw = ImageDraw.Draw(im)
    face = font(regular, 6)
    fill = (238, 68, 100, 255)
    stroke = (39, 18, 27, 255)
    top = [
        ("좀비", "가고일"),
        ("오거", "골렘"),
        ("다크 링", "모브"),
        ("리더 프리니", "가면 병사"),
        ("이그니스", "배트"),
        ("마신", "아사기"),
        ("보스", "아이템"),
    ]
    for row, (left, right) in enumerate(top):
        y = 2 + row * 17
        centered(draw, (164, y, 220, y + 13), left, face, fill, 1, stroke)
        centered(draw, (223, y, 256, y + 13), right, font(regular, 5),
                 fill, 1, stroke)
    middle = [
        ((41, 68, 70, 81), "프리니"),
        ((73, 68, 102, 81), "모브"),
        ((107, 68, 135, 81), "마신"),
        ((138, 68, 160, 81), "보스"),
        ((85, 84, 118, 97), "아이템"),
        ((122, 84, 160, 97), "폭탄"),
    ]
    for box, label in middle:
        centered(draw, box, label, font(regular, 5), fill, 1, stroke)
    bottom = [
        ((0, 130, 67, 143), "프리니"),
        ((70, 130, 132, 143), "프리니 대장"),
        ((139, 130, 202, 143), "프리니 신"),
        ((208, 130, 256, 143), "아사기"),
        ((0, 147, 66, 160), "모브 병사"),
        ((69, 147, 132, 160), "모브 대장"),
        ((139, 147, 202, 160), "다스 모브"),
        ((208, 147, 256, 160), "기절한 적"),
    ]
    for box, label in bottom:
        centered(draw, box, label, font(regular, 5), fill, 1, stroke)
    im.save(output)


def build_stage_result(source: Path, output: Path, bold: Path) -> None:
    im = Image.open(source).convert("RGBA")
    # These are independent sprites on the result atlas, so transparent erasure
    # is safer than painting over the parchment tiles.
    clear_alpha(im, (280, 372, 459, 423))
    clear_alpha(im, (300, 455, 512, 512))
    draw = ImageDraw.Draw(im)
    centered(draw, (282, 378, 454, 417), "스테이지 결과", font(bold, 22),
             (244, 229, 191, 255), 2, (113, 70, 31, 255))
    centered(draw, (305, 466, 505, 507), "클리어 랭크", font(bold, 18),
             (242, 219, 170, 255), 2, (71, 40, 20, 255))
    im.save(output)


def build_protagonist_sign(source: Path, output: Path, regular: Path) -> None:
    im = Image.open(source).convert("RGBA")
    box = (51, 91, 123, 106)
    # Restore only the bright glyph and dark outline pixels from the original
    # wood grain; do not repaint the sign face with a synthetic flat colour.
    restore_text_window(
        im, box,
        lambda p: p[3] and 70 <= p[0] <= 185
        and 30 <= p[1] <= 135 and 25 <= p[2] <= 145,
    )
    centered(ImageDraw.Draw(im), box, "주인공 모집", font(regular, 7),
             (238, 230, 202, 255), 1, (48, 34, 25, 255))
    im.save(output)


def build_end_card(source: Path, output: Path, bold: Path) -> None:
    im = Image.open(source).convert("RGBA")
    clear_alpha(im, (0, 262, 125, 320))
    centered(ImageDraw.Draw(im), (10, 267, 105, 315), "끝", font(bold, 30),
             (205, 151, 61, 255), 1, (73, 42, 22, 255))
    im.save(output)


CREDIT_PAGES = [
    [
        "게임 디자인 / 이즈미 타츠야",
        "캐릭터 디자인 / 하라다 타케히토",
        "메인 프로그래밍 / 나카가와 시게루",
        "음악 / 사토 텐페이",
        "시나리오 / 니이나 카나리",
        "프로그래밍 / 나카노 고·와다 히로노리",
        "나가토모 켄사쿠·이케다 쇼이치",
        "도구 프로그래밍 / 난바·다케우치",
        "2D 캐릭터 디자인 / 모리시타 다이스케",
    ],
    [
        "아트 스태프",
        "이타노·아키노·다케다·히라마쓰",
        "모리타·구보타",
        "3D 맵 디자인 / 오니시 히로시",
        "사사키 미카·시바자키 나나",
        "배경 디자인 / 아트 팀",
        "효과 디자인 / 캐스트",
        "프리니 / 아사기 애니메이션",
        "스위츠남작·마계 캐릭터 팀",
    ],
    [
        "인게임 그래픽",
        "효과·모델·애니메이션 팀",
        "음향 효과 / 사운드 팀",
        "음성 녹음 / 엔지니어 팀",
        "품질 관리 / 디버그 팀",
        "작곡·편곡 / 사토 텐페이",
        "노래 / 아티스트·코러스",
        "협력해 주신 모든 분께 감사드립니다",
    ],
    [
        "주제가·메타모르포제",
        "아사기 마이 러브 / 출연진",
        "로고 디자인 / 제작 스태프",
        "영업·홍보 / 프로모션 팀",
        "기술 지원 / 개발 지원 팀",
        "번역·웹 / 지원 스태프",
        "패키지 디자인 / 제작 팀",
        "소프트웨어 매뉴얼 디자인",
    ],
    [
        "개발 지원·스페셜 땡스",
        "프로젝트를 도와주신 모든 분",
        "애니메이션 제작 스태프",
        "컴퓨터 그래픽·촬영 스태프",
        "협력 회사 및 관계자 여러분",
        "응원해 주신 플레이어 여러분",
        "진심으로 감사드립니다",
    ],
    [
        "NIS America, Inc.",
        "디렉터 / 프로듀서",
        "엔지니어 / 디버그",
        "기획 / 제작",
        "니폰이치 소프트웨어",
        "프리니 스태프",
        "~제가 주인공해도 되겠슴까?~",
    ],
]


def build_credit_page(source: Path, output: Path, regular: Path, page: int) -> None:
    src = Image.open(source).convert("RGBA")
    im = Image.new("RGBA", src.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    lines = CREDIT_PAGES[page]
    face = font(regular, 15 if len(lines) <= 8 else 14)
    line_h = 23
    y = 8
    for line in lines:
        draw.text((7, y), line, font=face, fill=(245, 245, 245, 255),
                  stroke_width=1, stroke_fill=(18, 18, 18, 255))
        y += line_h
    im.save(output)


def build_anime91_tv(source: Path, output: Path, regular: Path, bold: Path) -> None:
    im = Image.open(source).convert("RGBA")
    # Name strips and the news ticker are baked into this scene texture.
    pale = lambda p: p[3] and (p[0] + p[1] + p[2]) // 3 >= 205
    dark_panel = lambda p: p[3] and (p[0] + p[1] + p[2]) // 3 <= 18
    restore_text_window(im, (34, 283, 102, 303), pale)
    restore_text_window(im, (374, 283, 469, 303), pale)
    draw = ImageDraw.Draw(im)
    centered(draw, (0, 278, 108, 307), "우사기", font(bold, 15), (109, 139, 121, 255))
    centered(draw, (372, 278, 510, 307), "플레네르", font(bold, 15), (109, 139, 121, 255))
    restore_text_window(im, (227, 385, 405, 402), dark_panel)
    restore_text_window(im, (234, 405, 405, 428), dark_panel)
    draw = ImageDraw.Draw(im)
    centered(draw, (225, 384, 407, 403), "뉴스 속보", font(regular, 11), (205, 215, 208, 255))
    centered(draw, (232, 405, 407, 430), "프리니 부대 전멸", font(bold, 14), (185, 194, 188, 255))
    im.save(output)


def build_anime91_staff_end(source: Path, output: Path, regular: Path) -> None:
    src = Image.open(source).convert("RGBA")
    im = Image.new("RGBA", src.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    lines = ["[스태프] 이상", "여러 사람과", "여러 회사", "끝."]
    for i, line in enumerate(lines):
        draw.text((5, 4 + i * 27), line, font=font(regular, 20),
                  fill=(75, 4, 8, 255), stroke_width=1, stroke_fill=(12, 0, 0, 255))
    im.save(output)


EPILOGUE = [
    "어둠에 홀린 자들과 온갖 마물이 꿈틀대는 세계, 마계…….",
    "밤이 깊어질수록 세력을 넓히는 마물들은",
    "비명과 피를 흩뿌리며 마계를 무법 지대로 이끈다.",
    "그곳에는 본래 인간이었으나 죽어 마물이 된 자들이 있었다.",
    "―프리니―",
    "가죽 속에는 육체가 없고, 죄지은 인간의 영혼만이 깃든다.",
    "그들이 과거를 씻는 길은 가혹한 노동뿐.",
    "죄를 용서받기 위해 프리니는 고통받으며 계속 일한다.",
    "이것은 사악한 마신을 섬기는 프리니들의",
    "기나긴 하루 이야기이다…….",
]


def build_epilogue(source: Path, output: Path, regular: Path) -> None:
    original = Image.open(source).convert("RGBA")
    im = Image.new("RGBA", original.size, (0, 0, 0, 255))
    draw = ImageDraw.Draw(im)
    face = font(regular, 17)
    line_h = 27
    y = (im.height - line_h * len(EPILOGUE)) // 2
    for line in EPILOGUE:
        centered(draw, (8, y, im.width - 8, y + line_h), line, face, (245, 245, 245, 255))
        y += line_h
    im.save(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--ppsspp-textures", type=Path)
    args = parser.parse_args()
    root = args.project_root.resolve()
    repo = root.parent.parent
    regular = repo / "Font" / "HancomMalangMalang-Regular.ttf"
    bold = repo / "Font" / "HancomMalangMalang-Bold.ttf"
    analysis = root / "work" / "analysis" / "graphics"
    out = root / "work" / "live" / "baked_graphics_bulk" / "generated"
    out.mkdir(parents=True, exist_ok=True)

    config_path = root / "workspace" / "config" / "baked_graphics_bulk.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))

    jobs = [
        ("gfx/start/enemy-label-atlas", "enemy_labels_r73_t00.png", build_enemy_labels,
         analysis / "start_anime" / "anime00_r73_t00.png", (regular,)),
        ("gfx/start/stage-result-atlas", "stage_result_r84_t00.png", build_stage_result,
         analysis / "start_anime" / "anime00_r84_t00.png", (bold,)),
        ("gfx/start/difficulty-labels", "difficulty_r84_t01.png", build_difficulty,
         analysis / "start_anime" / "anime00_r84_t01.png", (regular, bold)),
        ("gfx/start/replay-save", "replay_save_r87_t00.png", build_replay,
         analysis / "start_anime" / "anime00_r87_t00.png", (regular,)),
        ("gfx/anime20/protagonist-recruitment-sign", "protagonist_sign_anime20_r14_t00.png", build_protagonist_sign,
         analysis / "anime" / "anime20_r14_t00.png", (regular,)),
        ("gfx/ending/end-card", "end_card_anime90_r02_t00.png", build_end_card,
         analysis / "anime" / "anime90_r02_t00.png", (bold,)),
        *[
            ("gfx/ending/staff-credits", f"staff_credits_anime90_r03_t{page:02d}.png", build_credit_page,
             analysis / "anime" / f"anime90_r03_t{page:02d}.png", (regular, page))
            for page in range(6)
        ],
        ("gfx/ending/epilogue-prose", "epilogue_anime94_r00_t00.png", build_epilogue,
         analysis / "anime" / "anime94_r00_t00.png", (regular,)),
        ("gfx/anime91/screen-labels", "anime91_tv_labels_r00_t01.png", build_anime91_tv,
         analysis / "anime" / "anime91_r00_t01.png", (regular, bold)),
        ("gfx/anime91/screen-labels", "anime91_staff_end_r00_t03.png", build_anime91_staff_end,
         analysis / "anime" / "anime91_r00_t03.png", (regular,)),
    ]
    report = {"iso_built": False, "generated": [], "installed": [], "pending_live_mapping": []}
    for asset_id, name, builder, source, extra in jobs:
        target = out / name
        builder(source, target, *extra)
        with Image.open(source) as src, Image.open(target) as dst:
            if src.size != dst.size:
                raise RuntimeError(f"dimension changed for {name}: {src.size} -> {dst.size}")
        report["generated"].append({
            "id": asset_id,
            "name": name,
            "source": str(source),
            "sha256": sha256(target),
        })

    if args.ppsspp_textures:
        destination = args.ppsspp_textures.resolve()
        installed, pending, ini = install_live_previews(out, jobs, config, destination)
        report["installed"] = installed
        report["pending_live_mapping"] = pending
        report["textures_ini"] = ini

    report_path = out.parent / "build_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
