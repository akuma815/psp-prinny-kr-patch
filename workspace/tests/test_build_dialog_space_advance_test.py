from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import build_dialog_space_advance_test as target


class DialogSpaceAdvanceTest(unittest.TestCase):
    def executable(self) -> bytes:
        data = bytearray(target.instruction_offset(target.DOUBLE_BYTE_ADVANCE_VA) + 4)
        data[:4] = b"\x7fELF"
        struct.pack_into(
            "<I", data, target.instruction_offset(), target.ORIGINAL_SPACE_WORD
        )
        struct.pack_into(
            "<I",
            data,
            target.instruction_offset(target.DOUBLE_BYTE_ADVANCE_VA),
            target.ORIGINAL_DOUBLE_BYTE_WORD,
        )
        return bytes(data)

    def test_changes_only_spacing_immediates(self) -> None:
        source = self.executable()
        output, report = target.patch_executable(source, 6, 9)
        changed = [i for i, pair in enumerate(zip(source, output)) if pair[0] != pair[1]]
        self.assertEqual(
            changed,
            [
                target.instruction_offset(),
                target.instruction_offset(target.DOUBLE_BYTE_ADVANCE_VA),
            ],
        )
        self.assertEqual(
            struct.unpack_from("<I", output, target.instruction_offset())[0],
            0x26B50006,
        )
        self.assertEqual(
            struct.unpack_from(
                "<I", output, target.instruction_offset(target.DOUBLE_BYTE_ADVANCE_VA)
            )[0],
            0x24060009,
        )
        self.assertEqual(report["instructions"][0]["patched_advance_px"], 6)
        self.assertEqual(report["instructions"][1]["patched_advance_px"], 9)

    def test_rejects_unknown_revision(self) -> None:
        source = bytearray(self.executable())
        struct.pack_into("<I", source, target.instruction_offset(), 0)
        with self.assertRaisesRegex(ValueError, "instruction mismatch"):
            target.patch_executable(bytes(source), 6, 9)

    def test_rejects_invalid_space_advance(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 1 and 12"):
            target.patch_executable(self.executable(), 13, 9)

    def test_rejects_invalid_double_byte_advance(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 1 and 12"):
            target.patch_executable(self.executable(), 6, 13)


if __name__ == "__main__":
    unittest.main()
