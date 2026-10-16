from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import base_talk  # noqa: E402
import nsf_links  # noqa: E402


class NsfLinkTests(unittest.TestCase):
    def test_all_basetalk_keys_resolve_in_demo_nsf(self) -> None:
        table = base_talk.parse(
            (PROJECT / "work" / "system" / "start_assets" / "BaseTalk.dat").read_bytes()
        )
        links = nsf_links.parse_key_map((PROJECT / "work" / "script" / "demo.nsf").read_bytes())
        resolved = nsf_links.resolve(table, links)
        self.assertEqual(len(links), 531)
        self.assertEqual(len(resolved), 72)
        self.assertEqual(resolved[0x00C65D4A], 0x00029F28)
        self.assertEqual(resolved[0x00C67C80], 0x0002EC9C)

    def test_demo_nsf_layout(self) -> None:
        nsf = nsf_links.parse_nsf((PROJECT / "work" / "script" / "demo.nsf").read_bytes())
        self.assertEqual(nsf.code_base, 0x2E10)
        self.assertEqual(len(nsf.code), 0x30D70)
        self.assertEqual(nsf.block_count, 939)
        self.assertEqual(nsf.blocks[0].start, 0)
        self.assertEqual(nsf.blocks[0].end, 0x747)
        self.assertTrue(all(link.script_offset in {block.start for block in nsf.blocks} for link in nsf.links))


if __name__ == "__main__":
    unittest.main()
