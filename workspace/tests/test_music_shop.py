from __future__ import annotations

import importlib.util
import struct
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "music_shop.py"
SPEC = importlib.util.spec_from_file_location("music_shop", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
music_shop = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = music_shop
SPEC.loader.exec_module(music_shop)


def slot(text: str, size: int) -> bytes:
    content = text.encode("cp932")
    if len(content) >= size:
        raise ValueError("test string does not fit")
    return content + b"\0" + bytes(size - len(content) - 1)


def sample() -> bytes:
    record = music_shop.RECORD.pack(
        1,
        7,
        slot("ＢＧＭ０１", 21),
        slot("【ＢＧＭ０１】Prinny Action", 65),
        5,
        0,
    )
    return struct.pack("<HH", 1, 0x1234) + record + struct.pack("<I", 0)


class MusicShopTests(unittest.TestCase):
    def test_parse_serialize_is_byte_identical(self) -> None:
        source = sample()
        parsed = music_shop.parse(source)
        self.assertEqual(parsed.to_bytes(), source)
        self.assertEqual(parsed.records[0].record_index_id, 1)
        self.assertEqual(parsed.header_unknown, 0x1234)
        self.assertEqual(parsed.records[0].short_name.text, "ＢＧＭ０１")
        self.assertEqual(
            parsed.records[0].display_name.text, "【ＢＧＭ０１】Prinny Action"
        )

    def test_rejects_size_not_implied_by_count(self) -> None:
        with self.assertRaisesRegex(ValueError, "size mismatch"):
            music_shop.parse(sample() + b"\0")

    def test_rejects_slot_without_nul(self) -> None:
        damaged = bytearray(sample())
        damaged[4 + 3 : 4 + 3 + 21] = b"A" * 21
        with self.assertRaisesRegex(ValueError, "no NUL terminator"):
            music_shop.parse(bytes(damaged))

    def test_rejects_nonzero_padding(self) -> None:
        damaged = bytearray(sample())
        damaged[4 + 3 + 20] = 1
        with self.assertRaisesRegex(ValueError, "non-zero bytes after NUL"):
            music_shop.parse(bytes(damaged))

    def test_rejects_invalid_cp932(self) -> None:
        damaged = bytearray(sample())
        damaged[4 + 3 : 4 + 3 + 21] = b"\x81\x00" + bytes(19)
        with self.assertRaisesRegex(ValueError, "not valid cp932"):
            music_shop.parse(bytes(damaged))


if __name__ == "__main__":
    unittest.main()
