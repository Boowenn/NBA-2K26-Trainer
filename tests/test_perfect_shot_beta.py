import struct
import unittest
from pathlib import Path

from nba2k26_trainer.core.offsets import initialize_offsets
from nba2k26_trainer.models.player import (
    PERFECT_SHOT_ENTRY_ARRAY_OFFSET,
    PERFECT_SHOT_ENTRY_COUNT_OFFSET,
    PERFECT_SHOT_ENTRY_STRIDE,
    PERFECT_SHOT_ENABLE_OFFSET,
    PERFECT_SHOT_FORCED_ENABLE_VALUE,
    PERFECT_SHOT_FORCED_LOCK_VALUE,
    PERFECT_SHOT_LOCK_TIMER_ALT_OFFSET,
    PERFECT_SHOT_LOCK_TIMER_OFFSET,
    PERFECT_SHOT_MANAGER_SLOT_OFFSET,
    PlayerManager,
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


class PerfectShotBetaTests(unittest.TestCase):
    def setUp(self):
        self.mem = FakeMemory()
        self.config = initialize_offsets(str(CONFIG_PATH))
        self.pm = PlayerManager(self.mem, self.config)
        self.manager_base = 0x500000
        self.entries_base = 0x600000

        self.mem.write_uint64(
            self.mem.base_address + PERFECT_SHOT_MANAGER_SLOT_OFFSET,
            self.manager_base,
        )
        self.mem.write_uint32(
            self.manager_base + PERFECT_SHOT_ENTRY_COUNT_OFFSET,
            2,
        )
        self.mem.write_uint64(
            self.manager_base + PERFECT_SHOT_ENTRY_ARRAY_OFFSET,
            self.entries_base,
        )

    def test_get_perfect_shot_beta_entry_bases_reads_live_entries(self):
        bases = self.pm._get_perfect_shot_beta_entry_bases()
        self.assertEqual(
            bases,
            [
                self.entries_base,
                self.entries_base + PERFECT_SHOT_ENTRY_STRIDE,
            ],
        )

    def test_enforce_perfect_shot_beta_writes_forced_values(self):
        summary = self.pm.enforce_perfect_shot_beta()

        self.assertEqual(summary["patched_entries"], 2)
        self.assertEqual(summary["entry_count"], 2)

        for entry_base in (
            self.entries_base,
            self.entries_base + PERFECT_SHOT_ENTRY_STRIDE,
        ):
            self.assertEqual(
                self.mem.read_uint8(entry_base + PERFECT_SHOT_ENABLE_OFFSET),
                PERFECT_SHOT_FORCED_ENABLE_VALUE,
            )
            self.assertEqual(
                self.mem.read_uint32(entry_base + PERFECT_SHOT_LOCK_TIMER_OFFSET),
                PERFECT_SHOT_FORCED_LOCK_VALUE,
            )
            self.assertEqual(
                self.mem.read_uint32(entry_base + PERFECT_SHOT_LOCK_TIMER_ALT_OFFSET),
                PERFECT_SHOT_FORCED_LOCK_VALUE,
            )

    def test_get_perfect_shot_beta_state_reports_entry_values(self):
        self.mem.write_uint8(self.entries_base + PERFECT_SHOT_ENABLE_OFFSET, 1)
        self.mem.write_uint32(self.entries_base + PERFECT_SHOT_LOCK_TIMER_OFFSET, 123)
        self.mem.write_uint32(self.entries_base + PERFECT_SHOT_LOCK_TIMER_ALT_OFFSET, 456)

        state = self.pm.get_perfect_shot_beta_state()

        self.assertEqual(state["manager_base"], hex(self.manager_base))
        self.assertEqual(state["entry_count"], 2)
        self.assertEqual(state["entries"][0]["base"], hex(self.entries_base))
        self.assertEqual(state["entries"][0]["enable_byte"], 1)
        self.assertEqual(state["entries"][0]["lock_timer"], 123)
        self.assertEqual(state["entries"][0]["lock_timer_alt"], 456)


if __name__ == "__main__":
    unittest.main()
