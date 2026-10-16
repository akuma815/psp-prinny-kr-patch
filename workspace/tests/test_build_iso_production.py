from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import build_iso_production  # noqa: E402


class BuildIsoProductionTests(unittest.TestCase):
    def test_disc_layout_has_only_two_following_usrdir_files(self) -> None:
        iso = next((PROJECT / "original").glob("*.iso"))
        parent = build_iso_production.locate_directory(iso, "/PSP_GAME/USRDIR")
        children = build_iso_production.positioned_children(iso, parent)
        target = next(item for item in children if item.record.name == "SYSTEM.DAT")
        following = [
            item.record.name for item in children
            if not item.record.is_directory and item.record.offset > target.record.offset
        ]
        self.assertEqual(set(following), {"ANIME.DAT", "BG.DAT"})
        self.assertEqual(target.record.offset, 0x1AA10000)


if __name__ == "__main__":
    unittest.main()
