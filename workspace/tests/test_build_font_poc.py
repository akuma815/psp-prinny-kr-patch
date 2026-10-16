from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
ROOT = PROJECT.parents[1]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import build_font_poc  # noqa: E402


class BuildFontPocTests(unittest.TestCase):
    def test_build_has_one_declared_unchanged_size_write(self) -> None:
        assets = PROJECT / "work" / "system" / "start_assets"
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            report = build_font_poc.build(
                PROJECT / "workspace" / "config" / "font_profile.json",
                ROOT / "Font" / "HancomMalangMalang-Regular.ttf",
                assets / "font.fnt",
                assets / "font.txp",
                output,
            )
            replacement = report["replacement"]
            self.assertEqual(replacement["cp932_hex"], "8376")
            self.assertEqual(replacement["dense_index"], 533)
            self.assertEqual(replacement["glyph_id"], 371)
            self.assertEqual(replacement["font_txp_write_start"], "0xCB34")
            self.assertEqual(replacement["font_txp_write_end_exclusive"], "0xCBC0")
            self.assertEqual(replacement["declared_write_bytes"], 140)
            self.assertEqual(
                report["source_font"]["missing_modern_hangul_syllables"], 0
            )
            self.assertEqual(
                report["source_font"]["configured_cell_fit_audit"]["checked_syllables"],
                11172,
            )
            self.assertEqual(
                report["source_font"]["configured_cell_fit_audit"]["overflow_count"],
                0,
            )
            self.assertIn("embedding permitted", report["source_font"]["license_status"])
            self.assertTrue(report["outputs"]["font.txp"]["same_size_as_original"])
            self.assertTrue(report["outputs"]["font.fnt"]["byte_identical_to_original"])
            saved = json.loads((output / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["gate_id"], "POC-FONT-VIS-001")


if __name__ == "__main__":
    unittest.main()
