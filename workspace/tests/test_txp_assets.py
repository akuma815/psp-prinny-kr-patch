import struct
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import txp_assets  # noqa: E402


def make_txp(width, height, pixel_format, palette, linear, swizzled=False):
    header = struct.pack(
        "<8H", width, height, pixel_format, 0, len(palette), 1, int(swizzled), 1
    )
    raw = txp_assets.swizzle(linear, width if pixel_format == 0x100 else width // 2, height) if swizzled else linear
    return header + b"".join(bytes(color) for color in palette) + raw


class TxpAssetsTests(unittest.TestCase):

    def test_index_decode_encode_is_byte_identical(self):
        palette = [(i * 17, i * 17, i * 17, 255) for i in range(16)]
        linear = bytes((x & 0x0F) | (((x + 1) & 0x0F) << 4) for _y in range(8) for x in range(0, 32, 2))
        data = make_txp(32, 8, 0x10, palette, linear, swizzled=True)
        indices = txp_assets.decode_indices(data)
        self.assertEqual(txp_assets.encode_indices(data, indices), data)

    def test_swizzle_roundtrip(self):
        raw = bytes(range(256)) * 8
        self.assertEqual(txp_assets.unswizzle(txp_assets.swizzle(raw, 32, 64), 32, 64), raw)

    def test_decode_linear_4bpp_low_nibble_first(self):
        palette = [(0, 0, 0, 0), (255, 0, 0, 255), (0, 255, 0, 255)]
        data = make_txp(2, 1, 0x10, palette, bytes([0x21]))
        image = txp_assets.decode_txp(data)
        self.assertEqual(image.getpixel((0, 0)), palette[1])
        self.assertEqual(image.getpixel((1, 0)), palette[2])

    def test_decode_swizzled_8bpp(self):
        palette = [(i, 0, 0, 255) for i in range(256)]
        linear = bytes((x + y * 16) & 0xFF for y in range(8) for x in range(16))
        data = make_txp(16, 8, 0x100, palette, linear, swizzled=True)
        image = txp_assets.decode_txp(data)
        self.assertEqual(image.getpixel((5, 3)), palette[53])

    def test_rejects_mismatched_payload(self):
        with self.assertRaisesRegex(ValueError, "payload mismatch"):
            txp_assets.parse_txp(struct.pack("<8H", 16, 8, 0x100, 0, 1, 1, 0, 1) + b"\0" * 4)


if __name__ == "__main__":
    unittest.main()
