import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "demo00_review_queue.py"
SPEC = importlib.util.spec_from_file_location("demo00_review_queue", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class Demo00ReviewQueueTests(unittest.TestCase):
    def test_separates_review_statuses_and_preserves_context(self):
        artifact = {
            "source": {"sha256": "abc"},
            "entries": [
                {
                    "entry_id": "demo00/0001",
                    "coordinates": {"index": 0},
                    "protected": {"source": {"speaker": "A", "lines": ["x"]}},
                    "translation": {
                        "speaker": "가",
                        "lines": ["나"],
                        "status": "needs_review",
                        "notes": "",
                        "flags": [],
                    },
                },
                {
                    "entry_id": "demo00/0002",
                    "coordinates": {"index": 1},
                    "protected": {"source": {"speaker": "B", "lines": ["y"]}},
                    "translation": {
                        "speaker": "다",
                        "lines": ["라"],
                        "status": "complete",
                        "notes": "",
                        "flags": [],
                    },
                },
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            batch_dir = Path(directory)
            (batch_dir / "batch.json").write_text(
                '{"batch_id":"b1","context":{"scene":"scene","evidence":[]},'
                '"entries":[{"entry_id":"demo00/0001"}]}',
                encoding="utf-8",
            )
            queue = MODULE.build_queue(artifact, batch_dir)
        self.assertEqual(queue["counts"]["needs_review"], 1)
        self.assertEqual(queue["counts"]["needs_human_review"], 0)
        self.assertEqual(queue["item_count"], 1)
        self.assertEqual(queue["items"][0]["contexts"][0]["batch_id"], "b1")


if __name__ == "__main__":
    unittest.main()
