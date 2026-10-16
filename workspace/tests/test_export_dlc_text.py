from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import export_dlc_text  # noqa: E402


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class ExportDlcTextTests(unittest.TestCase):
    def test_exports_closed_population_and_protected_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            translation = root / "translation"
            manifest_path = root / "source" / "dlc_manifest.json"
            result = export_dlc_text.export(
                PROJECT / "original" / "Prinny DLC",
                translation,
                manifest_path,
            )
            self.assertEqual(
                result["totals"],
                {
                    "files": 3,
                    "ddem_records": 67,
                    "ddem_rows": 67,
                    "ddem_text_slots": 268,
                    "ddem_nonempty_text_slots": 182,
                    "dsti_rows": 33,
                    "dsti_nonempty_text_slots": 31,
                },
            )
            self.assertTrue(manifest_path.is_file())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(
                manifest["editable_fields"]["ddem"],
                ["ko_speaker", "ko_line_1", "ko_line_2", "ko_line_3", "status", "notes"],
            )
            self.assertEqual(len(manifest["sources"]), 3)
            self.assertTrue(all(source["roundtrip"] == "PASS" for source in manifest["sources"]))

            expected_rows = {"dl0000": 29, "dl0001": 23, "dl0002": 15}
            for dlc_id, count in expected_rows.items():
                path = translation / f"{dlc_id}_ddem.csv"
                self.assertEqual(path.read_bytes()[:3], b"\xEF\xBB\xBF")
                rows = read_rows(path)
                self.assertEqual(len(rows), count)
                self.assertTrue(all(row["status"] == "untranslated" for row in rows))

            dsti_path = translation / "dlc_stage_info.csv"
            self.assertEqual(dsti_path.read_bytes()[:3], b"\xEF\xBB\xBF")
            self.assertEqual(len(read_rows(dsti_path)), 33)

    def test_reexport_preserves_only_editable_columns(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            translation = root / "translation"
            manifest_path = root / "source" / "dlc_manifest.json"
            args = (PROJECT / "original" / "Prinny DLC", translation, manifest_path)
            export_dlc_text.export(*args)

            path = translation / "dl0000_ddem.csv"
            rows = read_rows(path)
            original_ja = rows[0]["ja_line_1"]
            rows[0]["ja_line_1"] = "보호 필드 변조"
            rows[0]["line_1_bytes"] = "00"
            rows[0]["ko_speaker"] = "플론"
            rows[0]["ko_line_1"] = "시험 번역"
            rows[0]["status"] = "in_progress"
            rows[0]["notes"] = "보존 확인"
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=export_dlc_text.DDEM_FIELDS, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)

            export_dlc_text.export(*args)
            refreshed = read_rows(path)[0]
            self.assertEqual(refreshed["ja_line_1"], original_ja)
            self.assertNotEqual(refreshed["line_1_bytes"], "00")
            self.assertEqual(refreshed["ko_speaker"], "플론")
            self.assertEqual(refreshed["ko_line_1"], "시험 번역")
            self.assertEqual(refreshed["status"], "in_progress")
            self.assertEqual(refreshed["notes"], "보존 확인")


if __name__ == "__main__":
    unittest.main()
