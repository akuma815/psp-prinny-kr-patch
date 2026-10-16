from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "work" / "pydeps"))
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import nsf_links  # noqa: E402
import nsf_reachability  # noqa: E402


class NsfReachabilityTests(unittest.TestCase):
    def test_first_message_instruction_advances_to_exact_next_pc(self) -> None:
        nsf = nsf_links.parse_nsf((PROJECT / "work" / "script" / "demo.nsf").read_bytes())
        stepper = nsf_reachability.DispatcherStepper(
            (PROJECT / "extracted" / "PSP_GAME" / "SYSDIR" / "BOOT.BIN").read_bytes(),
            nsf,
        )
        step = stepper.step(0x961)
        self.assertEqual(step.start, 0x961)
        self.assertEqual(step.end, 0x971)
        self.assertEqual(step.outcome, "next")


if __name__ == "__main__":
    unittest.main()
