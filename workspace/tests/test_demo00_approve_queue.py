import copy
import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "demo00_approve_queue.py"
SPEC = importlib.util.spec_from_file_location("demo00_approve_queue", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class Demo00ApproveQueueTests(unittest.TestCase):
    def fixture(self):
        translation = {
            "speaker": "프리니",
            "lines": ["검토임다", "", ""],
            "status": "needs_human_review",
            "notes": "초벌.",
            "flags": [
                "draft",
                "term_review_required",
                "referent_review_required",
                "consumer_review_required",
            ],
        }
        artifact = {
            "source": {"sha256": "abc"},
            "entries": [{"entry_id": "demo00/0001", "translation": translation}],
        }
        queue = {
            "source_identity": {"sha256": "abc"},
            "item_count": 1,
            "items": [
                {"entry_id": "demo00/0001", "translation": copy.deepcopy(translation)}
            ],
        }
        terminology = {
            "decisions": [{"decision_id": "T1", "status": "needs_human_review"}]
        }
        return artifact, queue, terminology

    def test_approves_exact_snapshot_and_preserves_technical_review(self):
        artifact, queue, terminology = self.fixture()
        report = MODULE.approve_snapshot(artifact, queue, terminology, "2026-07-18")
        translation = artifact["entries"][0]["translation"]
        self.assertEqual(translation["status"], "complete")
        self.assertNotIn("draft", translation["flags"])
        self.assertNotIn("term_review_required", translation["flags"])
        self.assertNotIn("referent_review_required", translation["flags"])
        self.assertIn("consumer_review_required", translation["flags"])
        self.assertIn("user_approved", translation["flags"])
        self.assertEqual(terminology["decisions"][0]["status"], "approved")
        self.assertEqual(report["approved_entry_count"], 1)

    def test_rejects_stale_queue_translation(self):
        artifact, queue, terminology = self.fixture()
        artifact["entries"][0]["translation"]["lines"][0] = "변경됨"
        with self.assertRaisesRegex(ValueError, "stale queue translation"):
            MODULE.approve_snapshot(artifact, queue, terminology, "2026-07-18")


if __name__ == "__main__":
    unittest.main()
