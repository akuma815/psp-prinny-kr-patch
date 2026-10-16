from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

from compress_nis_lzs import compress  # noqa: E402
from decompress_nis_lzs import decompress  # noqa: E402


class NisLzsTests(unittest.TestCase):
    def test_literals_flag_escape_and_repeated_data_roundtrip(self) -> None:
        source = b"ABABABAB" + bytes([0xD5]) + b"Z" * 600 + bytes(range(256))
        packed, stats = compress(source)
        restored, extension = decompress(packed)
        self.assertEqual(restored, source)
        self.assertEqual(extension, "dat")
        self.assertEqual(stats["overlapping_matches"], 0)
        self.assertLessEqual(stats["maximum_length"], stats["maximum_distance"])

    def test_observed_original_stream_decompresses_exactly(self) -> None:
        packed = (PROJECT / "work" / "system" / "start.lzs").read_bytes()
        expected = (PROJECT / "work" / "system" / "start.dat").read_bytes()
        restored, extension = decompress(packed)
        self.assertEqual(restored, expected)
        self.assertEqual(extension, "dat")

    def test_rejects_invalid_extension_and_flag(self) -> None:
        with self.assertRaises(ValueError):
            compress(b"data", "toolong")
        with self.assertRaises(ValueError):
            compress(b"data", flag=0)


if __name__ == "__main__":
    unittest.main()
