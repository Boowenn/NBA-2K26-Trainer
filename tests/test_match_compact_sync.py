import struct
import unittest
from pathlib import Path
from unittest.mock import patch

from nba2k26_trainer.core.offsets import AttributeDef, initialize_offsets
from nba2k26_trainer.models.player import (
    MATCH_COMPACT_HANDLE_OFFSET,
    Player,
    PlayerManager,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "config" / "offsets_2k26.json"


class FakeMemory:
    base_address = 0x140000000
    handle = 1

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

    def read_uint16(self, address: int):
        return int.from_bytes(self.read_bytes(address, 2), byteorder="little")

    def write_uint16(self, address: int, value: int) -> bool:
        self.write_bytes_at(address, int(value).to_bytes(2, byteorder="little"))
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

    def read_int8(self, address: int):
        return struct.unpack("<b", self.read_bytes(address, 1))[0]

    def write_int8(self, address: int, value: int) -> bool:
        self.write_bytes_at(address, struct.pack("<b", value))
        return True

    def read_int16(self, address: int):
        return struct.unpack("<h", self.read_bytes(address, 2))[0]

    def write_int16(self, address: int, value: int) -> bool:
        self.write_bytes_at(address, struct.pack("<h", value))
        return True

    def read_int32(self, address: int):
        return struct.unpack("<i", self.read_bytes(address, 4))[0]

    def write_int32(self, address: int, value: int) -> bool:
        self.write_bytes_at(address, struct.pack("<i", value))
        return True

    def read_float(self, address: int):
        return struct.unpack("<f", self.read_bytes(address, 4))[0]

    def write_float(self, address: int, value: float) -> bool:
        self.write_bytes_at(address, struct.pack("<f", value))
        return True

    def read_bitfield(self, address: int, bit_start: int, bit_length: int):
        byte_offset = bit_start // 8
        total_bits = bit_start % 8 + bit_length
        total_bytes = (total_bits + 7) // 8
        data = self.read_bytes(address + byte_offset, total_bytes)
        raw = int.from_bytes(data, byteorder="little")
        shift = bit_start % 8
        mask = (1 << bit_length) - 1
        return (raw >> shift) & mask

    def write_bitfield(self, address: int, bit_start: int, bit_length: int, value: int) -> bool:
        byte_offset = bit_start // 8
        total_bits = bit_start % 8 + bit_length
        total_bytes = (total_bits + 7) // 8
        current = self.read_bytes(address + byte_offset, total_bytes)
        raw = int.from_bytes(current, byteorder="little")
        shift = bit_start % 8
        mask = ((1 << bit_length) - 1) << shift
        raw = (raw & ~mask) | ((value << shift) & mask)
        self.write_bytes_at(address + byte_offset, raw.to_bytes(total_bytes, byteorder="little"))
        return True


class MatchCompactSyncTests(unittest.TestCase):
    def setUp(self):
        self.mem = FakeMemory()
        self.config = initialize_offsets(str(CONFIG_PATH))
        self.pm = PlayerManager(self.mem, self.config)
        self.player = Player(
            index=0,
            record_address=0x500000,
            first_name="Luka",
            last_name="Doncic",
            team_id=13,
            team_name="Lakers",
        )
        self.entry_a = 0x700000
        self.entry_b = 0x710000
        self.pm._get_match_compact_entry_bases = lambda _player: [self.entry_a, self.entry_b]

    def test_match_compact_offset_maps_known_live_blocks(self):
        self.assertEqual(self.pm._map_match_compact_offset(0x3E1), 0x189)
        self.assertEqual(self.pm._map_match_compact_offset(0x47C), 0x224)
        self.assertIsNone(self.pm._map_match_compact_offset(0x120))

    def test_write_attribute_direct_syncs_uint32_into_match_compact_entries(self):
        attr = AttributeDef(
            name="Mirror UInt32",
            offset=0x328,
            type="uint32",
            min_val=0,
            max_val=999999999,
            description="Mirror UInt32",
        )

        self.mem.write_uint32(self.player.record_address + attr.offset, 70)
        self.mem.write_uint32(self.entry_a + 0xD0, 70)
        self.mem.write_uint32(self.entry_b + 0xD0, 70)

        self.assertTrue(self.pm._write_attribute_direct(self.player, attr, 99))
        self.assertEqual(self.mem.read_uint32(self.player.record_address + attr.offset), 99)
        self.assertEqual(self.mem.read_uint32(self.entry_a + 0xD0), 99)
        self.assertEqual(self.mem.read_uint32(self.entry_b + 0xD0), 99)

    def test_write_attribute_direct_syncs_bitfields_into_match_compact_entries(self):
        attr = AttributeDef(
            name="Mirror Badge",
            offset=0x47C,
            type="bitfield",
            bit_start=0,
            bit_length=3,
            min_val=0,
            max_val=4,
            description="Mirror Badge",
        )

        self.assertTrue(self.pm._write_attribute_direct(self.player, attr, 4))
        self.assertEqual(self.mem.read_bitfield(self.player.record_address + attr.offset, 0, 3), 4)
        self.assertEqual(self.mem.read_bitfield(self.entry_a + 0x224, 0, 3), 4)
        self.assertEqual(self.mem.read_bitfield(self.entry_b + 0x224, 0, 3), 4)

    def test_read_match_compact_attribute_values_reads_mirrored_values(self):
        attr = self.config.find_attribute_by_description("Deadeye")
        self.assertIsNotNone(attr)
        assert attr is not None

        mapped_offset = self.pm._map_match_compact_offset(attr.offset)
        self.assertIsNotNone(mapped_offset)
        assert mapped_offset is not None

        self.mem.write_bitfield(self.entry_a + mapped_offset, attr.bit_start, attr.bit_length, 4)
        self.mem.write_bitfield(self.entry_b + mapped_offset, attr.bit_start, attr.bit_length, 3)

        self.assertEqual(self.pm.read_match_compact_attribute_values(self.player, attr), [4, 3])

    def test_summarize_live_gameplay_state_reports_current_and_match_copy_values(self):
        driving_layup = self.config.find_attribute_by_description("Driving Layup")
        deadeye = self.config.find_attribute_by_description("Deadeye")
        spot_up_drive = self.config.find_attribute_by_description("Spot Up Drive")
        contest_shot = self.config.find_attribute_by_description("Contest Shot")

        for attr in (driving_layup, deadeye, spot_up_drive, contest_shot):
            self.assertIsNotNone(attr)

        assert driving_layup is not None
        assert deadeye is not None
        assert spot_up_drive is not None
        assert contest_shot is not None

        self.mem.write_bitfield(self.player.record_address + driving_layup.offset, 1, 7, 99)
        self.mem.write_bitfield(
            self.player.record_address + deadeye.offset, deadeye.bit_start, deadeye.bit_length, 4
        )
        self.mem.write_bitfield(
            self.player.record_address + spot_up_drive.offset,
            spot_up_drive.bit_start,
            spot_up_drive.bit_length,
            90,
        )
        self.mem.write_bitfield(
            self.player.record_address + contest_shot.offset,
            contest_shot.bit_start,
            contest_shot.bit_length,
            99,
        )

        layup_offset = self.pm._map_match_compact_offset(driving_layup.offset)
        deadeye_offset = self.pm._map_match_compact_offset(deadeye.offset)
        spot_up_drive_offset = self.pm._map_match_compact_offset(spot_up_drive.offset)
        contest_shot_offset = self.pm._map_match_compact_offset(contest_shot.offset)

        self.assertIsNotNone(layup_offset)
        self.assertIsNotNone(deadeye_offset)
        self.assertIsNotNone(spot_up_drive_offset)
        self.assertIsNotNone(contest_shot_offset)

        assert layup_offset is not None
        assert deadeye_offset is not None
        assert spot_up_drive_offset is not None
        assert contest_shot_offset is not None

        for entry in (self.entry_a, self.entry_b):
            self.mem.write_bitfield(entry + layup_offset, 1, 7, 99)
            self.mem.write_bitfield(entry + deadeye_offset, deadeye.bit_start, deadeye.bit_length, 4)
            self.mem.write_bitfield(
                entry + spot_up_drive_offset,
                spot_up_drive.bit_start,
                spot_up_drive.bit_length,
                90,
            )
            self.mem.write_bitfield(
                entry + contest_shot_offset,
                contest_shot.bit_start,
                contest_shot.bit_length,
                99,
            )

        summary = self.pm.summarize_live_gameplay_state(self.player)

        self.assertEqual(summary["match_compact_entries"], 2)
        self.assertEqual(summary["match_compact_bases"], [hex(self.entry_a), hex(self.entry_b)])
        self.assertEqual(summary["attributes"]["Driving Layup"]["current"], 99)
        self.assertEqual(summary["attributes"]["Driving Layup"]["match_copies"], [99, 99])
        self.assertEqual(summary["attributes"]["Deadeye"]["current"], 4)
        self.assertEqual(summary["attributes"]["Deadeye"]["match_copies"], [4, 4])
        self.assertEqual(summary["attributes"]["Spot Up Drive"]["current"], 90)
        self.assertEqual(summary["attributes"]["Spot Up Drive"]["match_copies"], [90, 90])
        self.assertEqual(summary["attributes"]["Contest Shot"]["current"], 99)
        self.assertEqual(summary["attributes"]["Contest Shot"]["match_copies"], [99, 99])

    def test_match_compact_validation_accepts_current_handle_layout(self):
        handle = bytes.fromhex("E0A1083600000000")
        self.mem.write_bytes_at(self.player.record_address + 0x2B8, handle)
        self.mem.write_bytes_at(self.entry_a + MATCH_COMPACT_HANDLE_OFFSET, handle)

        self.assertTrue(self.pm._is_valid_match_compact_entry(self.player, self.entry_a))

    def test_discover_match_compact_regions_keeps_team_region_and_player_specific_region(self):
        team_player_b = Player(
            index=1,
            record_address=0x500498,
            first_name="Austin",
            last_name="Reaves",
            team_id=13,
            team_name="Lakers",
        )
        team_player_c = Player(
            index=2,
            record_address=0x500930,
            first_name="LeBron",
            last_name="James",
            team_id=13,
            team_name="Lakers",
        )
        self.pm.players = [self.player, team_player_b, team_player_c]
        handle_a = bytes.fromhex("E0A1083600000000")
        handle_b = bytes.fromhex("20B6307AF78D0000")
        handle_c = bytes.fromhex("60FC4459F3DB0000")
        self.mem.write_bytes_at(self.player.record_address + 0x2B8, handle_a)
        self.mem.write_bytes_at(team_player_b.record_address + 0x2B8, handle_b)
        self.mem.write_bytes_at(team_player_c.record_address + 0x2B8, handle_c)

        region_team = 0x900000
        region_player = 0x910000
        region_noise = 0x920000
        self.mem.write_bytes_at(region_team + 0x60, handle_a)
        self.mem.write_bytes_at(region_team + 0x160, handle_b)
        self.mem.write_bytes_at(region_team + 0x260, handle_c)
        self.mem.write_bytes_at(region_player + 0x60, handle_a)
        self.mem.write_bytes_at(region_noise + 0x60, b"\xAA" * 8)

        with patch(
            "nba2k26_trainer.models.player.enum_candidate_regions",
            return_value=[
                (region_team, 0x400, 0x04, 0x20000),
                (region_player, 0x400, 0x04, 0x20000),
                (region_noise, 0x400, 0x04, 0x20000),
            ],
        ):
            regions = self.pm._discover_match_compact_regions(self.player)

        self.assertEqual(regions[0][0], region_team)
        self.assertEqual(regions[1][0], region_player)


if __name__ == "__main__":
    unittest.main()
