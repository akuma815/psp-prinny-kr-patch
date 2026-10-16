from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "work" / "pydeps"))
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import ppsspp_nsf_trace  # noqa: E402


class PpssppNsfTraceTests(unittest.TestCase):
    def test_decode_literal_message_head(self) -> None:
        result = ppsspp_nsf_trace.decode_message_head(
            2, bytes.fromhex("FF 78 56 34 12 00 00 00")
        )
        self.assertEqual(result["channel"], -1)
        self.assertEqual(result["message_id"], 0x12345678)
        self.assertIsNone(result["message_operand"])

    def test_decode_tagged_message_head(self) -> None:
        result = ppsspp_nsf_trace.decode_message_head(
            1, bytes.fromhex("02 02 FE FF 00 00 00 00")
        )
        self.assertEqual(result["channel"], 2)
        self.assertEqual(result["message_id"], -2)
        self.assertEqual(result["message_operand"]["tag"], 2)

    def test_decode_dynamic_message_head(self) -> None:
        result = ppsspp_nsf_trace.decode_message_head(
            1, bytes.fromhex("00 00 2A 00 00 00 00 00")
        )
        self.assertIsNone(result["message_id"])
        self.assertEqual(result["message_operand"]["raw_hex"], "2a")


if __name__ == "__main__":
    unittest.main()
