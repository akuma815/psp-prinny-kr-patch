from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "workspace" / "scripts"))

import didt  # noqa: E402


EXPECTED = {
    "DL0000.EDAT": {
        "size": 1624784,
        "sha256": "a0209702de5210b2f35c57e7c12bfddbeb691200de06769b615ca50254d48c1b",
        "index": 0,
        "records": 29,
        "nonempty_ddem": 83,
        "nonempty_dsti": 9,
        "first_id": 0x55F0,
        "last_id": 0x5628,
        "ddem_footer": 8,
    },
    "DL0001.EDAT": {
        "size": 1540688,
        "sha256": "86b48d56b6ba853f09ffb0a524ccebf4f601c78cb0f4937cb885ec8815bdb7a7",
        "index": 1,
        "records": 23,
        "nonempty_ddem": 68,
        "nonempty_dsti": 11,
        "first_id": 0x53FC,
        "last_id": 0x5428,
        "ddem_footer": 0,
    },
    "DL0002.EDAT": {
        "size": 1365296,
        "sha256": "3fbc26ed99c1b3f474e50dd5290eb0497e61f0a7e8e9268fb82980a426079be9",
        "index": 2,
        "records": 15,
        "nonempty_ddem": 31,
        "nonempty_dsti": 11,
        "first_id": 0xC350,
        "last_id": 0xC36A,
        "ddem_footer": 0,
    },
}

EXPECTED_CHUNKS = (
    "DSTI",
    "DICO",
    "DTZO",
    "DAMM",
    "DAMP",
    "DABG",
    "DBMM",
    "DBMP",
    "DBBG",
    "DANM",
    "DSCR",
    "DCHR",
    "DDEM",
    "DCLT",
    "NEND",
)


class DidtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source_dir = PROJECT / "original" / "Prinny DLC"

    def test_supported_dlc_roundtrips_and_matches_baseline(self) -> None:
        for filename, expected in EXPECTED.items():
            with self.subTest(filename=filename):
                source = (self.source_dir / filename).read_bytes()
                self.assertEqual(len(source), expected["size"])
                self.assertEqual(hashlib.sha256(source).hexdigest(), expected["sha256"])
                container = didt.parse(source)
                self.assertEqual(container.to_bytes(), source)
                self.assertEqual(container.dlc_index, expected["index"])
                self.assertEqual(container.title, didt.parse_dsti(container.chunk("DSTI").payload).slots[0].lstrip("\u3000"))
                self.assertEqual(tuple(chunk.tag for chunk in container.chunks), EXPECTED_CHUNKS)

                ddem = didt.parse_ddem(container.chunk("DDEM").payload)
                self.assertEqual(ddem.to_bytes(), container.chunk("DDEM").payload)
                self.assertEqual(len(ddem.records), expected["records"])
                self.assertEqual(ddem.records[0].record_id, expected["first_id"])
                self.assertEqual(ddem.records[-1].record_id, expected["last_id"])
                self.assertEqual(len(ddem.footer), expected["ddem_footer"])
                self.assertEqual(
                    sum(
                        bool(text)
                        for record in ddem.records
                        for text in (record.speaker, *record.lines)
                    ),
                    expected["nonempty_ddem"],
                )

                dsti = didt.parse_dsti(container.chunk("DSTI").payload)
                self.assertEqual(dsti.to_bytes(), container.chunk("DSTI").payload)
                self.assertEqual(len(dsti.slots), 11)
                self.assertEqual(sum(bool(text) for text in dsti.slots), expected["nonempty_dsti"])

    def test_known_52_base_references_and_15_dlc_local_records(self) -> None:
        ids_by_file: dict[str, set[int]] = {}
        for filename in EXPECTED:
            container = didt.parse((self.source_dir / filename).read_bytes())
            ids_by_file[filename] = {
                record.record_id
                for record in didt.parse_ddem(container.chunk("DDEM").payload).records
            }
        base_references = set(range(0x53FC, 0x5429, 2)) | set(range(0x55F0, 0x5629, 2))
        all_ids = set().union(*ids_by_file.values())
        self.assertEqual(len(all_ids), 67)
        self.assertEqual(all_ids & base_references, base_references)
        self.assertEqual(len(all_ids - base_references), 15)
        self.assertEqual(ids_by_file["DL0002.EDAT"], all_ids - base_references)

    def test_rejects_nonzero_ddem_record_tail(self) -> None:
        source = (self.source_dir / "DL0001.EDAT").read_bytes()
        container = didt.parse(source)
        payload = bytearray(container.chunk("DDEM").payload)
        payload[4 + 129] = 1
        with self.assertRaisesRegex(ValueError, "non-zero tail"):
            didt.parse_ddem(bytes(payload))

    def test_rejects_bytes_after_nend(self) -> None:
        source = (self.source_dir / "DL0001.EDAT").read_bytes()
        with self.assertRaisesRegex(ValueError, "bytes remain after NEND"):
            didt.parse(source + b"X")


if __name__ == "__main__":
    unittest.main()
