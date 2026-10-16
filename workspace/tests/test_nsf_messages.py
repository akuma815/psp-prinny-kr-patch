from __future__ import annotations

import sys
import unittest
from collections import Counter
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import demo00  # noqa: E402
import nsf_links  # noqa: E402
import nsf_messages  # noqa: E402


class NsfMessageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.nsf = nsf_links.parse_nsf((PROJECT / "work" / "script" / "demo.nsf").read_bytes())
        cls.table = demo00.parse(
            (PROJECT / "work" / "system" / "start_assets" / "Demo00.dat").read_bytes()
        )
        cls.references = nsf_messages.scan(cls.nsf, cls.table)

    def test_observed_candidate_population(self) -> None:
        counts = Counter(reference.status for reference in self.references)
        self.assertEqual(counts, {"demo00": 1481, "unresolved": 54, "dynamic": 5})
        self.assertEqual(
            len({reference.message_id for reference in self.references if reference.status == "demo00"}),
            1378,
        )

    def test_first_demo00_reference(self) -> None:
        reference = next(item for item in self.references if item.status == "demo00")
        self.assertEqual(reference.logical_offset, 0x961)
        self.assertEqual(reference.file_offset, 0x3771)
        self.assertEqual(reference.opcode, 1)
        self.assertEqual(reference.message_id, 0x5A)
        self.assertEqual(reference.raw.hex(), "420100015a04e7000000049800000001")


if __name__ == "__main__":
    unittest.main()
