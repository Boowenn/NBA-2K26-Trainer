import csv
import tempfile
import unittest

from nba2k26_trainer.prospects import (
    analyze_prospect_snapshot,
    compare_prospect_snapshots,
    export_prospect_board_csv,
    export_prospect_trend_csv,
    format_prospect_report,
    format_prospect_trend_report,
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

    def test_compare_prospect_snapshots_surfaces_risers_and_fallers(self):
        left_snapshot = {
            "scope_name": "Preseason",
            "players": [
                {
                    "player_key": "elite wing",
                    "index": 1,
                    "full_name": "Elite Wing",
                    "team_name": "Spurs",
                    "position": "SF",
                    "overall": 77,
                    "age": 20,
                    "birth_year": 2006,
                    "attributes": {
                        "Potential": 90,
                        "Avg Potential %": 88,
                        "Boom % (positive growth)": 82,
                        "Bust % (negative growth)": 12,
                        "Three-Point Shot": 88,
                        "Mid-Range Shot": 84,
                        "Shot IQ": 86,
                        "Offensive Consistency": 80,
                        "Stamina": 84,
                    },
                },
                {
                    "player_key": "point stopper",
                    "index": 2,
                    "full_name": "Point Stopper",
                    "team_name": "Spurs",
                    "position": "SG",
                    "overall": 79,
                    "age": 22,
                    "birth_year": 2004,
                    "attributes": {
                        "Potential": 89,
                        "Avg Potential %": 87,
                        "Boom % (positive growth)": 78,
                        "Bust % (negative growth)": 8,
                        "Perimeter Defense": 94,
                        "Steal": 92,
                        "Pass Perception": 90,
                        "Shot IQ": 84,
                        "Offensive Consistency": 82,
                        "Stamina": 88,
                    },
                },
                {
                    "player_key": "bench project",
                    "index": 3,
                    "full_name": "Bench Project",
                    "team_name": "Spurs",
                    "position": "PF",
                    "overall": 73,
                    "age": 23,
                    "birth_year": 2003,
                    "attributes": {
                        "Potential": 82,
                        "Avg Potential %": 80,
                        "Boom % (positive growth)": 65,
                        "Bust % (negative growth)": 18,
                    },
                },
            ],
        }
        right_snapshot = {
            "scope_name": "Trade Deadline",
            "players": [
                {
                    "player_key": "elite wing",
                    "index": 1,
                    "full_name": "Elite Wing",
                    "team_name": "Spurs",
                    "position": "SF",
                    "overall": 81,
                    "age": 20,
                    "birth_year": 2006,
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
                    "player_key": "point stopper",
                    "index": 2,
                    "full_name": "Point Stopper",
                    "team_name": "Spurs",
                    "position": "SG",
                    "overall": 76,
                    "age": 22,
                    "birth_year": 2004,
                    "attributes": {
                        "Potential": 84,
                        "Avg Potential %": 82,
                        "Boom % (positive growth)": 66,
                        "Bust % (negative growth)": 18,
                        "Perimeter Defense": 90,
                        "Steal": 88,
                        "Pass Perception": 86,
                        "Shot IQ": 78,
                        "Offensive Consistency": 75,
                        "Stamina": 84,
                    },
                },
                {
                    "player_key": "new shooter",
                    "index": 4,
                    "full_name": "New Shooter",
                    "team_name": "Spurs",
                    "position": "SG",
                    "overall": 75,
                    "age": 21,
                    "birth_year": 2005,
                    "attributes": {
                        "Potential": 88,
                        "Avg Potential %": 86,
                        "Boom % (positive growth)": 84,
                        "Bust % (negative growth)": 9,
                        "Three-Point Shot": 90,
                        "Mid-Range Shot": 85,
                        "Shot IQ": 87,
                        "Offensive Consistency": 82,
                        "Stamina": 85,
                    },
                },
            ],
        }

        trend = compare_prospect_snapshots(left_snapshot, right_snapshot, max_age=24, min_potential=80)

        self.assertEqual(len(trend["risers"]), 1)
        self.assertEqual(trend["risers"][0]["full_name"], "Elite Wing")
        self.assertGreater(trend["risers"][0]["score_delta"], 0)
        self.assertEqual(len(trend["fallers"]), 1)
        self.assertEqual(trend["fallers"][0]["full_name"], "Point Stopper")
        self.assertLess(trend["fallers"][0]["score_delta"], 0)
        self.assertEqual(len(trend["added"]), 1)
        self.assertEqual(trend["added"][0]["full_name"], "New Shooter")
        self.assertEqual(len(trend["removed"]), 1)
        self.assertEqual(trend["removed"][0]["full_name"], "Bench Project")

    def test_format_and_export_prospect_trend_outputs(self):
        trend = {
            "left_board": {"scope_name": "Preseason", "qualified_count": 2, "average_score": 80.1},
            "right_board": {"scope_name": "Deadline", "qualified_count": 3, "average_score": 82.4},
            "compared_count": 2,
            "average_score_delta": 1.8,
            "risers": [
                {
                    "full_name": "Elite Wing",
                    "team_name": "Spurs",
                    "position": "SF",
                    "score_delta": 3.6,
                    "overall_delta": 4,
                    "potential_delta": 4,
                    "tier_before": "Starter Bet",
                    "tier_after": "Blue Chip",
                    "growth_before": "Franchise Prospect",
                    "growth_after": "Hold Ceiling",
                    "notes": "potential +4, overall +4, tier Starter Bet -> Blue Chip",
                }
            ],
            "fallers": [
                {
                    "full_name": "Point Stopper",
                    "team_name": "Spurs",
                    "position": "SG",
                    "score_delta": -2.1,
                    "overall_delta": -3,
                    "potential_delta": -5,
                    "tier_before": "Starter Bet",
                    "tier_after": "Rotation Swing",
                    "growth_before": "Franchise Prospect",
                    "growth_after": "Monitor",
                    "notes": "potential -5, overall -3",
                }
            ],
            "added": [
                {
                    "player_key": "new shooter",
                    "full_name": "New Shooter",
                    "team_name": "Spurs",
                    "position": "SG",
                    "prospect_score": 82.8,
                    "overall": 75,
                    "potential": 88,
                    "tier": "Starter Bet",
                    "growth_plan": "Franchise Prospect",
                    "role_track": "Sniper Wing",
                }
            ],
            "removed": [
                {
                    "player_key": "bench project",
                    "full_name": "Bench Project",
                    "team_name": "Spurs",
                    "position": "PF",
                    "prospect_score": 72.0,
                    "overall": 73,
                    "potential": 82,
                    "tier": "Rotation Swing",
                    "growth_plan": "Monitor",
                    "role_track": "Franchise Prospect",
                }
            ],
            "changed": [
                {
                    "player_key": "elite wing",
                    "full_name": "Elite Wing",
                    "team_name": "Spurs",
                    "position": "SF",
                    "status": "Riser",
                    "score_before": 84.0,
                    "score_after": 87.6,
                    "score_delta": 3.6,
                    "overall_before": 77,
                    "overall_after": 81,
                    "overall_delta": 4,
                    "potential_before": 90,
                    "potential_after": 94,
                    "potential_delta": 4,
                    "tier_before": "Starter Bet",
                    "tier_after": "Blue Chip",
                    "growth_before": "Franchise Prospect",
                    "growth_after": "Hold Ceiling",
                    "role_before": "Sniper Wing",
                    "role_after": "Sniper Wing",
                    "notes": "potential +4, overall +4, tier Starter Bet -> Blue Chip",
                }
            ],
        }

        report = format_prospect_trend_report(trend)
        self.assertIn("Prospect Trend", report)
        self.assertIn("Top Risers", report)
        self.assertIn("New Board Entries", report)
        self.assertIn("Dropped From Board", report)

        with tempfile.TemporaryDirectory() as temp_dir:
            filepath = f"{temp_dir}\\prospect_trend.csv"
            export_prospect_trend_csv(filepath, trend)

            with open(filepath, "r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)

        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["full_name"], "Elite Wing")
        self.assertEqual(rows[0]["status"], "Riser")
        self.assertIn(rows[1]["status"], {"New Entry", "Dropped"})


if __name__ == "__main__":
    unittest.main()
