import unittest
from pathlib import Path

from nba2k26_trainer.core.offsets import initialize_offsets
from nba2k26_trainer.models.player import (
    PERFECT_SHOT_SHARED_LEGACY_PATCHES_ENABLED,
    PERFECT_SHOT_SHARED_RUNTIME_PATCHES_ENABLED,
    PERFECT_SHOT_ENTRY_COUNT_OFFSET,
    PERFECT_SHOT_ENABLE_OFFSET,
    PERFECT_SHOT_ENTRY_ARRAY_OFFSET,
    PERFECT_SHOT_LEGACY_STATE_PATCHES,
    PERFECT_SHOT_LOCK_TIMER_ALT_OFFSET,
    PERFECT_SHOT_LOCK_TIMER_OFFSET,
    PERFECT_SHOT_MANAGER_SLOT_OFFSET,
    SHOT_RUNTIME_AI_HUMAN_DELTA_OFFSET,
    SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE,
    SHOT_RUNTIME_AI_TEAM_DELTA_OFFSET,
    SHOT_RUNTIME_COVERAGE_DELTA_OFFSET,
    SHOT_RUNTIME_CONTAINER_OFFSET,
    SHOT_RUNTIME_ENTRY_BASE_OFFSET,
    SHOT_RUNTIME_ENTRY_COUNT_OFFSET,
    SHOT_RUNTIME_GLOBAL_PTR_SLOT,
    SHOT_RUNTIME_IMPACT_DELTA_OFFSET,
    SHOT_RUNTIME_PERFECT_PATCHES,
    PlayerManager,
    Player,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "config" / "offsets_2k26.json"


class FakeMemory:
    base_address = 0x140000000

    def __init__(self):
        self._bytes = {}

    def write_bytes_at(self, address: int, data: bytes) -> None:
        for index, byte in enumerate(data):
            self._bytes[address + index] = byte

    def read_bytes(self, address: int, size: int):
        return bytes(self._bytes.get(address + index, 0) for index in range(size))

    def write_bytes(self, address: int, data: bytes) -> bool:
        self.write_bytes_at(address, data)
        return True

    def read_uint8(self, address: int):
        return self.read_bytes(address, 1)[0]

    def write_uint8(self, address: int, value: int) -> bool:
        self.write_bytes_at(address, bytes([value & 0xFF]))
        return True

    def read_uint32(self, address: int):
        return int.from_bytes(self.read_bytes(address, 4), byteorder="little")

    def write_uint32(self, address: int, value: int) -> bool:
        self.write_bytes_at(address, int(value).to_bytes(4, byteorder="little"))
        return True

    def read_uint64(self, address: int):
        return int.from_bytes(self.read_bytes(address, 8), byteorder="little")

    def write_uint64(self, address: int, value: int) -> bool:
        self.write_bytes_at(address, int(value).to_bytes(8, byteorder="little"))
        return True

    def read_bitfield(self, address: int, bit_start: int, bit_length: int):
        byte_offset = bit_start // 8
        total_bits = bit_start % 8 + bit_length
        total_bytes = (total_bits + 7) // 8
        data = self.read_bytes(address + byte_offset, total_bytes)
        value = int.from_bytes(data, byteorder="little")
        shift = bit_start % 8
        mask = (1 << bit_length) - 1
        return (value >> shift) & mask

    def write_bitfield(self, address: int, bit_start: int, bit_length: int, value: int) -> bool:
        byte_offset = bit_start // 8
        total_bits = bit_start % 8 + bit_length
        total_bytes = (total_bits + 7) // 8
        current = self.read_bytes(address + byte_offset, total_bytes)
        current_value = int.from_bytes(current, byteorder="little")
        shift = bit_start % 8
        mask = ((1 << bit_length) - 1) << shift
        next_value = (current_value & ~mask) | ((int(value) << shift) & mask)
        self.write_bytes_at(address + byte_offset, next_value.to_bytes(total_bytes, byteorder="little"))
        return True


class PerfectShotTestPlayerManager(PlayerManager):
    def __init__(self, mem, config, player):
        super().__init__(mem, config)
        self.players = [player]
        self._player = player
        self.god_mode_team_calls = 0
        self.fake_match_entries = [0x710000, 0x711000]

    def scan_players(self, progress_callback=None):
        return self.players

    def summarize_live_gameplay_state(self, player):
        return {
            "match_compact_entries": 2,
            "match_compact_bases": ["0x600000", "0x601000"],
            "attributes": {},
        }

    def _resolve_shot_runtime_team_block_index(self, entry_base, player):
        return 0

    def _get_match_compact_entry_bases(self, player):
        return list(self.fake_match_entries)

    def apply_god_mode_to_team(self, team_id: int, team_name=None):
        self.god_mode_team_calls += 1
        return super().apply_god_mode_to_team(team_id, team_name)


class PerfectShotBetaTests(unittest.TestCase):
    def setUp(self):
        self.mem = FakeMemory()
        self.config = initialize_offsets(str(CONFIG_PATH))
        self.player = Player(
            index=0,
            record_address=0x700000,
            first_name="Luka",
            last_name="Doncic",
            team_id=13,
            team_name="Lakers",
        )
        self.pm = PerfectShotTestPlayerManager(self.mem, self.config, self.player)
        self.global_obj = 0x410000
        self.container = 0x420000
        self.runtime_entry = 0x430000
        self.manager_base = 0x500000
        self.legacy_entry = 0x600000

        self.mem.write_uint64(
            SHOT_RUNTIME_GLOBAL_PTR_SLOT,
            self.global_obj,
        )
        self.mem.write_uint64(
            self.global_obj + SHOT_RUNTIME_CONTAINER_OFFSET,
            self.container,
        )
        self.mem.write_uint32(self.container + SHOT_RUNTIME_ENTRY_COUNT_OFFSET, 1)
        self.mem.write_uint64(
            self.container + SHOT_RUNTIME_ENTRY_BASE_OFFSET,
            self.runtime_entry,
        )

        original_ai_delta = bytes(range(1, SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE + 1))
        original_ai_team_delta = bytes(range(33, 33 + SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE))
        original_coverage_delta = bytes(range(65, 65 + SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE))
        original_impact_delta = bytes(range(97, 97 + SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE))
        self.mem.write_bytes_at(
            self.runtime_entry + SHOT_RUNTIME_AI_TEAM_DELTA_OFFSET,
            original_ai_team_delta,
        )
        self.mem.write_bytes_at(
            self.runtime_entry + SHOT_RUNTIME_AI_HUMAN_DELTA_OFFSET,
            original_ai_delta,
        )
        self.mem.write_bytes_at(
            self.runtime_entry + SHOT_RUNTIME_COVERAGE_DELTA_OFFSET,
            original_coverage_delta,
        )
        self.mem.write_bytes_at(
            self.runtime_entry + SHOT_RUNTIME_IMPACT_DELTA_OFFSET,
            original_impact_delta,
        )
        self.original_ai_team_delta = original_ai_team_delta
        self.original_ai_delta = original_ai_delta
        self.original_coverage_delta = original_coverage_delta
        self.original_impact_delta = original_impact_delta
        self.runtime_patch_originals = {}
        for patch_index, (name, offset, patch_bytes) in enumerate(SHOT_RUNTIME_PERFECT_PATCHES, start=1):
            if offset == SHOT_RUNTIME_AI_TEAM_DELTA_OFFSET:
                self.runtime_patch_originals[name] = self.original_ai_team_delta
                continue
            if offset == SHOT_RUNTIME_AI_HUMAN_DELTA_OFFSET:
                self.runtime_patch_originals[name] = self.original_ai_delta
                continue
            if offset == SHOT_RUNTIME_COVERAGE_DELTA_OFFSET:
                self.runtime_patch_originals[name] = self.original_coverage_delta
                continue
            if offset == SHOT_RUNTIME_IMPACT_DELTA_OFFSET:
                self.runtime_patch_originals[name] = self.original_impact_delta
                continue
            original = bytes(
                ((patch_index * 11) + value_index) % 256
                for value_index in range(len(patch_bytes))
            )
            if original == patch_bytes:
                original = bytes(
                    (((patch_index + 7) * 13) + value_index) % 256
                    for value_index in range(len(patch_bytes))
                )
            self.mem.write_bytes_at(self.runtime_entry + offset, original)
            self.runtime_patch_originals[name] = original

        self.mem.write_uint64(self.mem.base_address + PERFECT_SHOT_MANAGER_SLOT_OFFSET, self.manager_base)
        self.mem.write_uint32(self.manager_base + PERFECT_SHOT_ENTRY_COUNT_OFFSET, 1)
        self.mem.write_uint64(self.manager_base + PERFECT_SHOT_ENTRY_ARRAY_OFFSET, self.legacy_entry)
        self.mem.write_uint8(self.legacy_entry + PERFECT_SHOT_ENABLE_OFFSET, 1)
        self.mem.write_uint32(self.legacy_entry + PERFECT_SHOT_LOCK_TIMER_OFFSET, 123)
        self.mem.write_uint32(self.legacy_entry + PERFECT_SHOT_LOCK_TIMER_ALT_OFFSET, 456)
        self.legacy_patch_originals = {}
        for offset, patch_bytes in PERFECT_SHOT_LEGACY_STATE_PATCHES:
            original = bytes((index + 1) % 256 for index in range(len(patch_bytes)))
            self.mem.write_bytes_at(self.legacy_entry + offset, original)
            self.legacy_patch_originals[offset] = original

    def test_start_perfect_shot_beta_zeroes_ai_delta_and_clears_legacy_lock(self):
        summary = self.pm.start_perfect_shot_beta(self.player)

        self.assertTrue(summary["active"])
        self.assertEqual(summary["target_team_name"], "Lakers")
        self.assertEqual(summary["team_block_index"], 0)
        self.assertEqual(summary["representative_player"], "Luka Doncic")
        self.assertFalse(summary["ai_delta_written"])
        self.assertEqual(summary["match_boost_players"], 1)
        self.assertEqual(summary["match_boost_entries"], 2)
        self.assertGreater(summary["match_boost_writes"], 0)
        self.assertNotIn("boosted_players", summary)
        self.assertNotIn("boosted_attributes", summary)
        self.assertEqual(self.pm.god_mode_team_calls, 0)
        self.assertEqual(
            self.mem.read_bytes(
                self.runtime_entry + SHOT_RUNTIME_AI_TEAM_DELTA_OFFSET,
                SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE,
            ),
            self.original_ai_team_delta,
        )
        self.assertEqual(
            self.mem.read_bytes(
                self.runtime_entry + SHOT_RUNTIME_AI_HUMAN_DELTA_OFFSET,
                SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE,
            ),
            self.original_ai_delta,
        )
        self.assertEqual(
            self.mem.read_bytes(
                self.runtime_entry + SHOT_RUNTIME_COVERAGE_DELTA_OFFSET,
                SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE,
            ),
            self.original_coverage_delta,
        )
        self.assertEqual(
            self.mem.read_bytes(
                self.runtime_entry + SHOT_RUNTIME_IMPACT_DELTA_OFFSET,
                SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE,
            ),
            self.original_impact_delta,
        )
        for name, offset, patch_bytes in SHOT_RUNTIME_PERFECT_PATCHES:
            self.assertEqual(
                self.mem.read_bytes(self.runtime_entry + offset, len(patch_bytes)),
                self.runtime_patch_originals[name],
            )
        self.assertEqual(self.mem.read_uint8(self.legacy_entry + PERFECT_SHOT_ENABLE_OFFSET), 0)
        self.assertEqual(self.mem.read_uint32(self.legacy_entry + PERFECT_SHOT_LOCK_TIMER_OFFSET), 0)
        self.assertEqual(self.mem.read_uint32(self.legacy_entry + PERFECT_SHOT_LOCK_TIMER_ALT_OFFSET), 0)
        for offset, patch_bytes in PERFECT_SHOT_LEGACY_STATE_PATCHES:
            self.assertEqual(
                self.mem.read_bytes(self.legacy_entry + offset, len(patch_bytes)),
                self.legacy_patch_originals[offset],
            )
        self.assertEqual(summary["legacy_state_writes"], 0)
        self.assertEqual(summary["runtime_patch_writes"], 0)
        self.assertEqual(summary["legacy_cleared"], True)
        self.assertEqual(summary["ai_team_delta_written"], PERFECT_SHOT_SHARED_RUNTIME_PATCHES_ENABLED)
        self.assertEqual(summary["human_team_delta_written"], PERFECT_SHOT_SHARED_RUNTIME_PATCHES_ENABLED)
        self.assertEqual(summary["coverage_delta_written"], PERFECT_SHOT_SHARED_RUNTIME_PATCHES_ENABLED)
        self.assertEqual(summary["impact_delta_written"], PERFECT_SHOT_SHARED_RUNTIME_PATCHES_ENABLED)

        driving_layup = self.config.find_attribute_by_description("Driving Layup")
        deadeye = self.config.find_attribute_by_description("Deadeye")
        three_point = self.config.find_attribute_by_description("Three-Point Shot")
        shot_iq = self.config.find_attribute_by_description("Shot IQ")
        self.assertEqual(self.pm.read_match_compact_attribute_values(self.player, driving_layup), [99, 99])
        self.assertEqual(self.pm.read_match_compact_attribute_values(self.player, deadeye), [4, 4])
        self.assertEqual(self.pm._read_attribute_direct(self.player, three_point), 99)
        self.assertEqual(self.pm._read_attribute_direct(self.player, shot_iq), 99)

    def test_refresh_perfect_shot_beta_reapplies_zero_buffer(self):
        self.pm.start_perfect_shot_beta(self.player)
        driving_layup = self.config.find_attribute_by_description("Driving Layup")
        three_point = self.config.find_attribute_by_description("Three-Point Shot")
        self.mem.write_bytes_at(
            self.runtime_entry + SHOT_RUNTIME_AI_TEAM_DELTA_OFFSET,
            bytes([7] * SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE),
        )
        self.mem.write_bytes_at(
            self.runtime_entry + SHOT_RUNTIME_AI_HUMAN_DELTA_OFFSET,
            bytes([9] * SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE),
        )
        self.mem.write_bytes_at(
            self.runtime_entry + SHOT_RUNTIME_COVERAGE_DELTA_OFFSET,
            bytes([5] * SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE),
        )
        self.mem.write_bytes_at(
            self.runtime_entry + SHOT_RUNTIME_IMPACT_DELTA_OFFSET,
            bytes([3] * SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE),
        )
        for offset, patch_bytes in PERFECT_SHOT_LEGACY_STATE_PATCHES:
            self.mem.write_bytes_at(self.legacy_entry + offset, bytes(len(patch_bytes)))
        self.mem.write_uint8(self.player.record_address + driving_layup.offset, 25)
        self.mem.write_uint8(self.player.record_address + three_point.offset, 25)

        summary = self.pm.refresh_perfect_shot_beta()

        self.assertTrue(summary["active"])
        self.assertFalse(summary["ai_delta_written"])
        self.assertNotIn("boosted_players", summary)
        self.assertNotIn("boosted_attributes", summary)
        self.assertEqual(self.pm.god_mode_team_calls, 0)
        self.assertEqual(
            self.mem.read_bytes(
                self.runtime_entry + SHOT_RUNTIME_AI_TEAM_DELTA_OFFSET,
                SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE,
            ),
            bytes([7] * SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE),
        )
        self.assertEqual(
            self.mem.read_bytes(
                self.runtime_entry + SHOT_RUNTIME_AI_HUMAN_DELTA_OFFSET,
                SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE,
            ),
            bytes([9] * SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE),
        )
        self.assertEqual(
            self.mem.read_bytes(
                self.runtime_entry + SHOT_RUNTIME_COVERAGE_DELTA_OFFSET,
                SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE,
            ),
            bytes([5] * SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE),
        )
        self.assertEqual(
            self.mem.read_bytes(
                self.runtime_entry + SHOT_RUNTIME_IMPACT_DELTA_OFFSET,
                SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE,
            ),
            bytes([3] * SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE),
        )
        for name, offset, patch_bytes in SHOT_RUNTIME_PERFECT_PATCHES:
            if offset == SHOT_RUNTIME_AI_TEAM_DELTA_OFFSET:
                expected_bytes = bytes([7] * SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE)
            elif offset == SHOT_RUNTIME_AI_HUMAN_DELTA_OFFSET:
                expected_bytes = bytes([9] * SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE)
            elif offset == SHOT_RUNTIME_COVERAGE_DELTA_OFFSET:
                expected_bytes = bytes([5] * SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE)
            elif offset == SHOT_RUNTIME_IMPACT_DELTA_OFFSET:
                expected_bytes = bytes([3] * SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE)
            else:
                expected_bytes = self.runtime_patch_originals[name]
            self.assertEqual(
                self.mem.read_bytes(self.runtime_entry + offset, len(patch_bytes)),
                expected_bytes,
            )
        for offset, patch_bytes in PERFECT_SHOT_LEGACY_STATE_PATCHES:
            self.assertEqual(
                self.mem.read_bytes(self.legacy_entry + offset, len(patch_bytes)),
                bytes(len(patch_bytes)),
            )
        self.assertEqual(summary["legacy_state_writes"], 0)
        self.assertGreater(summary["roster_boost_writes"], 0)
        self.assertEqual(self.pm._read_attribute_direct(self.player, driving_layup), 99)
        self.assertEqual(self.pm._read_attribute_direct(self.player, three_point), 99)

    def test_stop_perfect_shot_beta_restores_original_ai_delta(self):
        self.pm.start_perfect_shot_beta(self.player)

        summary = self.pm.stop_perfect_shot_beta()

        self.assertFalse(summary["active"])
        self.assertTrue(summary["restored"])
        self.assertGreater(summary["restored_match_writes"], 0)
        self.assertGreater(summary["restored_roster_writes"], 0)
        self.assertEqual(summary["restored_legacy_state_writes"], 0)
        self.assertEqual(summary["target_team_name"], "Lakers")
        self.assertEqual(
            self.mem.read_bytes(
                self.runtime_entry + SHOT_RUNTIME_AI_TEAM_DELTA_OFFSET,
                SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE,
            ),
            self.original_ai_team_delta,
        )
        self.assertEqual(
            self.mem.read_bytes(
                self.runtime_entry + SHOT_RUNTIME_AI_HUMAN_DELTA_OFFSET,
                SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE,
            ),
            self.original_ai_delta,
        )
        self.assertEqual(
            self.mem.read_bytes(
                self.runtime_entry + SHOT_RUNTIME_COVERAGE_DELTA_OFFSET,
                SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE,
            ),
            self.original_coverage_delta,
        )
        self.assertEqual(
            self.mem.read_bytes(
                self.runtime_entry + SHOT_RUNTIME_IMPACT_DELTA_OFFSET,
                SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE,
            ),
            self.original_impact_delta,
        )
        for name, offset, patch_bytes in SHOT_RUNTIME_PERFECT_PATCHES:
            self.assertEqual(
                self.mem.read_bytes(self.runtime_entry + offset, len(patch_bytes)),
                self.runtime_patch_originals[name],
            )
        for offset, original in self.legacy_patch_originals.items():
            self.assertEqual(
                self.mem.read_bytes(self.legacy_entry + offset, len(original)),
                original,
            )
        driving_layup = self.config.find_attribute_by_description("Driving Layup")
        deadeye = self.config.find_attribute_by_description("Deadeye")
        three_point = self.config.find_attribute_by_description("Three-Point Shot")
        shot_iq = self.config.find_attribute_by_description("Shot IQ")
        self.assertEqual(self.pm.read_match_compact_attribute_values(self.player, driving_layup), [0, 0])
        self.assertEqual(self.pm.read_match_compact_attribute_values(self.player, deadeye), [0, 0])
        self.assertEqual(self.pm._read_attribute_direct(self.player, three_point), 25)
        self.assertEqual(self.pm._read_attribute_direct(self.player, shot_iq), 25)
        self.assertEqual(self.pm.get_perfect_shot_beta_state()["active"], False)

    def test_start_perfect_shot_beta_for_team_works_without_selected_player(self):
        summary = self.pm.start_perfect_shot_beta_for_team(team_id=13, team_name="Lakers")

        self.assertTrue(summary["active"])
        self.assertEqual(summary["target_team_name"], "Lakers")
        self.assertEqual(summary["representative_player"], "Luka Doncic")
        self.assertEqual(summary["team_block_index"], 0)
        self.assertEqual(self.pm.god_mode_team_calls, 0)

    def test_get_perfect_shot_beta_state_reports_active_target_team(self):
        self.pm.start_perfect_shot_beta(self.player)

        state = self.pm.get_perfect_shot_beta_state()

        self.assertTrue(state["active"])
        self.assertEqual(state["target_team_name"], "Lakers")
        self.assertEqual(state["team_block_index"], 0)
        self.assertEqual(state["representative_player"], "Luka Doncic")
        self.assertEqual(state["match_boost_players"], 1)
        self.assertEqual(state["match_boost_entries"], 2)
        self.assertFalse(state["ai_team_delta_written"])
        self.assertFalse(state["human_team_delta_written"])
        self.assertFalse(state["coverage_delta_written"])
        self.assertFalse(state["impact_delta_written"])
        self.assertEqual(state["legacy_state_writes"], 0)
        self.assertEqual(state["legacy_manager_base"], hex(self.manager_base))
        self.assertEqual(state["legacy_entries"][0]["base"], hex(self.legacy_entry))

    def test_refresh_perfect_shot_beta_auto_stops_when_match_context_disappears(self):
        self.pm.start_perfect_shot_beta(self.player)
        self.pm.fake_match_entries = []

        summary = self.pm.refresh_perfect_shot_beta()

        self.assertFalse(summary["active"])
        self.assertTrue(summary["auto_stopped"])
        self.assertTrue(summary["restore_skipped"])
        self.assertIn("No active in-match copies", summary["reason"])
        self.assertFalse(self.pm.get_perfect_shot_beta_state()["active"])


if __name__ == "__main__":
    unittest.main()
