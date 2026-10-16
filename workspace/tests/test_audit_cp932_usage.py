from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import audit_cp932_usage  # noqa: E402


class AuditCp932UsageTests(unittest.TestCase):
    def test_confirmed_corpus_and_probe_sequence(self) -> None:
        report = audit_cp932_usage.audit(PROJECT / "work" / "system" / "start_assets")
        self.assertEqual(report["scope"]["total_text_slots"], 6396)
        self.assertEqual(report["scope"]["nonempty_text_slots"], 4430)
        self.assertEqual(report["usage"]["distinct_cp932_codes"], 1171)
        probe = report["multi_glyph_probe"]
        self.assertEqual(probe["display_sequence_source"], "プリニー")
        self.assertEqual(probe["display_sequence_generated"], "가각뾰힣")
        self.assertEqual(
            [item["cp932_hex"] for item in probe["replacements"]],
            ["8376", "838A", "836A", "815B"],
        )
        self.assertGreater(report["usage"]["unused_renderable_codes_in_confirmed_corpus"], 0)


if __name__ == "__main__":
    unittest.main()
