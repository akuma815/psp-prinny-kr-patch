from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

from ppsspp_boot_probe import classify_line  # noqa: E402


class PpssppBootProbeTests(unittest.TestCase):
    def test_classifies_loader_evidence(self) -> None:
        keys, error, warning = classify_line(
            'D KO 296: OpenFile "disc0:/PSP_GAME/USRDIR/SYSTEM.DAT": Seekpos: 0003be74'
        )
        self.assertEqual(keys, ["system_dat"])
        self.assertFalse(error)
        self.assertFalse(warning)

    def test_classifies_meaningful_error_but_ignores_audio_busy(self) -> None:
        self.assertTrue(classify_line("E loader failed")[1])
        self.assertFalse(
            classify_line("E SCE_KERNEL_ERROR_AUDIO_CHANNEL_BUSY expected retry")[1]
        )
        error = "E Missing filesystem for 'lang/.ini'"
        self.assertFalse(classify_line(error)[1])
        self.assertTrue(classify_line(error)[2])


if __name__ == "__main__":
    unittest.main()
