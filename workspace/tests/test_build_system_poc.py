from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import build_system_poc  # noqa: E402


class BuildSystemPocTests(unittest.TestCase):
    def test_replaces_start_lzs_inside_existing_extent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = build_system_poc.build(
                PROJECT / "workspace" / "config" / "font_profile.json",
                PROJECT / "extracted" / "PSP_GAME" / "USRDIR" / "SYSTEM.DAT",
                PROJECT / "work" / "poc" / "font_visibility" / "start.lzs",
                Path(temporary),
            )
            self.assertEqual(report["replacement"]["entry_name"], "start.lzs")
            self.assertEqual(report["replacement"]["size_delta"], 40)
            self.assertEqual(report["extent"]["original_padding"], 333)
            self.assertEqual(report["extent"]["remaining_padding"], 293)
            self.assertTrue(report["output"]["same_size_as_input"])
            self.assertTrue(
                report["expected_write"]["other_entry_metadata_and_data_preserved"]
            )


if __name__ == "__main__":
    unittest.main()
