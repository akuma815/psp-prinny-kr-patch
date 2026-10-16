from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import build_start_production  # noqa: E402
from inspect_start_dat import read_entries  # noqa: E402


class BuildStartProductionTests(unittest.TestCase):
    def test_relocates_entries_and_preserves_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            report = build_start_production.build(
                PROJECT / "workspace" / "config" / "demo00_production_profile.json",
                PROJECT / "work" / "system" / "start.dat",
                PROJECT / "work" / "production" / "demo00",
                output,
            )
            _, entries = read_entries(output / "start.dat")
            by_name = {entry.name: entry for entry in entries}
            self.assertEqual(report["output"]["size_delta"], 0)
            self.assertEqual((output / "start.dat").stat().st_size, 9030752)
            self.assertEqual(by_name["font.txp"].span, 328800)
            self.assertEqual(by_name["Demo00.dat"].span, 207520)
            self.assertEqual(report["index"]["relocated_end_offsets"], 0)
            self.assertTrue(report["index"]["all_non_target_payloads_byte_identical"])


if __name__ == "__main__":
    unittest.main()
