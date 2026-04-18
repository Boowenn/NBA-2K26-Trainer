import tempfile
import unittest
from pathlib import Path

from nba2k26_trainer.core.offsets import AttributeDef, OffsetConfig, initialize_offsets
from nba2k26_trainer.preset_packs import (
    PresetPackDefinition,
    PresetPackRule,
    builtin_preset_packs,
    format_preset_pack_plan,
    inspect_preset_pack,
    load_preset_pack,
    plan_preset_pack_application,
    save_preset_pack,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "config" / "offsets_2k26.json"


class PresetPackTests(unittest.TestCase):
    def setUp(self):
        self.config = OffsetConfig(
            version="test-offsets",
            game_version="1.0",
            attributes={
                "Scoring": [
                    AttributeDef(name="three_point_shot", offset=0, category="Scoring", description="Three-Point Shot"),
                ],
                "Defense": [
                    AttributeDef(name="steal", offset=1, category="Defense", description="Steal"),
                ],
                "Growth": [
                    AttributeDef(name="potential", offset=2, category="Growth", description="Potential"),
                ],
            },
        )

    def test_plan_preset_pack_assigns_players_by_rule_and_honors_limits(self):
        pack = PresetPackDefinition(
            pack_id="test_pack",
            name="Test Pack",
            description="A small scope pack for unit coverage.",
            rules=(
                PresetPackRule(
                    rule_id="core_ceiling",
                    name="Core Ceiling",
                    description="Boost only one franchise-level youngster.",
                    values_by_description={"Potential": 95},
                    growth_plans=("Franchise Prospect",),
                    max_players=1,
                ),
                PresetPackRule(
                    rule_id="spacing",
                    name="Spacing",
                    description="Apply a shooter template to wings.",
                    values_by_description={"Three-Point Shot": 91},
                    role_tracks=("Sniper Wing",),
                    positions=("SG", "SF"),
                ),
                PresetPackRule(
                    rule_id="stopper",
                    name="Stopper",
                    description="Apply a defense template to stopper profiles.",
                    values_by_description={"Steal": 90},
                    role_tracks=("Two-Way Stopper",),
                    positions=("SF", "PF"),
                ),
            ),
        )
        board = {
            "scope_name": "Unit Test Scope",
            "players": [
                {
                    "index": 10,
                    "full_name": "Chris Core",
                    "team_name": "Test Team",
                    "position": "PF",
                    "age": 21,
                    "overall": 76,
                    "potential": 90,
                    "prospect_score": 86.4,
                    "tier": "Blue Chip",
                    "growth_plan": "Franchise Prospect",
                    "role_track": "Franchise Prospect",
                },
                {
                    "index": 11,
                    "full_name": "Dana Core",
                    "team_name": "Test Team",
                    "position": "SF",
                    "age": 20,
                    "overall": 74,
                    "potential": 88,
                    "prospect_score": 84.1,
                    "tier": "Starter Bet",
                    "growth_plan": "Franchise Prospect",
                    "role_track": "Franchise Prospect",
                },
                {
                    "index": 12,
                    "full_name": "Alex Shooter",
                    "team_name": "Test Team",
                    "position": "SG",
                    "age": 24,
                    "overall": 78,
                    "potential": 83,
                    "prospect_score": 81.0,
                    "tier": "Starter Bet",
                    "growth_plan": "Monitor",
                    "role_track": "Sniper Wing",
                },
                {
                    "index": 13,
                    "full_name": "Ben Stopper",
                    "team_name": "Test Team",
                    "position": "SF",
                    "age": 25,
                    "overall": 79,
                    "potential": 82,
                    "prospect_score": 80.5,
                    "tier": "Starter Bet",
                    "growth_plan": "Monitor",
                    "role_track": "Two-Way Stopper",
                },
            ],
        }

        plan = plan_preset_pack_application(self.config, board, pack)

        self.assertEqual(plan["assigned_player_count"], 3)
        self.assertEqual(plan["unmatched_player_count"], 1)
        self.assertEqual(plan["total_attribute_targets"], 3)
        self.assertEqual([rule["matched_count"] for rule in plan["rules"]], [1, 1, 1])
        self.assertEqual(plan["assignments"][0]["full_name"], "Chris Core")
        self.assertEqual(plan["assignments"][1]["full_name"], "Alex Shooter")
        self.assertEqual(plan["assignments"][1]["preset_name"], "Spacing")
        self.assertEqual(plan["assignments"][2]["full_name"], "Ben Stopper")
        self.assertEqual(plan["assignments"][2]["preset_name"], "Stopper")

        report = format_preset_pack_plan(plan)
        self.assertIn("Preset Pack: Test Pack", report)
        self.assertIn("Assigned players: 3", report)
        self.assertIn("Alex Shooter", report)

    def test_save_and_load_preset_pack_round_trip(self):
        pack = PresetPackDefinition(
            pack_id="round_trip_pack",
            name="Round Trip Pack",
            description="Mixed preset references for export coverage.",
            rules=(
                PresetPackRule(
                    rule_id="built_in",
                    name="Built-In Rule",
                    description="Uses a built-in preset id.",
                    preset_id="franchise_prospect",
                    growth_plans=("Franchise Prospect",),
                    max_players=4,
                ),
                PresetPackRule(
                    rule_id="inline",
                    name="Inline Rule",
                    description="Uses inline values for portability.",
                    preset_name="Portable Shooter",
                    values_by_description={"Three-Point Shot": 89, "Steal": 75},
                    positions=("SG", "SF"),
                    role_tracks=("Sniper Wing",),
                ),
            ),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            filepath = Path(temp_dir) / "pack.json"
            save_preset_pack(str(filepath), pack)
            loaded = load_preset_pack(str(filepath))

        self.assertEqual(loaded.pack_id, "round_trip_pack")
        self.assertEqual(loaded.name, "Round Trip Pack")
        self.assertEqual(len(loaded.rules), 2)
        self.assertEqual(loaded.rules[0].preset_id, "franchise_prospect")
        self.assertEqual(loaded.rules[1].preset_name, "Portable Shooter")
        self.assertEqual(loaded.rules[1].values_by_description["Three-Point Shot"], 89)
        self.assertEqual(loaded.rules[1].positions, ("SG", "SF"))

    def test_builtin_preset_packs_resolve_against_real_offsets(self):
        config = initialize_offsets(str(CONFIG_PATH))

        for pack in builtin_preset_packs():
            with self.subTest(pack=pack.name):
                inspection = inspect_preset_pack(config, pack)
                self.assertGreater(inspection["rule_count"], 0)
                for rule in inspection["rules"]:
                    self.assertGreater(rule["mapped_count"], 0)
                    self.assertEqual(rule["unresolved"], [])


if __name__ == "__main__":
    unittest.main()
