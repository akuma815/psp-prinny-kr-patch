from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import base_talk  # noqa: E402


class BaseTalkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (PROJECT / "work" / "system" / "start_assets" / "BaseTalk.dat").read_bytes()

    def test_observed_file_roundtrips(self) -> None:
        table = base_talk.parse(self.source)
        self.assertEqual(table.to_bytes(), self.source)
        self.assertEqual(table.count, 16)
        self.assertEqual(base_talk.RECORD.size, 52)
        self.assertEqual(
            [record.record_id for record in table.records],
            [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 22, 23, 24, 25, 26, 27],
        )

    def test_rejects_nonzero_footer(self) -> None:
        damaged = bytearray(self.source)
        damaged[-1] = 1
        with self.assertRaisesRegex(ValueError, "non-zero footer"):
            base_talk.parse(bytes(damaged))


if __name__ == "__main__":
    unittest.main()
