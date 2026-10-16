from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import build_system_production  # noqa: E402
from inspect_nispack import read_entries  # noqa: E402


class BuildSystemProductionTests(unittest.TestCase):
    def test_relocates_following_entries_and_preserves_unknowns(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            report = build_system_production.build(
                PROJECT / "workspace" / "config" / "demo00_production_profile.json",
                PROJECT / "extracted" / "PSP_GAME" / "USRDIR" / "SYSTEM.DAT",
                PROJECT / "work" / "production" / "start" / "start.lzs",
                PROJECT / "work" / "production" / "start" / "start.dat",
                output,
            )
            entries = read_entries(output / "SYSTEM.DAT")
            by_name = {entry.name: entry for entry in entries}
            self.assertEqual(by_name["start.lzs"].size, 3672819)
            self.assertEqual(by_name["UMD_PIC1.PNG"].offset % 2048, 0)
            self.assertEqual(report["index"]["moved_entries"], 2)
            self.assertTrue(report["index"]["all_non_target_payloads_byte_identical"])


if __name__ == "__main__":
    unittest.main()
