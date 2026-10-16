from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
SCRIPTS = PROJECT / "workspace" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import build_boot_ui_exact_length_control as control


class BootUiExactLengthControlTests(unittest.TestCase):
    def test_changes_only_targets_and_matches_source_bytes(self) -> None:
        source = PROJECT / "workspace/text/boot_ui_translation.json"
        source_before = source.read_bytes()
        original = json.loads(source_before.decode("utf-8"))

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "control.json"
            report_path = root / "report.json"
            report = control.build(source, output, report_path)
            candidate = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(source.read_bytes(), source_before)
        self.assertTrue(report["canonical_unchanged"])
        self.assertEqual(report["changed_entries"], 4)
        original_by_offset = {
            entry["offset"]: entry for entry in original["entries"]
        }
        candidate_by_offset = {
            entry["offset"]: entry for entry in candidate["entries"]
        }
        self.assertEqual(set(original_by_offset), set(candidate_by_offset))

        changed = []
        for offset, entry in candidate_by_offset.items():
            before = original_by_offset[offset]["translation"]
            after = entry["translation"]
            if before != after:
                changed.append(offset.upper().replace("X", "x"))
                self.assertEqual(
                    control.text_runtime_size(after),
                    len(entry["source"].encode("cp932")),
                )
                self.assertTrue(
                    all(control.runtime_size(character) == 2 for character in after)
                )
        self.assertEqual(set(changed), set(control.REPLACEMENTS))


if __name__ == "__main__":
    unittest.main()
