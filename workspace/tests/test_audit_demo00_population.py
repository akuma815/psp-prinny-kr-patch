from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import audit_demo00_population  # noqa: E402


class Demo00PopulationAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.demo_path = PROJECT / "work" / "system" / "start_assets" / "Demo00.dat"
        cls.boot_path = PROJECT / "extracted" / "PSP_GAME" / "SYSDIR" / "BOOT.BIN"
        cls.report = audit_demo00_population.audit(
            cls.demo_path,
            cls.demo_path.read_bytes(),
            list((PROJECT / "work" / "script").glob("*.nsf")),
            cls.boot_path,
            cls.boot_path.read_bytes(),
            json.loads(
                (PROJECT / "work" / "analysis" / "enemy_orphan_key.json").read_text(
                    encoding="utf-8"
                )
            ),
        )

    def test_layout_template_matrix_is_complete(self) -> None:
        pattern = self.report["observed_pattern"]
        self.assertEqual(pattern["record_count"], 49)
        self.assertEqual(self.report["population"]["unresolved"], 0)
        self.assertEqual(self.report["population"]["evidence_based_exclusions"], 49)

    def test_enemy_nsf_candidate_is_retained_with_reachability_evidence(self) -> None:
        referenced = [item for item in self.report["records"] if item["references"]]
        self.assertEqual([item["entry_id"] for item in referenced], ["demo00/00E6"])
        reference = referenced[0]["references"][0]
        self.assertEqual(reference["nsf"].split("/")[-1], "enemy.nsf")
        self.assertEqual(reference["opcode"], "42 02")
        self.assertTrue(reference["containing_blocks"])

    def test_declared_base_population_is_closed(self) -> None:
        population = self.report["population"]
        self.assertEqual(population["resolved_translation_targets"], 1523)
        self.assertTrue(population["completion_denominator_closed"])


if __name__ == "__main__":
    unittest.main()
