from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import audit_cp932_allocation  # noqa: E402


class AuditCp932AllocationTests(unittest.TestCase):
    def test_scanner_rejects_halfwidth_noise_and_keeps_japanese(self) -> None:
        noise = "ﾀﾝﾌﾝﾝMD4".encode("cp932")
        actual = "魔風草原のプリニー".encode("cp932")
        runs = audit_cp932_allocation.candidate_runs(
            noise + b"\0" + actual + b"\0",
            minimum_strong_japanese=2,
            minimum_strong_ratio=0.35,
            maximum_run_bytes=256,
        )
        self.assertEqual([run["text"] for run in runs], ["魔風草原のプリニー"])

    def test_boot_scanner_excludes_utf8_japanese_literal(self) -> None:
        cp932 = "プリニーの拠点です".encode("cp932")
        utf8 = "通信中にエラー".encode("utf-8")
        runs = audit_cp932_allocation.candidate_runs(
            b"\0" + cp932 + b"\0" + utf8 + b"\0",
            minimum_strong_japanese=5,
            minimum_strong_ratio=0.7,
            maximum_run_bytes=256,
            require_nul_boundaries=True,
            exclude_utf8_japanese=True,
        )
        self.assertEqual([run["text"] for run in runs], ["プリニーの拠点です"])

    def test_supported_revision_allocation_audit(self) -> None:
        report = audit_cp932_allocation.audit(
            PROJECT / "workspace" / "config" / "cp932_allocation_profile.json",
            PROJECT / "work" / "system" / "start.dat",
            PROJECT / "extracted" / "PSP_GAME" / "SYSDIR" / "BOOT.BIN",
            PROJECT / "work" / "system" / "start_assets",
        )
        self.assertEqual(
            report["evidence_tiers"]["confirmed_structured"]["distinct_cp932_codes"],
            1171,
        )
        budget = report["allocation_budget"]
        self.assertEqual(budget["currently_mapped_nonblank_codes"], 2347)
        self.assertGreater(budget["currently_unmapped_or_blank_code_slots"], 0)
        self.assertGreater(budget["reclaimable_nonblank_glyph_candidates"], 0)
        self.assertEqual(budget["policy_reserved_single_byte_ascii_codes"], 95)
        self.assertEqual(
            budget["fixed_size_new_glyph_candidate_upper_bound"],
            budget["reclaimable_nonblank_glyph_candidates"],
        )
        self.assertFalse(report["decision"]["production_allocation_approved"])
        self.assertTrue(all(item["reserved"] for item in report["dialog_e2e_proxy_codes"]))


if __name__ == "__main__":
    unittest.main()
