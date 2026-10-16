from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import demo00_batches  # noqa: E402


class Demo00BatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.artifact = json.loads(
            (PROJECT / "workspace" / "text" / "demo00_translation.json").read_text(
                encoding="utf-8"
            )
        )

    def make_batch(self) -> dict:
        return demo00_batches.create_batch(
            self.artifact,
            "test_batch",
            ["demo00/005A", "demo00/005B"],
            {"scene": "difficulty selection", "evidence": ["screen"]},
        )

    def test_create_preserves_protected_snapshot(self) -> None:
        batch = self.make_batch()
        self.assertEqual(len(batch["entries"]), 2)
        self.assertEqual(
            batch["entries"][0]["protected_snapshot"],
            self.artifact["entries"][0]["protected"],
        )

    def test_merge_only_applies_translation_and_projects_fit(self) -> None:
        batch = self.make_batch()
        proposed = batch["entries"][0]["proposed_translation"]
        proposed.update({
            "speaker": "프리니",
            "lines": ["도전하는 맛이 확실한", "악마용 난이도임다.", ""],
            "status": "needs_human_review",
            "notes": "말투 검토 필요",
            "flags": ["draft", "speaker_style_review"],
        })
        merged, report = demo00_batches.merge_batch(self.artifact, batch)
        self.assertEqual(
            merged["entries"][0]["protected"], self.artifact["entries"][0]["protected"]
        )
        self.assertEqual(merged["entries"][0]["translation"]["speaker"], "프리니")
        self.assertTrue(report["all_entries_projected_fixed_slot_fit"])
        self.assertFalse(report["build_eligible"])

    def test_merge_rejects_stale_protected_snapshot(self) -> None:
        batch = self.make_batch()
        batch["entries"][0]["protected_snapshot"]["raw_hex"] = "00"
        with self.assertRaisesRegex(ValueError, "protected snapshot is stale"):
            demo00_batches.merge_batch(self.artifact, batch)

    def test_merge_rejects_translation_conflict(self) -> None:
        batch = self.make_batch()
        changed = copy.deepcopy(self.artifact)
        changed["entries"][0]["translation"]["status"] = "in_progress"
        with self.assertRaisesRegex(ValueError, "translation conflict"):
            demo00_batches.merge_batch(changed, batch)


if __name__ == "__main__":
    unittest.main()
