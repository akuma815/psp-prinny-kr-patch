from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import demo00  # noqa: E402


class Demo00Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (PROJECT / "work" / "system" / "start_assets" / "Demo00.dat").read_bytes()

    def test_observed_file_roundtrips(self) -> None:
        table = demo00.parse(self.source)
        self.assertEqual(table.to_bytes(), self.source)
        self.assertEqual(len(table.records), 1572)
        self.assertEqual(len(self.source), 207520)
        self.assertEqual(
            hashlib.sha256(self.source).hexdigest(),
            "5db04fe85175e01e14d9abfef5a2817c85c3987c4b76ba33bad39651df60b01d",
        )
        self.assertEqual(table.records[0].record_id, 0x5A)
        self.assertEqual(table.records[0].speaker, "プリニー")
        self.assertEqual(table.records[0].lines[0], "やりごたえバッチリの")

    def test_rejects_nonzero_record_tail(self) -> None:
        damaged = bytearray(self.source)
        damaged[4 + 129] = 1
        with self.assertRaisesRegex(ValueError, "non-zero tail"):
            demo00.parse(bytes(damaged))


if __name__ == "__main__":
    unittest.main()
