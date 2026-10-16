from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import build_demo00_poc  # noqa: E402
import demo00  # noqa: E402


class BuildDemo00PocTests(unittest.TestCase):
    def test_one_record_fixed_slot_reinsertion(self) -> None:
        source_path = PROJECT / "work" / "system" / "start_assets" / "Demo00.dat"
        source = source_path.read_bytes()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            report = build_demo00_poc.build(
                PROJECT / "workspace" / "config" / "dialog_e2e_profile.json",
                PROJECT / "workspace" / "text" / "demo00_poc_07d0.json",
                source_path,
                output,
            )
            rebuilt = (output / "Demo00.dat").read_bytes()
        self.assertEqual(len(rebuilt), len(source))
        self.assertTrue(report["entry"]["control_metadata_byte_identical"])
        self.assertEqual(report["entry"]["ko_speaker"], "프리니")
        self.assertEqual(report["entry"]["ko_lines"][0], "우와、지각했다！！")
        table = demo00.parse(rebuilt)
        record = table.records[291]
        self.assertEqual(record.record_id, 0x07D0)
        self.assertEqual(record.speaker, "プリニ")
        self.assertEqual(record.lines[0], "うわ、ちこくッ！！")
        start = demo00.HEADER.size + 291 * demo00.RECORD_SIZE
        self.assertEqual(source[:start], rebuilt[:start])
        self.assertEqual(
            source[start + demo00.RECORD_SIZE:],
            rebuilt[start + demo00.RECORD_SIZE:],
        )


if __name__ == "__main__":
    unittest.main()
