from __future__ import annotations

import hashlib
import struct
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import build_dialog_punctuation_spacing_patch as target


class DialogPunctuationSpacingPatchTest(unittest.TestCase):
    def executable(self) -> bytes:
        size = target._offset(target.CODE_CAVE_VA) + target.CODE_CAVE_SIZE
        data = bytearray(size)
        data[:4] = b"\x7fELF"
        struct.pack_into(
            "<I", data, target._offset(target.ASCII_CLASSIFY_VA), target.V2_ASCII_CLASSIFY
        )
        struct.pack_into(
            "<I", data, target._offset(target.ASCII_BRANCH_VA), target.V2_ASCII_BRANCH
        )
        for va, word in zip(
            (
                target.ADVANCE_BRANCH_VA,
                target.ADVANCE_DELAY_VA,
                target.ADVANCE_ASCII_VA,
                target.ADVANCE_JUMP_VA,
                target.ADVANCE_STORE_DELAY_VA,
                target.ADVANCE_STORE_VA,
            ),
            target.V2_ADVANCE_WORDS,
            strict=True,
        ):
            struct.pack_into("<I", data, target._offset(va), word)
        cave = bytes.fromhex(
            "00" * target.V2_HELPERS_SIZE
        )
        # The production fingerprint is tested by substituting a deterministic
        # fixture digest so the unit test need not duplicate the v2 machine code.
        data[
            target._offset(target.CODE_CAVE_VA):
            target._offset(target.CODE_CAVE_VA) + target.V2_HELPERS_SIZE
        ] = cave
        return bytes(data)

    def test_installs_two_pixel_punctuation_helper(self) -> None:
        source = self.executable()
        original_digest = target.V2_HELPERS_SHA256
        try:
            target.V2_HELPERS_SHA256 = hashlib.sha256(
                bytes(target.V2_HELPERS_SIZE)
            ).hexdigest()
            output, report = target.patch_executable(source, 2)
        finally:
            target.V2_HELPERS_SHA256 = original_digest

        classify, = struct.unpack_from(
            "<I", output, target._offset(target.ASCII_CLASSIFY_VA)
        )
        branch, = struct.unpack_from(
            "<I", output, target._offset(target.ASCII_BRANCH_VA)
        )
        self.assertEqual(classify, target._jump(target.PUNCT_HELPER_VA))
        self.assertEqual(branch, 0)
        self.assertEqual(report["spacing"]["punctuation"], ["!", ",", ".", "?"])
        self.assertEqual(report["spacing"]["punctuation_leading_gap_px"], 2)
        self.assertEqual(report["spacing"]["punctuation_trailing_gap_px"], 2)
        helper_offset = target._offset(target.PUNCT_HELPER_VA)
        helper = output[helper_offset:helper_offset + report["code_cave"]["used_bytes"]]
        self.assertIn(struct.pack("<I", 0x26B50002), helper)
        self.assertIn(struct.pack("<I", 0x8FA90038), helper)
        self.assertIn(struct.pack("<I", 0x25290002), helper)
        self.assertIn(struct.pack("<I", 0xAFA90038), helper)
        self.assertEqual(report["spacing"]["hangul_cp932_lead_range"], "F0-F9")
        self.assertEqual(report["spacing"]["hangul_double_byte_advance_px"], 9)
        self.assertEqual(
            report["spacing"]["original_japanese_double_byte_advance_px"], 13
        )
        self.assertEqual(report["code_cave"]["used_bytes"], 196)
        dispatch, = struct.unpack_from(
            "<I", output, target._offset(target.ADVANCE_BRANCH_VA)
        )
        self.assertNotEqual(dispatch, target.V2_ADVANCE_WORDS[0])

    def test_rejects_unknown_revision(self) -> None:
        with self.assertRaisesRegex(ValueError, "v2 helper fingerprint mismatch"):
            target.patch_executable(self.executable(), 2)

    def test_rejects_out_of_range_gap(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 0 and 4"):
            target.patch_executable(self.executable(), 5)


if __name__ == "__main__":
    unittest.main()
