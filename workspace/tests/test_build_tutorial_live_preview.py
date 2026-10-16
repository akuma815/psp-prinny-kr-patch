from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import build_tutorial_live_preview  # noqa: E402


class TutorialLivePreviewTests(unittest.TestCase):
    def test_observed_hash_variants_map_to_the_canonical_replacement(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dumps = root / "new"
            replacements = root / "pack"
            dumps.mkdir()
            replacements.mkdir()
            (replacements / "textures.ini").write_text(
                "[options]\nversion = 1\n\n[hashes]\nkept = bulk.png\n",
                encoding="utf-8",
            )
            Image.new("RGBA", (2, 2)).save(dumps / "1234567890abcdef11111111.png")
            Image.new("RGBA", (2, 2)).save(dumps / "1234567890abcdef22222222.png")
            Image.new("RGBA", (1, 1)).save(dumps / "1234567890abcdef33333333.png")
            result = build_tutorial_live_preview.write_texture_aliases(
                dumps,
                replacements,
                [{
                    "output": (replacements / "1234567890abcdefaaaaaaaa.png").as_posix(),
                    "size": [2, 2],
                }],
            )
            ini = (replacements / "textures.ini").read_text(encoding="utf-8")
            self.assertEqual(result["alias_count"], 2)
            self.assertIn(
                "1234567890abcdef11111111 = 1234567890abcdefaaaaaaaa.png",
                ini,
            )
            self.assertIn(
                "1234567890abcdef22222222 = 1234567890abcdefaaaaaaaa.png",
                ini,
            )
            self.assertNotIn("33333333", ini)
            self.assertIn("kept = bulk.png", ini)

    def test_palette_fallback_only_fills_missing_indices(self):
        mapping = {0: (0, 0, 0, 0), 1: (1, 1, 1, 1)}
        confidence = {0: 1.0, 1: 0.9}
        added = build_tutorial_live_preview.merge_palette_fallback(
            mapping,
            confidence,
            {1: (9, 9, 9, 9), 2: (2, 2, 2, 2)},
            {1: 0.8, 2: 0.7},
        )
        self.assertEqual(added, [2])
        self.assertEqual(mapping[1], (1, 1, 1, 1))
        self.assertEqual(mapping[2], (2, 2, 2, 2))
        self.assertEqual(confidence[2], 0.7)

    def test_unchanged_pixels_are_preserved_and_changed_pixels_use_palette(self):
        baseline = Image.new("L", (2, 1))
        baseline.putdata([0, 1])
        dump = Image.new("RGBA", (2, 1))
        dump.putdata([(90, 40, 10, 0), (10, 20, 30, 255)])

        mapping, confidence = build_tutorial_live_preview.derive_rgba_palette(baseline, dump)
        self.assertEqual(mapping[0], (0, 0, 0, 0))
        self.assertEqual(mapping[1], (10, 20, 30, 255))
        self.assertEqual(confidence, {0: 1.0, 1: 1.0})

        unchanged = build_tutorial_live_preview.render_replacement(
            baseline, baseline, mapping, dump
        )
        self.assertEqual(
            list(build_tutorial_live_preview.pixel_data(unchanged)),
            list(build_tutorial_live_preview.pixel_data(dump)),
        )

        candidate = Image.new("L", (2, 1))
        candidate.putdata([1, 0])
        changed = build_tutorial_live_preview.render_replacement(
            baseline, candidate, mapping, dump
        )
        self.assertEqual(
            list(build_tutorial_live_preview.pixel_data(changed)),
            [(10, 20, 30, 255), (0, 0, 0, 0)],
        )

        stale_dump = Image.new("RGBA", (2, 1))
        stale_dump.putdata([(99, 99, 99, 255), (10, 20, 30, 255)])
        forced = build_tutorial_live_preview.render_replacement(
            baseline, baseline, mapping, stale_dump, {0}
        )
        self.assertEqual(
            list(build_tutorial_live_preview.pixel_data(forced)),
            [(0, 0, 0, 0), (10, 20, 30, 255)],
        )


if __name__ == "__main__":
    unittest.main()
