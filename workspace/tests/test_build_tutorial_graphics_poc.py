from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
ROOT = PROJECT.parents[1]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import build_tutorial_graphics_poc  # noqa: E402


class TutorialGraphicsPocTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config_path = PROJECT / "workspace" / "config" / "tutorial_graphics_poc.json"
        cls.archive_path = PROJECT / "extracted" / "PSP_GAME" / "USRDIR" / "ANIME.DAT"
        cls.font_path = ROOT / "Font" / "HancomMalangMalang-Regular.ttf"
        cls.config = json.loads(cls.config_path.read_text(encoding="utf-8"))

    def test_translation_inventory_is_complete_and_stable(self):
        textures = self.config["textures"]
        self.assertEqual([item["texture_index"] for item in textures], [0, 1, 2, 3])
        blocks = [block for texture in textures for block in texture["blocks"]]
        self.assertEqual(len(blocks), 61)
        self.assertEqual(len({block["id"] for block in blocks}), 61)
        self.assertTrue(all(block["source"] and block["ko"] for block in blocks))
        self.assertEqual(self.config["font"]["style"], "Regular")

    def test_runtime_spacing_corrections_are_stable(self):
        blocks = {
            block["id"]: block
            for texture in self.config["textures"]
            for block in texture["blocks"]
        }
        self.assertEqual(
            [segment["draw_bounds"] for segment in blocks["tutorial/page1/00"]["segments"]],
            [[161, 1, 292, 23], [289, 0, 304, 24], [338, 0, 353, 24]],
        )
        self.assertEqual(
            [segment.get("font_size") for segment in blocks["tutorial/page1/00"]["segments"]],
            [None, 21, 21],
        )
        self.assertEqual(
            [segment.get("offset_y") for segment in blocks["tutorial/page1/00"]["segments"]],
            [None, -2, -2],
        )
        self.assertEqual(
            [segment["draw_bounds"] for segment in blocks["tutorial/page1/01"]["segments"]],
            [[124, 25, 246, 47], [268, 25, 389, 47]],
        )
        self.assertEqual(blocks["tutorial/page1/06"]["segments"][1]["draw_bounds"][0], 293)
        self.assertEqual(
            [segment["draw_bounds"] for segment in blocks["tutorial/page1/11"]["segments"]],
            [[182, 265, 262, 287], [244, 264, 259, 288], [336, 264, 351, 288]],
        )
        self.assertEqual(
            [segment["draw_bounds"] for segment in blocks["tutorial/page1/12"]["segments"]],
            [[91, 289, 146, 311], [168, 289, 298, 311], [292, 288, 307, 312], [400, 288, 415, 312]],
        )
        self.assertEqual(
            [segment["draw_bounds"] for segment in blocks["tutorial/page1/15"]["segments"][-2:]],
            [[275, 360, 290, 384], [359, 360, 374, 384]],
        )
        self.assertEqual(
            [segment["draw_bounds"] for segment in blocks["tutorial/page1/16"]["segments"][-2:]],
            [[306, 384, 321, 408], [379, 384, 394, 408]],
        )
        self.assertEqual(
            [segment["text"] for segment in blocks["tutorial/page2/02"]["segments"]],
            ["「", "」", "「", "」", "가능!"],
        )
        self.assertEqual(
            [segment["draw_bounds"] for segment in blocks["tutorial/page2/02"]["segments"]],
            [[122, 48, 137, 72], [172, 48, 187, 72], [229, 48, 244, 72], [305, 48, 320, 72], [320, 49, 395, 71]],
        )
        self.assertEqual(blocks["tutorial/page2/10"]["segments"][0]["draw_bounds"], [185, 241, 200, 263])
        self.assertEqual(blocks["tutorial/label/jump"]["draw_bounds"], [0, 0, 64, 24])
        self.assertEqual(blocks["tutorial/label/jump"]["offset_x"], 4)
        self.assertEqual(blocks["tutorial/label/prinny-barrage"]["offset_x"], 4)
        self.assertEqual(blocks["tutorial/label/crouch"]["offset_x"], 4)
        self.assertEqual(
            [segment["draw_bounds"] for segment in blocks["tutorial/page1/15"]["segments"]],
            [[138, 361, 274, 383], [275, 360, 290, 384], [359, 360, 374, 384]],
        )
        self.assertEqual(blocks["tutorial/label/throw"]["draw_bounds"], [0, 264, 48, 288])
        self.assertEqual(blocks["tutorial/label/throw"]["tracking"], -3)
        self.assertEqual(blocks["tutorial/label/shield-counter"]["offset_x"], 4)
        self.assertEqual(
            {
                key: blocks[key]["font_size"]
                for key in (
                    "tutorial/label/slash",
                    "tutorial/label/prinny-barrage",
                    "tutorial/label/crouch",
                    "tutorial/label/stun",
                    "tutorial/label/carry",
                    "tutorial/label/throw",
                )
            },
            {
                "tutorial/label/slash": 19,
                "tutorial/label/prinny-barrage": 19,
                "tutorial/label/crouch": 19,
                "tutorial/label/stun": 19,
                "tutorial/label/carry": 19,
                "tutorial/label/throw": 19,
            },
        )
        self.assertEqual(self.config["sprite_relocations"], [])

    def test_fixed_size_build_and_expected_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = build_tutorial_graphics_poc.build(
                self.config_path,
                self.archive_path,
                self.font_path,
                Path(temporary),
            )
            self.assertTrue(report["output"]["same_size_as_input"])
            self.assertEqual(report["output"]["sha256"], "9b487201baef12e15661f2c956109e1e1ea88fdd392cacc7be8490af276dd2f7")
            self.assertEqual(report["output"]["changed_bytes"], 102778)
            self.assertEqual(
                [item["texture_index"] for item in report["target"]["textures"]],
                [0, 1, 2, 3],
            )
            self.assertTrue(all(report["expected_write"].values()))
            texture_two = next(
                item for item in report["target"]["textures"] if item["texture_index"] == 2
            )
            self.assertEqual(texture_two["sprite_relocations"], [])
            texture_three = next(
                item for item in report["target"]["textures"] if item["texture_index"] == 3
            )
            throw = next(block for block in texture_three["blocks"] if block["id"] == "tutorial/label/throw")
            self.assertEqual(throw["segments"][0]["fitted_font_size"], 19)
            self.assertEqual(throw["segments"][0]["tracking"], -3)
            self.assertLessEqual(throw["segments"][0]["rendered_width"], 48)


if __name__ == "__main__":
    unittest.main()
