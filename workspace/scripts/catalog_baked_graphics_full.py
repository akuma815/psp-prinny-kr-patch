#!/usr/bin/env python3
"""Create a denominator-preserving 949-item baked-graphics review catalog."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


TARGETS = {
    "start.dat/system1.txp": "고정 영문 UI 문구(Level UP·Now Loading)",
    "start.dat/anime00.dat/record-73/texture-0": "적/HUD 명칭 아틀라스",
    "start.dat/anime00.dat/record-78/texture-0": "타이틀 로고·메뉴",
    "start.dat/anime00.dat/record-82/texture-0": "거점 메뉴",
    "start.dat/anime00.dat/record-84/texture-0": "스테이지 결과",
    "start.dat/anime00.dat/record-84/texture-1": "난이도 장식",
    "start.dat/anime00.dat/record-87/texture-0": "리플레이 저장",
    "ANIME.DAT/anime20.dat/record-14/texture-0": "주인공 모집 간판",
    "ANIME.DAT/anime90.dat/record-2/texture-0": "끝 표기",
    "ANIME.DAT/anime91.dat/record-0/texture-1": "TV 화면·이름표",
    "ANIME.DAT/anime91.dat/record-0/texture-3": "스태프 종료 문구",
    "ANIME.DAT/anime94.dat/record-0/texture-0": "에필로그",
    "ANIME.DAT/anime96.dat/record-0/texture-0": "에필로그 중복 소비본",
    "BG.DAT/bg9801.txp": "체험판 경고",
    "BG.DAT/bg9802.txp": "체험판 조작 설명",
    "BG.DAT/bg9803.txp": "체험판 종료 안내",
}
for texture in range(4):
    TARGETS[f"ANIME.DAT/anime12.dat/record-0/texture-{texture}"] = \
        "튜토리얼 본문·강조어(기존 교체 텍스처 확정본)"

for archive, record in (("anime92", 1), ("anime93", 2)):
    for texture in range(10, 24):
        TARGETS[f"ANIME.DAT/{archive}.dat/record-{record}/texture-{texture}"] = \
            "엔딩 몽타주 내장 대사"
for archive in ("anime90", "anime92", "anime93"):
    record = 3 if archive == "anime90" else (0 if archive == "anime92" else 1)
    for texture in range(6):
        TARGETS[f"ANIME.DAT/{archive}.dat/record-{record}/texture-{texture}"] = \
            "스태프 롤 중복 소비본"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.project_root.resolve()
    source_path = root / "work" / "analysis" / "graphics" / "txp_inventory.json"
    inventory = json.loads(source_path.read_text(encoding="utf-8"))
    rows = []
    for entry in inventory["entries"]:
        asset_id = str(entry["asset_id"])
        if asset_id in TARGETS:
            classification = "target"
            reason = TARGETS[asset_id]
        else:
            classification = "non_target"
            reason = "전수 접촉 시트 검토: 배경·캐릭터·이펙트·영문/숫자 전용 또는 텍스트 없음"
        rows.append({
            "asset_id": asset_id,
            "classification": classification,
            "reason": reason,
            "preview": entry["preview"],
            "width": entry["width"],
            "height": entry["height"],
            "source_sha256": entry.get("sha256"),
        })

    target_count = sum(row["classification"] == "target" for row in rows)
    catalog = {
        "schema_version": 1,
        "denominator": inventory["total"],
        "counts": {
            "target": target_count,
            "non_target": len(rows) - target_count,
            "unknown": 0,
        },
        "policy": {
            "japanese_baked_text": "target",
            "fixed_player_facing_english": "target",
            "reusable_alphabet_numeric_and_stat_atlas": "non_target; runtime 조합용 아틀라스",
            "debug_and_trial": "trial Japanese text retained as target; pure debug markers non_target",
        },
        "entries": rows,
    }
    output = root / "work" / "analysis" / "graphics" / "baked_text_full_catalog.json"
    output.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print(json.dumps({"denominator": len(rows), "target": target_count,
                      "non_target": len(rows) - target_count, "output": str(output)},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
