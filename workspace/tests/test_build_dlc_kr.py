from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import build_dlc_kr  # noqa: E402
import didt  # noqa: E402


class BuildDlcKrTests(unittest.TestCase):
    def test_supported_translation_build(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "dlc"
            args = argparse.Namespace(
                input_dir=PROJECT / "original/Prinny DLC",
                translation_dir=PROJECT / "workspace/text/translation/dlc",
                profile=PROJECT / "workspace/config/demo00_production_profile.json",
                reclaim_report=PROJECT / "work/analysis/demo00_boot_ui_fixed_font_reclaim.json",
                base_mapping=PROJECT / "work/builds/direct_run_boot_ui_full_20260729/hangul_mapping.json",
                base_font_fnt=PROJECT / "work/builds/direct_run_boot_ui_full_20260729/font.fnt",
                base_font_txp=PROJECT / "work/builds/direct_run_boot_ui_full_20260729/font.txp",
                source_font=PROJECT.parent.parent / "Font/HancomMalangMalang-Regular.ttf",
                base_direct_run=PROJECT / "work/builds/direct_run_latest",
                output=output,
            )
            report = build_dlc_kr.build(args)
            self.assertEqual(report["font"]["base_entries"], 987)
            self.assertGreaterEqual(report["font"]["added_entries"], 0)
            self.assertEqual(
                report["font"]["final_entries"],
                report["font"]["base_entries"] + report["font"]["added_entries"],
            )
            self.assertEqual(set(report["dlc"]), set(build_dlc_kr.DDEM_FILES))
            with (PROJECT / "workspace/text/translation/dlc/dlc_stage_info.csv").open(
                "r", encoding="utf-8-sig", newline=""
            ) as handle:
                title_rows = {
                    row["dlc_id"]: row
                    for row in csv.DictReader(handle)
                    if row["kind"] == "title"
                }
            for filename in build_dlc_kr.DDEM_FILES:
                source = (PROJECT / "original/Prinny DLC" / filename).read_bytes()
                built = (output / "memstick/PSP/GAME/ULJS00150" / filename).read_bytes()
                self.assertEqual(len(source), len(built))
                self.assertNotEqual(source, built)
                self.assertEqual(didt.parse(built).to_bytes(), built)
                container = didt.parse(built)
                dlc_id = filename[:6].lower()
                mapping_rows = json.loads(
                    (output / "hangul_mapping.json").read_text(encoding="utf-8")
                )["entries"]
                character_map = build_dlc_kr.mapping_from_rows(mapping_rows)
                expected_title = build_dlc_kr.encode_slot(
                    title_rows[dlc_id]["ko"].lstrip("\u3000"),
                    didt.DLC_TITLE_SIZE,
                    character_map,
                    "test title",
                )
                self.assertEqual(container.title_raw, expected_title)
            mapping = json.loads((output / "hangul_mapping.json").read_text(encoding="utf-8"))
            self.assertEqual(mapping["entry_count"], report["font"]["final_entries"])
            self.assertTrue((output / "direct_run/PSP_GAME/USRDIR/SYSTEM.DAT").is_file())


if __name__ == "__main__":
    unittest.main()
