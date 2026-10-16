from __future__ import annotations

import tempfile
import sys
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import build_start_poc  # noqa: E402


class BuildStartPocTests(unittest.TestCase):
    def test_injects_only_fixed_font_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = build_start_poc.build(
                PROJECT / "workspace" / "config" / "font_profile.json",
                PROJECT / "work" / "system" / "start.dat",
                PROJECT / "work" / "poc" / "font_visibility" / "font.txp",
                Path(temporary),
            )
            self.assertEqual(report["replacement"]["entry_name"], "font.txp")
            self.assertEqual(report["replacement"]["entry_start"], "0x5339E0")
            self.assertEqual(report["replacement"]["entry_end_exclusive"], "0x583E40")
            self.assertEqual(report["replacement"]["entry_span"], 328800)
            self.assertEqual(report["replacement"]["actually_changed_bytes"], 79)
            self.assertTrue(report["output"]["same_size_as_input"])


if __name__ == "__main__":
    unittest.main()
