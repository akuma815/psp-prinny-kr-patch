from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import font_assets  # noqa: E402


class FontAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        assets = PROJECT / "work" / "system" / "start_assets"
        cls.report = font_assets.analyze(
            (PROJECT / "extracted" / "PSP_GAME" / "SYSDIR" / "BOOT.BIN").read_bytes(),
            (assets / "font.fnt").read_bytes(),
            (assets / "font.txp").read_bytes(),
            (assets / "jis2ucs.bin").read_bytes(),
            (assets / "ucs2jis.bin").read_bytes(),
        )

    def test_font_map_and_texture_cover_same_glyphs(self) -> None:
        mapping = self.report["font_map"]
        texture = self.report["font_texture"]
        self.assertEqual(mapping["entry_count"], 11615)
        self.assertEqual(mapping["glyph_count"], 2348)
        self.assertTrue(mapping["glyph_ids_are_exact_range"])
        self.assertEqual(texture["bytes_per_glyph"], 140)
        self.assertEqual(texture["pixel_bytes"], 2348 * 140)

    def test_conversion_tables_are_canonical_inverses(self) -> None:
        tables = self.report["conversion_tables"]
        self.assertEqual(tables["jis2ucs_assigned"], 7769)
        self.assertEqual(tables["ucs2jis_assigned"], 7766)
        self.assertEqual(tables["canonical_ucs_roundtrips"], 7766)
        self.assertEqual(tables["hangul_syllables_mapped"], 0)

    def test_dense_cp932_index_matches_observed_samples(self) -> None:
        self.assertEqual(font_assets.dense_cp932_index(b"A"), 33)
        self.assertEqual(font_assets.dense_cp932_index(bytes.fromhex("82A0")), 383)
        self.assertEqual(font_assets.dense_cp932_index(bytes.fromhex("8D91")), 2480)
        samples = self.report["font_map"]["samples"]
        self.assertEqual(samples["U+3042"]["glyph_id"], 238)
        self.assertEqual(samples["U+56FD"]["glyph_id"], 1010)

    def test_runtime_cache_fingerprint(self) -> None:
        runtime = self.report["runtime_path"]
        self.assertEqual(runtime["active_glyph_cap_per_page"], 216)
        self.assertEqual(runtime["cache_layout"], "12 columns x 18 rows of 20x14 cells")


if __name__ == "__main__":
    unittest.main()
