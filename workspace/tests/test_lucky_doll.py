import csv
import importlib.util
import json
import sys
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
SCRIPTS = PROJECT / "workspace/scripts"
sys.path.insert(0, str(SCRIPTS))

import export_lucky_doll
import lucky_doll
from integrate_stage_info_iso import mapping_from_rows


class LuckyDollTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = export_lucky_doll.extract_lucky_doll(
            PROJECT / "extracted/PSP_GAME/USRDIR/SYSTEM.DAT"
        )
        cls.rows = lucky_doll.load_rows(
            PROJECT / "workspace/text/translation/lucky_doll.csv"
        )
        mapping = json.loads(
            (
                PROJECT
                / "work/builds/integrated_20260726/stage_info/hangul_mapping.json"
            ).read_text(encoding="utf-8")
        )
        cls.character_map = mapping_from_rows(list(mapping["entries"]))

    def test_population_and_source_contract(self) -> None:
        self.assertEqual(len(self.source), lucky_doll.EXPECTED_SIZE)
        self.assertEqual(len(self.rows), lucky_doll.RECORD_COUNT)
        self.assertEqual(
            {int(row["record_index"]) for row in self.rows},
            set(range(1, lucky_doll.RECORD_COUNT + 1)),
        )

    def test_all_rows_patch_with_current_font_mapping(self) -> None:
        output, report = lucky_doll.patch(
            self.source, self.rows, self.character_map
        )
        self.assertEqual(len(output), len(self.source))
        self.assertEqual(len(report), lucky_doll.RECORD_COUNT)
        self.assertEqual(
            output[-lucky_doll.FOOTER_SIZE :],
            self.source[-lucky_doll.FOOTER_SIZE :],
        )
        self.assertLessEqual(
            max(int(item["encoded_bytes"]) for item in report),
            lucky_doll.TEXT_PAYLOAD_SIZE,
        )


if __name__ == "__main__":
    unittest.main()
