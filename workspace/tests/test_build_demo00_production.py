from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import build_demo00_production  # noqa: E402
import demo00  # noqa: E402


class BuildDemo00ProductionTests(unittest.TestCase):
    def test_supported_revision_build(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            report = build_demo00_production.build(
                PROJECT / "workspace" / "config" / "demo00_production_profile.json",
                PROJECT / "workspace" / "text" / "demo00_translation.json",
                PROJECT / "work" / "analysis" / "demo00_fixed_font_reclaim.json",
                PROJECT.parents[1] / "Font" / "HancomMalangMalang-Regular.ttf",
                PROJECT / "work" / "system" / "start_assets" / "font.fnt",
                PROJECT / "work" / "system" / "start_assets" / "font.txp",
                PROJECT / "work" / "system" / "start_assets" / "Demo00.dat",
                output,
            )
            self.assertEqual(report["demand"]["complete_entries"], 1523)
            self.assertEqual(report["demand"]["hangul_syllables"], 831)
            self.assertEqual(report["allocation"]["first_code"], "F040")
            self.assertEqual(report["allocation"]["last_code"], "F4BF")
            self.assertEqual(report["allocation"]["source_text_conflicts_skipped"], 63)
            self.assertEqual(report["outputs"]["font.txp"]["expanded_glyphs"], 2348)
            self.assertEqual(report["outputs"]["font.txp"]["height"], 32872)
            self.assertEqual((output / "font.txp").stat().st_size, 328800)
            self.assertEqual((output / "Demo00.dat").stat().st_size, 207520)
            self.assertEqual(demo00.parse((output / "Demo00.dat").read_bytes()).to_bytes(), (output / "Demo00.dat").read_bytes())
            mapping = json.loads((output / "hangul_mapping.json").read_text(encoding="utf-8"))
            self.assertEqual(mapping["entry_count"], 831)
            fnt = (output / "font.fnt").read_bytes()
            count, = struct.unpack_from("<H", fnt)
            values = struct.unpack_from(f"<{count}H", fnt, 2)
            self.assertEqual(set(values), set(range(2348)))
            self.assertTrue((output / "hangul_preview.png").is_file())

    def test_encoder_rejects_unmapped_character(self) -> None:
        with self.assertRaisesRegex(ValueError, "unmapped character"):
            build_demo00_production.encode_text("🙂", {})


if __name__ == "__main__":
    unittest.main()
