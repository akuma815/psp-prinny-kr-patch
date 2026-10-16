from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import build_dialog_typewriter_patch as target


class DialogTypewriterPatchTest(unittest.TestCase):
    def executable(self) -> bytes:
        size = target._offset(target.CODE_CAVE_VA) + target.CODE_CAVE_SIZE
        data = bytearray(size)
        data[:4] = b"\x7fELF"
        fingerprints = (
            (target.ATLAS_PAGE_STORE_VA, target.ORIGINAL_ATLAS_PAGE_STORE),
            (
                target.ATLAS_ALT_PAGE_STORE_VA,
                target.ORIGINAL_ATLAS_ALT_PAGE_STORE,
            ),
            (target.ATLAS_RESET_VA, target.ORIGINAL_ATLAS_RESET),
            (target.ATLAS_CAP_CHECK_VA, target.ORIGINAL_ATLAS_CAP_CHECK),
            (target.GLYPH_ID_READY_VA, target.ORIGINAL_GLYPH_ID_READY),
            (target.COUNT_CALL_VA, target.ORIGINAL_COUNT_CALL),
            (target.COUNT_DIVIDE_VA, target.ORIGINAL_COUNT_DIVIDE),
            (target.COPY_CALL_VA, target.ORIGINAL_COPY_CALL),
            (target.COPY_MULTIPLY_VA, target.ORIGINAL_COPY_MULTIPLY),
            (target.COPY_TRAILING_NUL_VA, target.ORIGINAL_COPY_TRAILING_NUL),
            (target.SPACE_ADVANCE_VA, target.ORIGINAL_SPACE_ADVANCE),
            (target.DOUBLE_BYTE_ADVANCE_VA, target.ORIGINAL_DOUBLE_BYTE_ADVANCE),
            (target.ASCII_CLASSIFY_VA, target.ORIGINAL_ASCII_CLASSIFY),
            (target.ASCII_BRANCH_VA, target.ORIGINAL_ASCII_BRANCH),
            (target.LEAD_LOWER_VA, target.ORIGINAL_LEAD_LOWER),
            (target.LEAD_INVERT_VA, target.ORIGINAL_LEAD_INVERT),
            (target.LEAD_UPPER_VA, target.ORIGINAL_LEAD_UPPER),
        )
        for address, word in fingerprints:
            struct.pack_into("<I", data, target._offset(address), word)
        return bytes(data)

    def test_installs_complete_character_helpers_and_spacing(self) -> None:
        source = self.executable()
        output, report = target.patch_executable(source, 6, 9)

        words = {
            address: struct.unpack_from("<I", output, target._offset(address))[0]
            for address in (
                target.COUNT_CALL_VA,
                target.COUNT_DIVIDE_VA,
                target.COPY_CALL_VA,
                target.COPY_MULTIPLY_VA,
                target.COPY_TRAILING_NUL_VA,
                target.SPACE_ADVANCE_VA,
                target.DOUBLE_BYTE_ADVANCE_VA,
                target.ASCII_CLASSIFY_VA,
                target.ASCII_BRANCH_VA,
                target.LEAD_LOWER_VA,
                target.LEAD_INVERT_VA,
                target.LEAD_UPPER_VA,
            )
        }
        self.assertEqual(words[target.COUNT_CALL_VA], target._jal(target.CODE_CAVE_VA))
        self.assertEqual(words[target.COUNT_DIVIDE_VA], 0x00401821)
        self.assertEqual(words[target.COPY_MULTIPLY_VA], 0x00403021)
        self.assertEqual(words[target.COPY_TRAILING_NUL_VA], 0)
        self.assertEqual(words[target.SPACE_ADVANCE_VA], 0x26B50006)
        self.assertEqual(words[target.DOUBLE_BYTE_ADVANCE_VA], 0x24060009)
        self.assertEqual(words[target.ASCII_CLASSIFY_VA], 0x2CA20080)
        self.assertEqual(words[target.ASCII_BRANCH_VA], 0x10400003)
        self.assertEqual(words[target.LEAD_LOWER_VA], 0x2CA20081)
        self.assertEqual(words[target.LEAD_INVERT_VA], 0x38420001)
        self.assertEqual(words[target.LEAD_UPPER_VA], 0x2CA600A0)

        copy_va = int(report["code_cave"]["copy_helper_virtual_address"], 16)
        self.assertEqual(words[target.COPY_CALL_VA], target._jal(copy_va))
        cave = output[
            target._offset(target.CODE_CAVE_VA):
            target._offset(target.CODE_CAVE_VA) + report["code_cave"]["used_bytes"]
        ]
        self.assertTrue(cave)
        self.assertNotEqual(cave, bytes(len(cave)))

    def test_rejects_unknown_revision(self) -> None:
        source = bytearray(self.executable())
        struct.pack_into("<I", source, target._offset(target.COPY_TRAILING_NUL_VA), 0)
        with self.assertRaisesRegex(ValueError, "fingerprint mismatch"):
            target.patch_executable(bytes(source), 6, 9)

    def test_accepts_native_ui_geometry(self) -> None:
        output, report = target.patch_executable(self.executable(), 13, 13)
        self.assertEqual(
            struct.unpack_from("<I", output, target._offset(target.SPACE_ADVANCE_VA))[0],
            target.ORIGINAL_SPACE_ADVANCE,
        )
        self.assertEqual(
            struct.unpack_from(
                "<I", output, target._offset(target.DOUBLE_BYTE_ADVANCE_VA)
            )[0],
            target.ORIGINAL_DOUBLE_BYTE_ADVANCE,
        )
        self.assertEqual(report["spacing"]["space_advance_px"], 13)
        self.assertEqual(report["spacing"]["default_glyph_advance_px"], 13)
        self.assertFalse(report["typewriter_units"]["ascii_space_consumes_unit"])
        self.assertTrue(report["typewriter_units"]["ascii_space_is_preserved_in_prefix"])

        count_words = struct.unpack(
            f"<{report['code_cave']['count_helper_bytes'] // 4}I",
            output[
                target._offset(target.CODE_CAVE_VA):
                target._offset(target.CODE_CAVE_VA)
                + report["code_cave"]["count_helper_bytes"]
            ],
        )
        copy_va = int(report["code_cave"]["copy_helper_virtual_address"], 16)
        copy_words = struct.unpack(
            f"<{report['code_cave']['copy_helper_bytes'] // 4}I",
            output[
                target._offset(copy_va):
                target._offset(copy_va) + report["code_cave"]["copy_helper_bytes"]
            ],
        )
        self.assertIn(0x24090020, count_words)
        self.assertIn(0x24090020, copy_words)

    def test_renderer_only_leaves_typewriter_native_and_reuses_glyph_cells(self) -> None:
        source = self.executable()
        output, report = target.patch_renderer_only(source, 13, 13)

        for address in (
            target.COUNT_CALL_VA,
            target.COUNT_DIVIDE_VA,
            target.COPY_CALL_VA,
            target.COPY_MULTIPLY_VA,
            target.COPY_TRAILING_NUL_VA,
        ):
            self.assertEqual(
                output[target._offset(address):target._offset(address) + 4],
                source[target._offset(address):target._offset(address) + 4],
            )
        helper_size = report["atlas_page_sync"]["helper_bytes"]
        used_size = report["glyph_cell_reuse"]["code_cave_used_bytes"]
        self.assertNotEqual(
            output[
                target._offset(target.CODE_CAVE_VA):
                target._offset(target.CODE_CAVE_VA) + helper_size
            ],
            bytes(helper_size),
        )
        self.assertEqual(
            output[
                target._offset(target.CODE_CAVE_VA) + used_size:
                target._offset(target.CODE_CAVE_VA) + target.CODE_CAVE_SIZE
            ],
            bytes(target.CODE_CAVE_SIZE - used_size),
        )
        self.assertEqual(report["mode"], "renderer_only_with_glyph_cell_reuse")
        self.assertTrue(report["atlas_page_sync"]["installed"])
        self.assertTrue(report["glyph_cell_reuse"]["installed"])
        self.assertEqual(report["glyph_cell_reuse"]["capacity"], 216)
        self.assertFalse(report["typewriter_hook"]["installed"])
        self.assertEqual(
            struct.unpack_from(
                "<I", output, target._offset(target.ATLAS_PAGE_STORE_VA)
            )[0],
            target._jal(target.CODE_CAVE_VA),
        )
        self.assertEqual(
            struct.unpack_from(
                "<I", output, target._offset(target.ATLAS_ALT_PAGE_STORE_VA)
            )[0],
            target._jal(
                int(
                    report["atlas_page_sync"][
                        "alternate_wrapper_virtual_address"
                    ],
                    16,
                )
            ),
        )
        self.assertEqual(
            struct.unpack_from(
                "<I", output, target._offset(target.ATLAS_RESET_VA)
            )[0],
            target._j(
                int(report["atlas_page_sync"]["reset_helper_virtual_address"], 16)
            ),
        )

        self.assertEqual(
            struct.unpack_from(
                "<I", output, target._offset(target.ATLAS_CAP_CHECK_VA)
            )[0],
            0x286100D9,
        )
        self.assertEqual(
            struct.unpack_from(
                "<I", output, target._offset(target.GLYPH_ID_READY_VA)
            )[0],
            target._jal(
                int(report["glyph_cell_reuse"]["helper_virtual_address"], 16)
            ),
        )
        self.assertEqual(
            struct.unpack_from(
                "<I", output, target._offset(target.ASCII_CLASSIFY_VA)
            )[0],
            0x2CA20080,
        )
        page0_cache = int(
            report["glyph_cell_reuse"]["page0_cache_virtual_address"], 16
        )
        page1_cache = int(
            report["glyph_cell_reuse"]["page1_cache_virtual_address"], 16
        )
        self.assertEqual(page1_cache - page0_cache, target.ATLAS_CAPACITY * 2)
        self.assertNotEqual(
            report["atlas_page_sync"]["page0_counter_virtual_address"],
            report["atlas_page_sync"]["page1_counter_virtual_address"],
        )
        atlas_words = struct.unpack(
            f"<{helper_size // 4}I",
            output[
                target._offset(target.CODE_CAVE_VA):
                target._offset(target.CODE_CAVE_VA) + helper_size
            ],
        )
        self.assertEqual(
            atlas_words[:4],
            (0x27BDFFF0, 0xAFA20000, 0xAFA80004, 0xAFA90008),
        )
        self.assertEqual(atlas_words.count(0xAD090000), 2)
        self.assertEqual(atlas_words.count(0x8D090000), 2)
        self.assertEqual(
            report["atlas_page_sync"]["preserved_registers"],
            ["v0", "t0", "t1"],
        )
        self.assertEqual(
            report["atlas_page_sync"]["cache_clear_bytes"],
            target.ATLAS_CAPACITY * 2 * 2,
        )
        self.assertEqual(
            report["atlas_page_sync"]["cache_clear_words"],
            target.ATLAS_CAPACITY,
        )
        self.assertEqual(
            report["atlas_page_sync"]["reset_preserved_registers"],
            ["t0", "t1"],
        )
        reset_va = int(
            report["atlas_page_sync"]["reset_helper_virtual_address"], 16
        )
        reset_size = report["atlas_page_sync"]["reset_helper_bytes"]
        reset_words = struct.unpack(
            f"<{reset_size // 4}I",
            output[
                target._offset(reset_va):
                target._offset(reset_va) + reset_size
            ],
        )
        self.assertEqual(reset_words[:3], (0x27BDFFF0, 0xAFA80000, 0xAFA90004))
        self.assertIn(0x240900D8, reset_words)
        self.assertIn(0xAD000000, reset_words)
        self.assertIn(0x2529FFFF, reset_words)
        alt_wrapper_va = int(
            report["atlas_page_sync"]["alternate_wrapper_virtual_address"], 16
        )
        alt_wrapper_size = report["atlas_page_sync"]["alternate_wrapper_bytes"]
        alt_wrapper_words = struct.unpack(
            f"<{alt_wrapper_size // 4}I",
            output[
                target._offset(alt_wrapper_va):
                target._offset(alt_wrapper_va) + alt_wrapper_size
            ],
        )
        self.assertEqual(alt_wrapper_words[0], 0x27BDFFF8)
        self.assertEqual(alt_wrapper_words[1], 0xAFBF0000)
        self.assertIn(target._jal(target.CODE_CAVE_VA), alt_wrapper_words)
        self.assertEqual(alt_wrapper_words[-3:], (0x03E00008, 0, 0))

    def test_native_atlas_control_omits_custom_cache_and_helpers(self) -> None:
        source = self.executable()
        output, report = target.patch_renderer_without_glyph_cache(source, 6, 9)

        self.assertEqual(report["mode"], "renderer_only_native_atlas_control")
        self.assertFalse(report["atlas_page_sync"]["installed"])
        self.assertFalse(report["glyph_cell_reuse"]["installed"])
        self.assertFalse(report["typewriter_hook"]["installed"])
        self.assertEqual(
            output[
                target._offset(target.CODE_CAVE_VA):
                target._offset(target.CODE_CAVE_VA) + target.CODE_CAVE_SIZE
            ],
            bytes(target.CODE_CAVE_SIZE),
        )
        for address in (
            target.ATLAS_PAGE_STORE_VA,
            target.ATLAS_ALT_PAGE_STORE_VA,
            target.ATLAS_RESET_VA,
            target.ATLAS_CAP_CHECK_VA,
            target.GLYPH_ID_READY_VA,
        ):
            self.assertEqual(
                output[target._offset(address):target._offset(address) + 4],
                source[target._offset(address):target._offset(address) + 4],
            )


if __name__ == "__main__":
    unittest.main()
