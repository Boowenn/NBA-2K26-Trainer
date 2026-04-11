import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "config" / "offsets_2k26.json"


class OffsetsConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            cls.raw = json.load(handle)

    def test_player_table_pointer_matches_known_good_snapshot(self):
        player_table = self.raw["player_table"]
        self.assertEqual(player_table["base_pointer"], 0x79D7EA0)
        self.assertEqual(player_table["base_pointer_hex"].lower(), "0x79d7ea0")

    def test_overall_rating_offset_matches_known_good_snapshot(self):
        overall_attr = next(
            attr
            for attr in self.raw["attributes"]["基本信息"]
            if attr.get("description") == "Overall Rating"
        )
        self.assertEqual(overall_attr["offset"], 1047)


if __name__ == "__main__":
    unittest.main()
