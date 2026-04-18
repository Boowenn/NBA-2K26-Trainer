import csv
import tempfile
import unittest

from nba2k26_trainer.prospects import (
    analyze_prospect_snapshot,
    export_prospect_board_csv,
    format_prospect_report,
)


class ProspectTests(unittest.TestCase):
    def test_analyze_prospect_snapshot_scores_and_recommends_tracks(self):
        snapshot = {
            "scope_name": "Team: Spurs",
            "player_count": 3,
            "players": [
                {
                    "index": 1,
                    "player_key": "elite wing",
                    "full_name": "Elite Wing",
                    "team_name": "Spurs",
                    "position": "SF",
                    "overall": 80,
                    "age": 20,
                    "attributes": {
                        "Potential": 94,
                        "Avg Potential %": 92,
                        "Boom % (positive growth)": 90,
                        "Bust % (negative growth)": 6,
                        "Three-Point Shot": 91,
                        "Mid-Range Shot": 88,
                        "Shot IQ": 90,
                        "Offensive Consistency": 86,
                        "Stamina": 88,
                    },
                },
                {
                    "index": 2,
                    "player_key": "defender",
                    "full_name": "Point Stopper",
                    "team_name": "Spurs",
                    "position": "SG",
                    "overall": 77,
                    "age": 22,
                    "attributes": {
                        "Potential": 88,
                        "Avg Potential %": 84,
                        "Boom % (positive growth)": 74,
                        "Bust % (negative growth)": 12,
                        "Perimeter Defense": 93,
                        "Steal": 91,
                        "Pass Perception": 89,
                        "Shot IQ": 79,
                        "Offensive Consistency": 76,
                        "Stamina": 85,
                    },
                },
                {
                    "index": 3,
                    "player_key": "vet",
                    "full_name": "Bench Veteran",
                    "team_name": "Spurs",
                    "position": "PF",
                    "overall": 75,
                    "age": 29,
                    "attributes": {
                        "Potential": 74,
                        "Avg Potential %": 73,
                        "Boom % (positive growth)": 30,
                        "Bust % (negative growth)": 45,
                    },
                },
            ],
        }

        board = analyze_prospect_snapshot(snapshot, max_age=24, min_potential=80)

        self.assertEqual(board["qualified_count"], 2)
        self.assertEqual(board["players"][0]["full_name"], "Elite Wing")
        self.assertEqual(board["players"][0]["growth_plan"], "Franchise Prospect")
        self.assertEqual(board["players"][0]["role_track"], "Sniper Wing")
        self.assertEqual(board["players"][1]["role_track"], "Two-Way Stopper")
        self.assertIn(board["players"][0]["tier"], {"Blue Chip", "Starter Bet"})

    def test_format_prospect_report_includes_summary(self):
        board = {
            "scope_name": "Draft Board",
            "player_count": 4,
            "qualified_count": 2,
            "max_age": 23,
            "min_potential": 82,
            "average_score": 84.4,
            "tier_counts": {"Blue Chip": 1, "Starter Bet": 1},
            "role_track_counts": {"Sniper Wing": 1, "Two-Way Stopper": 1},
            "players": [
                {
                    "full_name": "Elite Wing",
                    "team_name": "Spurs",
                    "position": "SF",
                    "prospect_score": 88.2,
                    "tier": "Blue Chip",
                    "growth_plan": "Franchise Prospect",
                    "role_track": "Sniper Wing",
                    "age": 20,
                    "overall": 80,
                    "potential": 94,
                    "boom": 90,
                    "bust": 6,
                    "notes": "large ceiling gap, high-growth profile",
                }
            ],
        }

        report = format_prospect_report(board)

        self.assertIn("Prospect Lab", report)
        self.assertIn("Qualified prospects: 2 / 4", report)
        self.assertIn("Tiers: Blue Chip (1), Starter Bet (1)", report)
        self.assertIn("Elite Wing", report)
        self.assertIn("Growth: Franchise Prospect", report)

    def test_export_prospect_board_csv_writes_rows(self):
        board = {
            "players": [
                {
                    "full_name": "Elite Wing",
                    "team_name": "Spurs",
                    "position": "SF",
                    "age": 20,
                    "overall": 80,
                    "potential": 94,
                    "average_potential": 92,
                    "boom": 90,
                    "bust": 6,
                    "development_gap": 14,
                    "prospect_score": 88.2,
                    "tier": "Blue Chip",
                    "growth_plan": "Franchise Prospect",
                    "role_track": "Sniper Wing",
                    "notes": "large ceiling gap",
                    "index": 1,
                    "player_key": "elite wing",
                }
            ]
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            filepath = f"{temp_dir}\\prospect_board.csv"
            export_prospect_board_csv(filepath, board)

            with open(filepath, "r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["full_name"], "Elite Wing")
        self.assertEqual(rows[0]["tier"], "Blue Chip")
        self.assertEqual(rows[0]["growth_plan"], "Franchise Prospect")


if __name__ == "__main__":
    unittest.main()
