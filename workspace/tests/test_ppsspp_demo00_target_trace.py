from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "work" / "pydeps"))
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import ppsspp_demo00_target_trace as target_trace  # noqa: E402


class PpssppDemo00TargetTraceTests(unittest.TestCase):
    def test_parse_hex_integer(self) -> None:
        self.assertEqual(target_trace.parse_int("0x00E6"), 0xE6)

    def test_no_hit_is_inconclusive(self) -> None:
        result = target_trace.classify_hits([], 0xE6, 0x1851C)
        self.assertEqual(result["status"], "INCONCLUSIVE_NO_HIT")

    def test_id_hit_at_other_offset_is_separate(self) -> None:
        result = target_trace.classify_hits(
            [{"logical_offset_value": 0x1234}], 0xE6, 0x1851C
        )
        self.assertEqual(result["status"], "POSITIVE_ID_OTHER_OFFSET")

    def test_exact_offset_is_positive(self) -> None:
        result = target_trace.classify_hits(
            [{"logical_offset_value": 0x1851C}], 0xE6, 0x1851C
        )
        self.assertEqual(result["status"], "POSITIVE_EXACT")
        self.assertEqual(result["exact_hit_count"], 1)


if __name__ == "__main__":
    unittest.main()
