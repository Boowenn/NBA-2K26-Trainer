import json
import tempfile
import unittest
from pathlib import Path

from nba2k26_trainer.core.offsets import initialize_offsets
from nba2k26_trainer.presets import (
    builtin_presets,
    export_custom_preset,
    load_custom_preset,
    resolve_preset_values,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "config" / "offsets_2k26.json"


class PresetTests(unittest.TestCase):
    def setUp(self):
        self.config = initialize_offsets(str(CONFIG_PATH))

    def test_builtin_presets_map_to_known_attributes(self):
        for preset in builtin_presets():
            with self.subTest(preset=preset.name):
                values, unresolved = resolve_preset_values(self.config, preset.values_by_description)
                self.assertTrue(values)
                self.assertEqual(unresolved, [])

    def test_resolve_preset_values_clamps_out_of_range_values(self):
        values, unresolved = resolve_preset_values(
            self.config,
            {
                "Three-Point Shot": 999,
                "Deadeye": -10,
            },
        )

        self.assertEqual(unresolved, [])
        three_point = self.config.find_attribute_by_description("Three-Point Shot")
        deadeye = self.config.find_attribute_by_description("Deadeye")
        self.assertIsNotNone(three_point)
        self.assertIsNotNone(deadeye)
        self.assertEqual(values[three_point.name], 99)
        self.assertEqual(values[deadeye.name], 0)

    def test_export_and_load_custom_preset_round_trip(self):
        payload = {
            "Three-Point Shot": 91,
            "Shot IQ": 88,
            "Deadeye": 4,
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            preset_path = Path(temp_dir) / "custom_preset.json"
            export_custom_preset(
                str(preset_path),
                "Bench Gunner",
                self.config,
                payload,
                description="Saved from modified attributes only.",
            )

            raw_data = json.loads(preset_path.read_text(encoding="utf-8"))
            self.assertEqual(raw_data["name"], "Bench Gunner")
            self.assertEqual(len(raw_data["values"]), 3)

            preset = load_custom_preset(str(preset_path))
            self.assertEqual(preset.name, "Bench Gunner")
            self.assertEqual(preset.values_by_description["Three-Point Shot"], 91)
            self.assertEqual(preset.values_by_description["Shot IQ"], 88)
            self.assertEqual(preset.values_by_description["Deadeye"], 4)


if __name__ == "__main__":
    unittest.main()
