from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

from build_iso_poc import locate_iso9660_path  # noqa: E402


class BuildIsoPocTests(unittest.TestCase):
    def test_locates_system_dat_from_iso9660_directories(self) -> None:
        iso = next((PROJECT / "original").glob("*.iso"))
        record = locate_iso9660_path(iso, "/PSP_GAME/USRDIR/SYSTEM.DAT;1")
        self.assertEqual(record.offset, 0x1AA10000)
        self.assertEqual(record.extent_lba, 218144)
        self.assertEqual(record.size, 4_127_307)
        self.assertFalse(record.is_directory)


if __name__ == "__main__":
    unittest.main()
