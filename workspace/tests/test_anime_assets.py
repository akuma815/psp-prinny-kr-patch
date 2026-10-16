from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import anime_assets  # noqa: E402
import inspect_nispack  # noqa: E402


class AnimeAssetsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.archive = PROJECT / "extracted" / "PSP_GAME" / "USRDIR" / "ANIME.DAT"
        cls.entries = inspect_nispack.read_entries(cls.archive)

    def test_all_entries_have_exact_record_and_texture_spans(self):
        record_count = 0
        texture_count = 0
        with self.archive.open("rb") as stream:
            for entry in self.entries:
                stream.seek(entry.offset)
                records = anime_assets.parse_records(stream.read(entry.size))
                record_count += len(records)
                texture_count += sum(len(record.textures) for record in records)
        self.assertEqual(record_count, 156)
        self.assertEqual(texture_count, 458)

    def test_representative_texture_decodes(self):
        entry = next(item for item in self.entries if item.name == "anime97.dat")
        with self.archive.open("rb") as stream:
            stream.seek(entry.offset)
            data = stream.read(entry.size)
        record = anime_assets.parse_records(data)[0]
        image = anime_assets.decode_texture(data, record, 0)
        self.assertEqual(image.size, (256, 256))
        self.assertEqual(image.mode, "RGBA")

    def test_start_anime00_population(self):
        import inspect_start_dat
        start = PROJECT / "work" / "system" / "start.dat"
        _, entries = inspect_start_dat.read_entries(start)
        entry = next(item for item in entries if item.name == "anime00.dat")
        with start.open("rb") as stream:
            stream.seek(entry.data_start)
            records = anime_assets.parse_records(stream.read(entry.span))
        self.assertEqual(len(records), 89)
        self.assertEqual(sum(len(record.textures) for record in records), 179)


if __name__ == "__main__":
    unittest.main()
