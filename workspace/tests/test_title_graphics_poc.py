import sys
import tempfile
import unittest
import json
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
ROOT = PROJECT.parents[1]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import build_title_graphics_poc  # noqa: E402
import build_title_live_preview  # noqa: E402


class TitleGraphicsPocTests(unittest.TestCase):
    def test_live_calibration_uses_identical_slot_source(self):
        calibration = build_title_live_preview._render_calibration()
        self.assertEqual(calibration.size, (24, 24))
        self.assertEqual(calibration.mode, "RGBA")

    def test_title_uv_slots_use_one_consistent_bold_style(self):
        config = json.loads(
            (PROJECT / "workspace" / "config" / "title_graphics_poc.json").read_text(
                encoding="utf-8"
            )
        )
        title = [block for block in config["blocks"] if block["id"].startswith("gfx/title/name-")]
        self.assertEqual([block["translation"] for block in title], ["프", "리", "니", ""])
        self.assertEqual(
            [block["bounds"] for block in title],
            [[255, 174, 318, 225], [315, 162, 376, 207], [374, 154, 416, 205], [422, 152, 466, 192]],
        )
        self.assertEqual(title[0]["clear_bounds"], [255, 166, 318, 225])
        self.assertEqual(title[2]["clear_bounds"], [374, 154, 422, 205])
        self.assertEqual([block["offset_y"] for block in title], [-5, -6, -4, 0])
        self.assertEqual(
            [block.get("alignment_anchor") for block in title[:3]],
            ["top-of-ㅍ", "top-of-ㅣ", "top-of-ㅣ"],
        )
        self.assertEqual([block.get("anchor_target_y") for block in title[:3]], [181, 161, 159])
        self.assertEqual(title[1]["clear_bounds"], [315, 159, 376, 207])
        self.assertTrue(all(block.get("allow_overflow") for block in title[:3]))
        self.assertEqual({block["font_style"] for block in title}, {"bold"})
        self.assertEqual([block["font_size"] for block in title], [48, 48, 48, 48])
        self.assertEqual({tuple(block["normalize_box"]) for block in title}, {(28, 28)})
        self.assertEqual([block["angle"] for block in title], [18.0, 21.0, 21.0, 15.0])
        self.assertEqual({block["stroke"] for block in title}, {1})
        self.assertEqual(
            {tuple(block["fill_alpha_indices"]) for block in title},
            {(9, 10, 11, 12, 13, 14, 15)},
        )
        self.assertEqual(
            {tuple(block["outline_alpha_indices"]) for block in title},
            {(7, 8, 9, 10, 11)},
        )

        regular = [block for block in config["blocks"] if block not in title]
        self.assertEqual({block["font_style"] for block in regular}, {"regular"})
        subtitle = next(block for block in regular if block["id"].endswith("subtitle"))
        self.assertEqual(subtitle["stroke"], 1)
        self.assertEqual(subtitle["outline_alpha_indices"], [9, 10, 11])
        self.assertEqual(subtitle["live_outline_color"], [32, 24, 40])
        self.assertEqual(subtitle["live_outline_alpha"], 144)
        menus = [block for block in regular if "/menu-" in block["id"]]
        self.assertEqual({block["stroke"] for block in menus}, {1})
        self.assertEqual(
            {tuple(block["outline_alpha_indices"]) for block in menus},
            {(1, 2, 3, 4, 5)},
        )

    def test_supported_production_start_build(self):
        with tempfile.TemporaryDirectory() as directory:
            report = build_title_graphics_poc.build(
                PROJECT / "workspace" / "config" / "title_graphics_poc.json",
                PROJECT / "work" / "builds" / "latest_20260722" / "start" / "start.dat",
                ROOT / "Font" / "HancomMalangMalang-Regular.ttf",
                Path(directory),
            )
        self.assertTrue(report["output"]["same_size_as_input"])
        self.assertTrue(report["expected_write"]["non_target_pixels_preserved"])
        self.assertGreater(report["output"]["changed_bytes"], 0)


if __name__ == "__main__":
    unittest.main()
