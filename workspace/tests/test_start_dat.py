from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

from inspect_start_dat import read_entries  # noqa: E402


class StartDatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.archive = PROJECT / "work" / "system" / "start.dat"
        cls.marker, cls.entries = read_entries(cls.archive)

    def test_index_is_contiguous_and_ends_at_eof(self) -> None:
        self.assertEqual(self.entries[0].data_start, self.marker)
        for previous, current in zip(self.entries, self.entries[1:]):
            self.assertEqual(previous.data_end, current.data_start)
        self.assertEqual(self.entries[-1].data_end, self.archive.stat().st_size)

    def test_basetalk_observed_span(self) -> None:
        entry = next(item for item in self.entries if item.name == "BaseTalk.dat")
        self.assertEqual(entry.data_start, 0x0078C260)
        self.assertEqual(entry.data_end, 0x0078C5B0)
        self.assertEqual(entry.span, 848)


if __name__ == "__main__":
    unittest.main()
