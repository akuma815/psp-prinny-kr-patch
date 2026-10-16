from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
ROOT = PROJECT.parents[1]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import build_demo00_poc  # noqa: E402
import build_font_multi_poc  # noqa: E402
import build_start_dialog_poc  # noqa: E402


class BuildStartDialogPocTests(unittest.TestCase):
    def test_injects_only_font_and_demo00_entries(self) -> None:
        assets = PROJECT / "work" / "system" / "start_assets"
        profile = PROJECT / "workspace" / "config" / "dialog_e2e_profile.json"
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            build_font_multi_poc.build(
                profile,
                ROOT / "Font" / "HancomMalangMalang-Regular.ttf",
                assets / "font.fnt",
                assets / "font.txp",
                output,
            )
            build_demo00_poc.build(
                profile,
                PROJECT / "workspace" / "text" / "demo00_poc_07d0.json",
                assets / "Demo00.dat",
                output,
            )
            report = build_start_dialog_poc.build(
                profile,
                PROJECT / "work" / "system" / "start.dat",
                output,
                output,
            )
        self.assertEqual(
            {item["entry_name"] for item in report["replacements"]},
            {"font.txp", "Demo00.dat"},
        )
        self.assertTrue(report["output"]["same_size_as_input"])
        self.assertTrue(
            report["expected_write"]["all_changes_inside_configured_entries"]
        )


if __name__ == "__main__":
    unittest.main()
