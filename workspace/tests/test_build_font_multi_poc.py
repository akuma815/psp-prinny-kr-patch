from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
ROOT = PROJECT.parents[1]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import build_font_multi_poc  # noqa: E402


class BuildFontMultiPocTests(unittest.TestCase):
    def test_four_declared_unchanged_size_writes(self) -> None:
        assets = PROJECT / "work" / "system" / "start_assets"
        with tempfile.TemporaryDirectory() as temporary:
            report = build_font_multi_poc.build(
                PROJECT / "workspace" / "config" / "font_multi_profile.json",
                ROOT / "Font" / "HancomMalangMalang-Regular.ttf",
                assets / "font.fnt",
                assets / "font.txp",
                Path(temporary),
            )
        self.assertEqual(report["display_probe"]["generated_sequence"], "가각뾰힣")
        self.assertEqual(report["expected_write"]["declared_cells"], 4)
        self.assertEqual(report["expected_write"]["declared_bytes"], 560)
        self.assertTrue(report["expected_write"]["all_changes_within_declared_cells"])
        self.assertTrue(report["outputs"]["font.txp"]["same_size_as_original"])
        self.assertTrue(report["outputs"]["font.fnt"]["byte_identical_to_original"])

    def test_dialog_e2e_builds_nine_declared_cells(self) -> None:
        assets = PROJECT / "work" / "system" / "start_assets"
        with tempfile.TemporaryDirectory() as temporary:
            report = build_font_multi_poc.build(
                PROJECT / "workspace" / "config" / "dialog_e2e_profile.json",
                ROOT / "Font" / "HancomMalangMalang-Regular.ttf",
                assets / "font.fnt",
                assets / "font.txp",
                Path(temporary),
            )
        self.assertEqual(report["display_probe"]["generated_sequence"], "프리니우와지각했다")
        self.assertEqual(report["expected_write"]["declared_cells"], 9)
        self.assertEqual(report["expected_write"]["declared_bytes"], 1260)
        self.assertTrue(report["expected_write"]["all_changes_within_declared_cells"])


if __name__ == "__main__":
    unittest.main()
