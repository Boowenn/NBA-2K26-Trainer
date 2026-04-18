import unittest

from nba2k26_trainer.core.offsets import AttributeDef, OffsetConfig
from nba2k26_trainer.models.player import Player
from nba2k26_trainer.snapshots import build_snapshot, diff_snapshots, format_diff_report


class FakePlayerManager:
    def __init__(self, values_by_index):
        self.values_by_index = values_by_index

    def read_all_attributes(self, player):
        return dict(self.values_by_index[player.index])


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.config = OffsetConfig(
            version="test-offsets",
            game_version="1.0",
            attributes={
                "Scoring": [
                    AttributeDef(name="三分球", offset=0, category="Scoring", description="Three-Point Shot"),
                    AttributeDef(name="投篮智商", offset=1, category="Scoring", description="Shot IQ"),
                ],
                "Defense": [
                    AttributeDef(name="抢断", offset=2, category="Defense", description="Steal"),
                ],
            },
        )

    def test_build_snapshot_uses_attribute_display_names(self):
        player = Player(
            index=0,
            record_address=0x1000,
            first_name="Stephen",
            last_name="Curry",
            team_id=9,
            team_name="GSW Warriors",
            overall=97,
            age=38,
            birth_year=1988,
            position="PG",
        )
        manager = FakePlayerManager(
            {
                0: {
                    "三分球": 99,
                    "投篮智商": 97,
                    "抢断": 78,
                }
            }
        )

        snapshot = build_snapshot(
            self.config,
            manager,
            [player],
            roster_mode="current",
            scope_name="Team: GSW Warriors",
        )

        self.assertEqual(snapshot["player_count"], 1)
        self.assertEqual(snapshot["scope_name"], "Team: GSW Warriors")
        self.assertEqual(snapshot["players"][0]["attributes"]["Three-Point Shot"], 99)
        self.assertEqual(snapshot["players"][0]["attributes"]["Shot IQ"], 97)
        self.assertEqual(snapshot["players"][0]["attributes"]["Steal"], 78)

    def test_diff_snapshots_detects_added_removed_and_changed(self):
        left_snapshot = {
            "scope_name": "Left",
            "player_count": 2,
            "players": [
                {
                    "full_name": "Luka Doncic",
                    "team_name": "Lakers",
                    "team_id": 13,
                    "position": "PG",
                    "overall": 96,
                    "age": 28,
                    "birth_year": 1999,
                    "attributes": {
                        "Three-Point Shot": 95,
                        "Shot IQ": 96,
                    },
                },
                {
                    "full_name": "Austin Reaves",
                    "team_name": "Lakers",
                    "team_id": 13,
                    "position": "SG",
                    "overall": 85,
                    "age": 28,
                    "birth_year": 1998,
                    "attributes": {
                        "Three-Point Shot": 83,
                        "Shot IQ": 86,
                    },
                },
            ],
        }
        right_snapshot = {
            "scope_name": "Right",
            "player_count": 2,
            "players": [
                {
                    "full_name": "Luka Doncic",
                    "team_name": "Lakers",
                    "team_id": 13,
                    "position": "PG",
                    "overall": 97,
                    "age": 28,
                    "birth_year": 1999,
                    "attributes": {
                        "Three-Point Shot": 99,
                        "Shot IQ": 96,
                    },
                },
                {
                    "full_name": "Jarred Vanderbilt",
                    "team_name": "Lakers",
                    "team_id": 13,
                    "position": "SF",
                    "overall": 80,
                    "age": 27,
                    "birth_year": 2000,
                    "attributes": {
                        "Three-Point Shot": 74,
                        "Shot IQ": 77,
                    },
                },
            ],
        }

        diff_result = diff_snapshots(left_snapshot, right_snapshot)

        self.assertEqual(len(diff_result["added"]), 1)
        self.assertEqual(diff_result["added"][0]["full_name"], "Jarred Vanderbilt")
        self.assertEqual(len(diff_result["removed"]), 1)
        self.assertEqual(diff_result["removed"][0]["full_name"], "Austin Reaves")
        self.assertEqual(len(diff_result["changed"]), 1)
        changed_player = diff_result["changed"][0]
        self.assertEqual(changed_player["right_player"]["full_name"], "Luka Doncic")
        self.assertIn("overall", changed_player["metadata_changes"])
        self.assertIn("Three-Point Shot", changed_player["attribute_changes"])

        report = format_diff_report(diff_result)
        self.assertIn("Added players:   1", report)
        self.assertIn("Removed players: 1", report)
        self.assertIn("Changed players: 1", report)
        self.assertIn("Luka Doncic", report)


if __name__ == "__main__":
    unittest.main()
