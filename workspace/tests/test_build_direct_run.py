from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
SCRIPTS = PROJECT / "workspace" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import build_direct_run


class DirectRunBuildTests(unittest.TestCase):
    def test_full_stage_rows_keep_unique_coordinates(self) -> None:
        rows, probes = build_direct_run.make_stage_rows(
            PROJECT / "workspace/text/translation/stage_info.csv", "full"
        )
        self.assertEqual(len(rows), 220)
        self.assertEqual(probes, [])
        self.assertEqual(len({row["entry_id"] for row in rows}), 220)
        self.assertEqual(
            len({(row["record_index"], row["slot_index"]) for row in rows}), 220
        )
        self.assertEqual(len({row["source_offset"] for row in rows}), 220)

    def test_probe_marks_first_and_last_five_records(self) -> None:
        rows, probes = build_direct_run.make_stage_rows(
            PROJECT / "workspace/text/translation/stage_info.csv", "probe"
        )
        self.assertEqual(len(rows), 220)
        self.assertEqual(len(probes), 20)
        self.assertEqual(len({item["marker"] for item in probes}), 20)
        self.assertEqual(
            {int(item["entry_id"].split("-")[1]) for item in probes},
            {*range(1, 6), *range(16, 21)},
        )


if __name__ == "__main__":
    unittest.main()
