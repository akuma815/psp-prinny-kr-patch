from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import build_baked_graphics_bulk_preview as bulk  # noqa: E402


class BakedGraphicsBulkPreviewTests(unittest.TestCase):
    def test_existing_aliases_are_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "textures.ini"
            path.write_text(
                "[options]\nversion = 1\n\n[hashes]\noldhash = old.png\n",
                encoding="utf-8",
            )
            aliases = bulk.read_existing_aliases(path)
            aliases["newhash"] = "new.png"
            bulk.write_aliases(path, aliases)
            text = path.read_text(encoding="utf-8")
            self.assertIn("oldhash = old.png", text)
            self.assertIn("newhash = new.png", text)

    def test_install_maps_same_prefix_and_size_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "generated"
            pack = root / "pack"
            dumps = pack / "new"
            output.mkdir()
            dumps.mkdir(parents=True)
            Image.new("RGBA", (4, 4), "red").save(output / "draft.png")
            Image.new("RGBA", (4, 4), "blue").save(dumps / "1234567890abcdef11111111.png")
            Image.new("RGBA", (2, 2), "blue").save(dumps / "1234567890abcdef22222222.png")
            jobs = [("asset", "draft.png", object(), root / "source.png", tuple())]
            config = {"assets": [{"id": "asset", "dump_names": ["1234567890abcdefaaaaaaaa.png"]}]}
            installed, pending, ini = bulk.install_live_previews(output, jobs, config, pack)
            self.assertEqual(installed[0]["alias_count"], 2)
            self.assertEqual(pending, [])
            text = (pack / "textures.ini").read_text(encoding="utf-8")
            self.assertIn("1234567890abcdef11111111 = 1234567890abcdefaaaaaaaa.png", text)
            self.assertNotIn("22222222", text)
            self.assertEqual(ini["alias_count"], 2)


if __name__ == "__main__":
    unittest.main()
