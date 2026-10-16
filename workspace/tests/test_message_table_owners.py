from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import message_table_owners  # noqa: E402


class MessageTableOwnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = message_table_owners.analyze(
            (PROJECT / "extracted" / "PSP_GAME" / "SYSDIR" / "BOOT.BIN").read_bytes(),
            (PROJECT / "work" / "script" / "demo.nsf").read_bytes(),
            (PROJECT / "work" / "system" / "start_assets" / "Demo00.dat").read_bytes(),
        )

    def test_second_slot_is_dlc_ddem(self) -> None:
        owner = self.result["owner_path"]
        self.assertEqual(owner["slot_0"], "Demo00.dat")
        self.assertEqual(owner["slot_1"], "DDEM")
        self.assertEqual(
            owner["slot_1_container"], "ms0:/PSP/GAME/%s/DL%04d.EDAT"
        )

    def test_ddem_candidate_population(self) -> None:
        candidates = self.result["ddem_candidates"]
        self.assertEqual(len(candidates), 52)
        self.assertEqual(len({item["message_id"] for item in candidates}), 52)
        self.assertEqual(candidates[0]["message_id"], 0x53FC)
        self.assertEqual(candidates[-1]["message_id"], 0x5628)

    def test_two_other_patterns_remain_separate(self) -> None:
        self.assertEqual(self.result["counts"]["other_unresolved_patterns"], 2)


if __name__ == "__main__":
    unittest.main()
