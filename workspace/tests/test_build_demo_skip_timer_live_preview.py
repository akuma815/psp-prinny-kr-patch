import importlib.util
import tempfile
import unittest
from pathlib import Path

from PIL import Image


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "build_demo_skip_timer_live_preview.py"
)
SPEC = importlib.util.spec_from_file_location("demo_skip_timer_preview", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class DemoSkipNormalizationTests(unittest.TestCase):
    def setUp(self):
        self.font = Path(
            "G:/Downloads/Korean Traslate Project/Font/"
            "HancomMalangMalang-Regular.ttf"
        )
        if not self.font.is_file():
            self.skipTest(f"font not found: {self.font}")

    def test_only_text_cells_are_redrawn(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path = root / "source.png"
            output_path = root / "output.png"

            source = Image.new("RGBA", MODULE.DEMO_SIZE, (10, 20, 30, 40))
            source.save(source_path)

            result = MODULE.build_demo(source_path, output_path, self.font)
            output = Image.open(output_path).convert("RGBA")

            self.assertEqual(output.getpixel((0, 0)), (10, 20, 30, 40))
            self.assertNotEqual(
                output.crop(MODULE.DEMO_TEXT_BOUNDS).tobytes(),
                source.crop(MODULE.DEMO_TEXT_BOUNDS).tobytes(),
            )
            self.assertEqual(result["changed_pixels_outside"], 0)
            self.assertEqual(
                [item["character"] for item in result["rendered"]],
                list("리플레이저장데모스킵"),
            )

    def test_all_states_receive_identical_text_pixels(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            bands = []
            for index, color in enumerate(
                ((255, 0, 0, 255), (0, 255, 0, 128), (0, 0, 255, 32))
            ):
                source_path = root / f"source-{index}.png"
                output_path = root / f"output-{index}.png"
                Image.new("RGBA", MODULE.DEMO_SIZE, color).save(source_path)
                MODULE.build_demo(source_path, output_path, self.font)
                bands.append(
                    Image.open(output_path)
                    .convert("RGBA")
                    .crop(MODULE.DEMO_TEXT_BOUNDS)
                    .tobytes()
                )

            self.assertEqual(bands[0], bands[1])
            self.assertEqual(bands[1], bands[2])


if __name__ == "__main__":
    unittest.main()
