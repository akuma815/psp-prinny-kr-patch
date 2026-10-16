from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import audit_enemy_orphan_key as orphan  # noqa: E402


class EnemyOrphanKeyAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.enemy = PROJECT / "work" / "script" / "enemy.nsf"
        cls.character = (
            PROJECT / "work" / "analysis" / "enemy_key_assets" / "Character00.dat"
        )
        cls.start = PROJECT / "work" / "system" / "start.dat"
        cls.boot = PROJECT / "extracted" / "PSP_GAME" / "SYSDIR" / "BOOT.BIN"

    def report(self) -> dict:
        return orphan.audit(
            self.enemy,
            self.enemy.read_bytes(),
            self.character,
            self.character.read_bytes(),
            self.start,
            self.start.read_bytes(),
            self.boot,
            self.boot.read_bytes(),
        )

    def test_character_table_is_strict(self) -> None:
        records = orphan.parse_characters(self.character.read_bytes())
        self.assertEqual(len(records), 390)
        self.assertEqual(records[44].name, "Archer_1")
        self.assertEqual(records[45].name, "Magician_1")
        self.assertEqual(records[44].character_id, 0x00FA)
        self.assertEqual(records[45].character_id, 0x010E)

    def test_target_family_has_no_character_descriptor(self) -> None:
        report = self.report()
        self.assertTrue(report["family"]["descriptor_gap_pattern"])
        self.assertEqual(report["family"]["character_descriptor_roots"], [])
        self.assertEqual(
            report["verdict"]["status"], "BASE_ISO_UNREACHABLE_DLC_SEPARATE"
        )

    def test_target_key_is_absent_from_start_and_boot(self) -> None:
        report = self.report()
        self.assertEqual(report["target_exact_external_occurrence_count"], 0)
        self.assertEqual(
            report["target"]["key_resolves_to_block_start"], "0x0001851B"
        )
        self.assertEqual(report["target"]["enemy_code_occurrences"], [])

    def test_boot_contract_separates_base_and_dlc_slots(self) -> None:
        report = self.report()
        self.assertEqual(report["boot_character_contract"]["status"], "PASS")
        assertions = report["boot_character_contract"]["assertions"]
        self.assertIn("base_character_slot_zero", assertions)
        self.assertIn("dlc_character_slot_one", assertions)
        self.assertIn("root_key_load", assertions)


if __name__ == "__main__":
    unittest.main()
