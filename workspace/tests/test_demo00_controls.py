from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import demo00_controls  # noqa: E402


class Demo00ControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = demo00_controls.analyze(
            PROJECT / "work" / "system" / "start_assets" / "Demo00.dat",
            PROJECT / "work" / "system" / "start.dat",
        )

    def test_observed_controls_validate(self) -> None:
        demo00_controls.validate(self.report)
        self.assertEqual(self.report["record_count"], 1572)

    def test_all_signed_face_ids_resolve(self) -> None:
        face = self.report["face_asset_signed"]
        self.assertEqual(face["unique_nonzero_asset_ids"], 120)
        self.assertEqual(face["matched_start_assets"], 120)
        self.assertEqual(face["missing_start_assets"], [])

    def test_speaker_styles_are_exact_length_tiers(self) -> None:
        speaker = self.report["speaker_box_style"]
        self.assertEqual(
            speaker["observed_counts"],
            {"0": 182, "200": 1048, "201": 310, "202": 32},
        )
        self.assertEqual(speaker["validation_errors"], [])


if __name__ == "__main__":
    unittest.main()
