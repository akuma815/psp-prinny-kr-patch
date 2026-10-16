from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
SCRIPTS = PROJECT / "workspace" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import build_boot_ui_runtime_patch as runtime_patch


class BootUiRuntimePatchTests(unittest.TestCase):
    def test_checked_in_artifact_and_generated_candidate(self) -> None:
        args = type("Args", (), {
            "profile": PROJECT / "workspace/config/demo00_production_profile.json",
            "artifact": PROJECT / "workspace/text/boot_ui_translation.json",
            "reclaim_report": PROJECT / "work/analysis/demo00_boot_ui_fixed_font_reclaim.json",
            "source_font": PROJECT.parents[1] / "Font/HancomMalangMalang-Regular.ttf",
            "font_fnt": PROJECT / "work/production/demo00/font.fnt",
            "font_txp": PROJECT / "work/production/demo00/font.txp",
            "base_mapping": PROJECT / "work/production/demo00/hangul_mapping.json",
            "boot_bin": PROJECT / "extracted/PSP_GAME/SYSDIR/BOOT.BIN",
        })()
        with tempfile.TemporaryDirectory() as temporary:
            args.output = Path(temporary)
            report = runtime_patch.build(args)
            self.assertEqual(report["status"], "PASS")
            artifact = json.loads(args.artifact.read_text(encoding="utf-8"))
            self.assertEqual(
                report["output_boot"]["patched_slots"],
                len(artifact["entries"]),
            )
            self.assertEqual(report["font"]["base_mapping_entries"], 831)
            self.assertGreater(report["font"]["new_hangul"], 0)
            self.assertEqual(
                report["font"]["combined_mapping_entries"],
                report["font"]["base_mapping_entries"]
                + report["font"]["new_hangul"],
            )
            self.assertEqual((args.output / "BOOT.BIN").read_bytes()[:4], b"\x7fELF")
            self.assertEqual(
                (args.output / "BOOT.BIN").read_bytes(),
                (args.output / "EBOOT.BIN").read_bytes(),
            )
            mapping = json.loads(
                (args.output / "hangul_mapping.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                mapping["entry_count"],
                report["font"]["combined_mapping_entries"],
            )


if __name__ == "__main__":
    unittest.main()
