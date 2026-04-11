import unittest
from pathlib import Path

from nba2k26_trainer.core.offsets import initialize_offsets
from nba2k26_trainer.models.player import (
    PERFECT_SHOT_ENTRY_COUNT_OFFSET,
    PERFECT_SHOT_ENABLE_OFFSET,
    PERFECT_SHOT_ENTRY_ARRAY_OFFSET,
    PERFECT_SHOT_LOCK_TIMER_ALT_OFFSET,
    PERFECT_SHOT_LOCK_TIMER_OFFSET,
    PERFECT_SHOT_MANAGER_SLOT_OFFSET,
    SHOT_RUNTIME_AI_HUMAN_DELTA_OFFSET,
    SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE,
    SHOT_RUNTIME_CONTAINER_OFFSET,
    SHOT_RUNTIME_ENTRY_BASE_OFFSET,
    SHOT_RUNTIME_ENTRY_COUNT_OFFSET,
    SHOT_RUNTIME_GLOBAL_PTR_SLOT,
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


class PerfectShotTestPlayerManager(PlayerManager):
    def __init__(self, mem, config, player):
        super().__init__(mem, config)
        self.players = [player]
        self._player = player

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

    def apply_god_mode_to_team(self, team_id: int, team_name=None):
        return {
            "boosted_players": 5,
            "boosted_attributes": 725,
        }


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
        self.mem.write_bytes_at(
            self.runtime_entry + SHOT_RUNTIME_AI_HUMAN_DELTA_OFFSET,
            original_ai_delta,
        )
        self.original_ai_delta = original_ai_delta

        self.mem.write_uint64(self.mem.base_address + PERFECT_SHOT_MANAGER_SLOT_OFFSET, self.manager_base)
        self.mem.write_uint32(self.manager_base + PERFECT_SHOT_ENTRY_COUNT_OFFSET, 1)
        self.mem.write_uint64(self.manager_base + PERFECT_SHOT_ENTRY_ARRAY_OFFSET, self.legacy_entry)
        self.mem.write_uint8(self.legacy_entry + PERFECT_SHOT_ENABLE_OFFSET, 1)
        self.mem.write_uint32(self.legacy_entry + PERFECT_SHOT_LOCK_TIMER_OFFSET, 123)
        self.mem.write_uint32(self.legacy_entry + PERFECT_SHOT_LOCK_TIMER_ALT_OFFSET, 456)

    def test_start_perfect_shot_beta_zeroes_ai_delta_and_clears_legacy_lock(self):
        summary = self.pm.start_perfect_shot_beta(self.player)

        self.assertTrue(summary["active"])
        self.assertEqual(summary["target_team_name"], "Lakers")
        self.assertEqual(summary["team_block_index"], 0)
        self.assertTrue(summary["ai_delta_written"])
        self.assertEqual(summary["boosted_players"], 5)
        self.assertEqual(summary["boosted_attributes"], 725)
        self.assertEqual(
            self.mem.read_bytes(
                self.runtime_entry + SHOT_RUNTIME_AI_HUMAN_DELTA_OFFSET,
                SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE,
            ),
            bytes(SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE),
        )
        self.assertEqual(self.mem.read_uint8(self.legacy_entry + PERFECT_SHOT_ENABLE_OFFSET), 0)
        self.assertEqual(self.mem.read_uint32(self.legacy_entry + PERFECT_SHOT_LOCK_TIMER_OFFSET), 0)
        self.assertEqual(self.mem.read_uint32(self.legacy_entry + PERFECT_SHOT_LOCK_TIMER_ALT_OFFSET), 0)

    def test_refresh_perfect_shot_beta_reapplies_zero_buffer(self):
        self.pm.start_perfect_shot_beta(self.player)
        self.mem.write_bytes_at(
            self.runtime_entry + SHOT_RUNTIME_AI_HUMAN_DELTA_OFFSET,
            bytes([9] * SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE),
        )

        summary = self.pm.refresh_perfect_shot_beta()

        self.assertTrue(summary["active"])
        self.assertTrue(summary["ai_delta_written"])
        self.assertEqual(
            self.mem.read_bytes(
                self.runtime_entry + SHOT_RUNTIME_AI_HUMAN_DELTA_OFFSET,
                SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE,
            ),
            bytes(SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE),
        )

    def test_stop_perfect_shot_beta_restores_original_ai_delta(self):
        self.pm.start_perfect_shot_beta(self.player)

        summary = self.pm.stop_perfect_shot_beta()

        self.assertFalse(summary["active"])
        self.assertTrue(summary["restored"])
        self.assertEqual(summary["target_team_name"], "Lakers")
        self.assertEqual(
            self.mem.read_bytes(
                self.runtime_entry + SHOT_RUNTIME_AI_HUMAN_DELTA_OFFSET,
                SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE,
            ),
            self.original_ai_delta,
        )
        self.assertEqual(self.pm.get_perfect_shot_beta_state()["active"], False)

    def test_get_perfect_shot_beta_state_reports_active_target_team(self):
        self.pm.start_perfect_shot_beta(self.player)

        state = self.pm.get_perfect_shot_beta_state()

        self.assertTrue(state["active"])
        self.assertEqual(state["target_team_name"], "Lakers")
        self.assertEqual(state["team_block_index"], 0)
        self.assertEqual(state["legacy_manager_base"], hex(self.manager_base))
        self.assertEqual(state["legacy_entries"][0]["base"], hex(self.legacy_entry))


if __name__ == "__main__":
    unittest.main()
