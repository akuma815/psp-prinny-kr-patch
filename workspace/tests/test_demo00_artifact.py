from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import demo00_artifact  # noqa: E402


class Demo00ArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source_path = PROJECT / "work" / "system" / "start_assets" / "Demo00.dat"
        cls.source = cls.source_path.read_bytes()
        cls.seed_path = PROJECT / "workspace" / "text" / "demo00_poc_07d0.json"
        cls.artifact = demo00_artifact.export_artifact(
            cls.source_path, cls.source, cls.seed_path
        )

    def test_complete_population_roundtrips_byte_identically(self) -> None:
        rebuilt, report = demo00_artifact.validate_and_rebuild(
            self.artifact, self.source
        )
        self.assertEqual(rebuilt, self.source)
        self.assertEqual(report["record_count"], 1572)
        self.assertEqual(report["slot_count"], 6288)
        self.assertTrue(report["source_roundtrip_byte_identical"])

    def test_screen_verified_poc_is_seeded_as_complete(self) -> None:
        entry = self.artifact["entries"][291]
        self.assertEqual(entry["entry_id"], "demo00/07D0")
        self.assertEqual(entry["translation"]["speaker"], "프리니")
        self.assertEqual(entry["translation"]["lines"][0], "우와、지각했다！！")
        self.assertEqual(entry["translation"]["status"], "complete")
        _, report = demo00_artifact.validate_and_rebuild(self.artifact, self.source)
        self.assertEqual(report["status_counts"]["complete"], 1)
        self.assertEqual(report["status_counts"]["untranslated"], 1571)

    def test_rejects_protected_source_tampering(self) -> None:
        damaged = copy.deepcopy(self.artifact)
        damaged["entries"][0]["protected"]["source"]["speaker"] = "변조"
        with self.assertRaisesRegex(ValueError, "source speaker changed"):
            demo00_artifact.validate_and_rebuild(damaged, self.source)

    def test_rejects_target_text_marked_untranslated(self) -> None:
        damaged = copy.deepcopy(self.artifact)
        damaged["entries"][0]["translation"]["speaker"] = "프리니"
        with self.assertRaisesRegex(ValueError, "untranslated entry has target text"):
            demo00_artifact.validate_and_rebuild(damaged, self.source)


if __name__ == "__main__":
    unittest.main()
