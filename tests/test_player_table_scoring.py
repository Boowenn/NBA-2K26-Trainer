import unittest
from pathlib import Path
from unittest.mock import patch

from nba2k26_trainer.core.offsets import initialize_offsets
from nba2k26_trainer.models.player import Player, PlayerManager, _is_valid_name


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "config" / "offsets_2k26.json"
PLAYER_TABLE_BASE = 0x500000
NOISE_TABLE_BASE = 0x700000


def _encode_wstring(text: str) -> bytes:
    return text.encode("utf-16-le") + b"\x00\x00"


def _alpha_name(index: int, prefix: str) -> str:
    letters = []
    value = index
    for _ in range(4):
        letters.append(chr(ord("A") + (value % 26)))
        value //= 26
    return prefix + "".join(letters)


class FakeMemory:
    def __init__(self):
        self.base_address = 0x140000000
        self._bytes = {}

    def write_bytes_at(self, address: int, data: bytes) -> None:
        for index, byte in enumerate(data):
            self._bytes[address + index] = byte

    def read_bytes(self, address: int, size: int):
        if not any((address + index) in self._bytes for index in range(size)):
            return None
        return bytes(self._bytes.get(address + index, 0) for index in range(size))

    def read_uint8(self, address: int):
        data = self.read_bytes(address, 1)
        return data[0] if data else None

    def read_uint32(self, address: int):
        data = self.read_bytes(address, 4)
        return int.from_bytes(data, byteorder="little") if data and len(data) == 4 else None

    def read_uint64(self, address: int):
        data = self.read_bytes(address, 8)
        return int.from_bytes(data, byteorder="little") if data and len(data) == 8 else None

    def read_wstring(self, address: int, max_len: int = 64):
        data = self.read_bytes(address, max_len * 2)
        if not data:
            return None
        for index in range(0, len(data) - 1, 2):
            if data[index] == 0 and data[index + 1] == 0:
                data = data[:index]
                break
        return data.decode("utf-16-le", errors="ignore")

    def read_bitfield(self, address: int, bit_start: int, bit_length: int):
        byte_offset = bit_start // 8
        total_bits = bit_start % 8 + bit_length
        total_bytes = (total_bits + 7) // 8
        data = self.read_bytes(address + byte_offset, total_bytes)
        if not data:
            return None
        value = int.from_bytes(data, byteorder="little")
        shift = bit_start % 8
        mask = (1 << bit_length) - 1
        return (value >> shift) & mask

    def write_bitfield(self, address: int, bit_start: int, bit_length: int, value: int) -> None:
        byte_offset = bit_start // 8
        total_bits = bit_start % 8 + bit_length
        total_bytes = (total_bits + 7) // 8
        current = self.read_bytes(address + byte_offset, total_bytes) or b"\x00" * total_bytes
        current_value = int.from_bytes(current, byteorder="little")
        shift = bit_start % 8
        mask = ((1 << bit_length) - 1) << shift
        new_value = (current_value & ~mask) | ((value << shift) & mask)
        self.write_bytes_at(address + byte_offset, new_value.to_bytes(total_bytes, byteorder="little"))
        return True


class PlayerTableScoringTests(unittest.TestCase):
    def setUp(self):
        self.mem = FakeMemory()
        self.config = initialize_offsets(str(CONFIG_PATH))
        self.config.team_table.base_pointer = 0
        self.pm = PlayerManager(self.mem, self.config)
        self.pm._resolve_team_table_base = lambda progress_callback=None: None
        self.pm._count_module_pointer_refs = lambda _table_base: 0

    def _write_record(
        self,
        table_base: int,
        index: int,
        *,
        first_name: str,
        last_name: str,
        birth_year: int | None,
        overall: int | None = None,
        live_overall_418: int | None = None,
        live_overall_1028: int | None = None,
        team_ptr: int = 0,
        team_ptr_offset: int = 96,
    ) -> None:
        pt = self.config.player_table
        record_address = table_base + index * pt.stride
        self.mem.write_bytes_at(record_address + pt.last_name_offset, _encode_wstring(last_name))
        self.mem.write_bytes_at(record_address + pt.first_name_offset, _encode_wstring(first_name))
        self.mem.write_bytes_at(record_address + team_ptr_offset, team_ptr.to_bytes(8, byteorder="little"))
        if birth_year is not None:
            self.mem.write_bytes_at(record_address + 266, birth_year.to_bytes(2, byteorder="little"))
        if overall is not None:
            self.mem.write_bytes_at(record_address + 1047, bytes([overall]))
        if live_overall_418 is not None:
            self.mem.write_bitfield(record_address + 418, 1, 7, live_overall_418)
        if live_overall_1028 is not None:
            self.mem.write_bitfield(record_address + 1028, 1, 7, live_overall_1028)

    def _write_team_record(self, address: int, name: str) -> None:
        self.mem.write_bytes_at(address + self.config.team_table.team_name_offset, _encode_wstring(name))

    def test_table_is_promising_when_ovr_reads_fail_but_names_and_birth_years_match(self):
        players = [
            ("LeBron", "James", 1984),
            ("Stephen", "Curry", 1988),
            ("Nikola", "Jokic", 1995),
            ("Jayson", "Tatum", 1998),
        ]
        for index, (first_name, last_name, birth_year) in enumerate(players):
            self._write_record(
                PLAYER_TABLE_BASE,
                index,
                first_name=first_name,
                last_name=last_name,
                birth_year=birth_year,
                overall=None,
            )

        metrics = self.pm._score_player_table_base(PLAYER_TABLE_BASE)

        self.assertEqual(metrics.valid_names, 4)
        self.assertEqual(metrics.valid_birth_year, 4)
        self.assertEqual(metrics.valid_overall, 0)
        self.assertEqual(metrics.valid_team_refs, 4)
        self.assertTrue(self.pm._is_promising_player_table(metrics))

    def test_pick_best_player_table_prefers_real_roster_over_noise(self):
        for index, (first_name, last_name, birth_year) in enumerate(
            [
                ("LeBron", "James", 1984),
                ("Stephen", "Curry", 1988),
                ("Nikola", "Jokic", 1995),
                ("Jayson", "Tatum", 1998),
            ]
        ):
            self._write_record(
                PLAYER_TABLE_BASE,
                index,
                first_name=first_name,
                last_name=last_name,
                birth_year=birth_year,
                overall=None,
            )

        for index, (first_name, last_name) in enumerate(
            [("Menu", "Entry"), ("Screen", "Prompt"), ("Random", "Label"), ("Fake", "Block")]
        ):
            self._write_record(
                NOISE_TABLE_BASE,
                index,
                first_name=first_name,
                last_name=last_name,
                birth_year=None,
                overall=None,
                team_ptr=0x1234,
            )

        best = self.pm._pick_best_player_table(
            [
                (NOISE_TABLE_BASE, "noise"),
                (PLAYER_TABLE_BASE, "real roster"),
            ]
        )

        self.assertEqual(best, PLAYER_TABLE_BASE)

    def test_pick_best_player_table_prefers_legend_roster_in_legend_mode(self):
        modern_team = 0x910000
        legend_team = 0x920000
        self._write_team_record(modern_team, "Lakers")
        self._write_team_record(legend_team, "Lakers")

        modern_players = [
            ("LeBron", "James", 1984, 96, modern_team),
            ("Stephen", "Curry", 1988, 96, modern_team),
            ("Kevin", "Durant", 1988, 96, modern_team),
            ("Nikola", "Jokic", 1995, 96, modern_team),
        ]
        for index in range(120):
            first_name, last_name, birth_year, team_ptr_offset, team_ptr = modern_players[index % len(modern_players)]
            self._write_record(
                PLAYER_TABLE_BASE,
                index,
                first_name=first_name,
                last_name=last_name,
                birth_year=birth_year,
                overall=80,
                team_ptr_offset=team_ptr_offset,
                team_ptr=team_ptr,
            )

        legend_players = [
            ("Magic", "Johnson", 1959, 184, legend_team),
            ("Michael", "Jordan", 1963, 184, legend_team),
            ("Scottie", "Pippen", 1965, 184, legend_team),
            ("James", "Worthy", 1961, 184, legend_team),
        ]
        for index in range(120):
            first_name, last_name, birth_year, team_ptr_offset, team_ptr = legend_players[index % len(legend_players)]
            self._write_record(
                NOISE_TABLE_BASE,
                index,
                first_name=first_name,
                last_name=last_name,
                birth_year=birth_year,
                overall=80,
                team_ptr_offset=team_ptr_offset,
                team_ptr=team_ptr,
            )

        self.pm.set_roster_mode("legend")
        best = self.pm._pick_best_player_table(
            [
                (PLAYER_TABLE_BASE, "module_base + modern"),
                (NOISE_TABLE_BASE, "memory scan legend"),
            ]
        )

        self.assertEqual(best, NOISE_TABLE_BASE)

    def test_pick_best_player_table_prefers_active_save_roster_in_auto_mode(self):
        active_team = 0x930000
        generic_team = 0x940000
        self._write_team_record(active_team, "Lakers")
        self._write_team_record(generic_team, "Lakers")

        generic_players = [
            ("LeBron", "James", 1984, generic_team),
            ("Stephen", "Curry", 1988, generic_team),
            ("Kevin", "Durant", 1988, generic_team),
            ("Nikola", "Jokic", 1995, generic_team),
        ]
        for index in range(120):
            first_name, last_name, birth_year, team_ptr = generic_players[index % len(generic_players)]
            self._write_record(
                PLAYER_TABLE_BASE,
                index,
                first_name=first_name,
                last_name=last_name,
                birth_year=birth_year,
                overall=80,
                team_ptr=team_ptr,
            )

        active_players = [
            ("Bronny", "James Jr.", 2004, active_team),
            ("Dalton", "Knecht", 2001, active_team),
            ("Julius", "Randle", 1994, active_team),
            ("Brandon", "Ingram", 1997, active_team),
        ]
        for index in range(120):
            first_name, last_name, birth_year, team_ptr = active_players[index % len(active_players)]
            self._write_record(
                NOISE_TABLE_BASE,
                index,
                first_name=first_name,
                last_name=last_name,
                birth_year=birth_year,
                overall=75,
                team_ptr=team_ptr,
                team_ptr_offset=184,
            )

        self.pm._count_module_pointer_refs = lambda table_base: {
            PLAYER_TABLE_BASE: 11,
            NOISE_TABLE_BASE: 70,
        }.get(table_base, 0)

        self.pm.set_roster_mode("auto")
        best = self.pm._pick_best_player_table(
            [
                (PLAYER_TABLE_BASE, "module_base + generic current"),
                (NOISE_TABLE_BASE, "memory scan active save"),
            ]
        )

        self.assertEqual(best, NOISE_TABLE_BASE)

    def test_pick_best_player_table_prefers_full_roster_over_partial_snapshot(self):
        full_team = 0x970000
        partial_team = 0x971000
        self._write_team_record(full_team, "Lakers")
        self._write_team_record(partial_team, "2K Sports")

        full_players = [
            ("Luka", "Doncic", 1999, 98, full_team),
            ("Austin", "Reaves", 1998, 87, full_team),
            ("LeBron", "James", 1984, 94, full_team),
            ("Rui", "Hachimura", 1998, 79, full_team),
        ]
        for index in range(600):
            first_name, last_name, birth_year, overall, team_ptr = full_players[index % len(full_players)]
            self._write_record(
                PLAYER_TABLE_BASE,
                index,
                first_name=first_name,
                last_name=last_name,
                birth_year=birth_year,
                overall=overall,
                team_ptr=team_ptr,
            )

        partial_players = [
            ("Alfredo", "Chavez", 1991, 71, partial_team),
            ("Jorge", "Fernandez", 1990, 70, partial_team),
            ("Pablo", "Garcia", 1992, 64, partial_team),
            ("Anthony", "Edwards", 2001, 95, full_team),
        ]
        for index in range(275):
            first_name, last_name, birth_year, overall, team_ptr = partial_players[index % len(partial_players)]
            self._write_record(
                NOISE_TABLE_BASE,
                index,
                first_name=first_name,
                last_name=last_name,
                birth_year=birth_year,
                overall=overall,
                team_ptr=team_ptr,
                team_ptr_offset=208,
            )

        self.pm.set_roster_mode("auto")
        best = self.pm._pick_best_player_table(
            [
                (NOISE_TABLE_BASE, "module_base + partial"),
                (PLAYER_TABLE_BASE, "module_base + full"),
            ]
        )

        self.assertEqual(best, PLAYER_TABLE_BASE)

    def test_resolve_live_team_ptr_offset_prefers_current_team_assignments(self):
        current_teams = [
            (0x950000, "Lakers"),
            (0x951000, "Warriors"),
            (0x952000, "Celtics"),
            (0x953000, "Bulls"),
        ]
        base_teams = [
            (0x960000, "Lakers"),
            (0x961000, "Warriors"),
        ]

        for address, name in current_teams + base_teams:
            self._write_team_record(address, name)

        current_players = [
            ("Luka", "Doncic", 1999, current_teams[0][0]),
            ("Austin", "Reaves", 1998, current_teams[0][0]),
            ("Stephen", "Curry", 1988, current_teams[1][0]),
            ("Jayson", "Tatum", 1998, current_teams[2][0]),
            ("Michael", "Jordan", 1963, current_teams[3][0]),
            ("Scottie", "Pippen", 1965, current_teams[3][0]),
        ]
        base_players = [
            ("Luka", "Doncic", 1999, base_teams[0][0]),
            ("Austin", "Reaves", 1998, base_teams[0][0]),
            ("Stephen", "Curry", 1988, base_teams[1][0]),
            ("LeBron", "James", 1984, base_teams[1][0]),
            ("Kevin", "Durant", 1988, base_teams[1][0]),
            ("Nikola", "Jokic", 1995, base_teams[1][0]),
        ]

        for index in range(24):
            first_name, last_name, birth_year, current_team_ptr = current_players[index % len(current_players)]
            _, _, _, base_team_ptr = base_players[index % len(base_players)]
            self._write_record(
                PLAYER_TABLE_BASE,
                index,
                first_name=first_name,
                last_name=last_name,
                birth_year=birth_year,
                overall=80,
                team_ptr=current_team_ptr,
                team_ptr_offset=96,
            )
            self._write_record(
                PLAYER_TABLE_BASE,
                index,
                first_name=first_name,
                last_name=last_name,
                birth_year=birth_year,
                overall=80,
                team_ptr=base_team_ptr,
                team_ptr_offset=184,
            )

        self.pm._live_team_ptr_offset_cache.clear()
        best_offset, _ = self.pm._resolve_live_team_ptr_offset(PLAYER_TABLE_BASE, None)

        self.assertEqual(best_offset, 96)

    def test_resolve_live_overall_attr_prefers_current_save_display_field(self):
        current_players = [
            ("Luka", "Doncic", 1999, 99, 99),
            ("Austin", "Reaves", 1998, 58, 80),
            ("Herbert", "Jones", 1998, 40, 80),
            ("Daniel", "Gafford", 1998, 45, 79),
            ("Nick", "Smith Jr.", 2004, 62, 81),
            ("Bronny", "James Jr.", 2004, 45, 77),
        ]

        for index in range(24):
            first_name, last_name, birth_year, raw_overall, live_overall = current_players[index % len(current_players)]
            self._write_record(
                PLAYER_TABLE_BASE,
                index,
                first_name=first_name,
                last_name=last_name,
                birth_year=birth_year,
                overall=raw_overall,
                live_overall_418=live_overall,
                live_overall_1028=82,
            )

        live_attr = self.pm._resolve_live_overall_attr(PLAYER_TABLE_BASE)
        self.assertIsNotNone(live_attr)
        self.assertEqual(live_attr.offset, 418)
        self.assertEqual(live_attr.type, "bitfield")

        self.pm.set_roster_mode("current")
        self.pm._table_base = PLAYER_TABLE_BASE
        with patch("nba2k26_trainer.models.player.MIN_ACCEPTABLE_PLAYER_COUNT", 24):
            players = self.pm.scan_players()
        players_by_name = {player.full_name: player for player in players}
        overall_attr = self.config.find_attribute_by_description("Overall Rating")

        self.assertEqual(players_by_name["Austin Reaves"].overall, 80)
        self.assertEqual(players_by_name["Herbert Jones"].overall, 80)
        self.assertEqual(players_by_name["Daniel Gafford"].overall, 79)
        self.assertEqual(self.pm.read_attribute(players_by_name["Austin Reaves"], overall_attr), 80)

    def test_begin_refresh_keeps_fast_caches_until_force_rescan(self):
        overall_attr = self.config.find_attribute_by_description("Overall Rating")
        self.pm._module_ref_count_cache[PLAYER_TABLE_BASE] = 42
        self.pm._live_overall_attr_cache[PLAYER_TABLE_BASE] = (overall_attr, 1234)

        self.pm.begin_refresh(force_rescan=False)
        self.assertEqual(self.pm._module_ref_count_cache[PLAYER_TABLE_BASE], 42)
        self.assertIn(PLAYER_TABLE_BASE, self.pm._live_overall_attr_cache)

        self.pm.begin_refresh(force_rescan=True)
        self.assertNotIn(PLAYER_TABLE_BASE, self.pm._module_ref_count_cache)
        self.assertNotIn(PLAYER_TABLE_BASE, self.pm._live_overall_attr_cache)

    def test_live_roster_signature_changes_when_sampled_roster_data_changes(self):
        players = [
            ("Luka", "Doncic", 1999, 94),
            ("Austin", "Reaves", 1998, 85),
            ("Herbert", "Jones", 1998, 84),
            ("Daniel", "Gafford", 1998, 82),
        ]
        for index in range(120):
            first_name, last_name, birth_year, overall = players[index % len(players)]
            self._write_record(
                PLAYER_TABLE_BASE,
                index,
                first_name=first_name,
                last_name=last_name,
                birth_year=birth_year,
                overall=overall,
                team_ptr=0x950000 + index * 0x20,
            )

        self.pm._resolve_table_base = lambda progress_callback=None, use_cached=True: PLAYER_TABLE_BASE

        before = self.pm.get_live_roster_signature(force_refresh=True)
        self._write_record(
            PLAYER_TABLE_BASE,
            50,
            first_name="LeBron",
            last_name="James",
            birth_year=1984,
            overall=97,
            team_ptr=0x990000,
        )
        after = self.pm.get_live_roster_signature(force_refresh=True)

        self.assertIsNotNone(before)
        self.assertIsNotNone(after)
        self.assertNotEqual(before, after)

    def test_is_valid_name_rejects_non_latin_gibberish(self):
        self.assertTrue(_is_valid_name("Luka"))
        self.assertTrue(_is_valid_name("Nicolas Batum"))
        self.assertTrue(_is_valid_name("Nikola Jokic"))
        self.assertFalse(_is_valid_name("\u3f97\u0f61\uf921\u212b\uc4ad"))
        self.assertFalse(_is_valid_name("\u4554\u4358\u4f4f\u4452"))

    def test_pick_best_player_table_rejects_gibberish_match_entity_table(self):
        real_players = [
            ("Luka", "Doncic", 1999),
            ("Austin", "Reaves", 1998),
            ("Herbert", "Jones", 1998),
            ("Daniel", "Gafford", 1998),
        ]
        for index in range(24):
            first_name, last_name, birth_year = real_players[index % len(real_players)]
            self._write_record(
                PLAYER_TABLE_BASE,
                index,
                first_name=first_name,
                last_name=last_name,
                birth_year=birth_year,
                overall=80,
            )

        gibberish_names = [
            ("\u3f97\u0f61\uf921\u212b", "\uc4ad\u17e4\u8db7\uc18a", 1999),
            ("\u4554\u4358\u4f4f\u4452", "\u5400\u5845\u4f43\u524f", 1998),
            ("\u6d7a\ud120\u40c2", "\ua0c5\u6d7a\ud120", 1997),
            ("\ue0ee\uf50e\u0ec0", "\u30ec\u6203\ua1c8", 1996),
        ]
        for index in range(24):
            first_name, last_name, birth_year = gibberish_names[index % len(gibberish_names)]
            self._write_record(
                NOISE_TABLE_BASE,
                index,
                first_name=first_name,
                last_name=last_name,
                birth_year=birth_year,
                overall=80,
            )

        self.pm._count_module_pointer_refs = lambda table_base: {
            PLAYER_TABLE_BASE: 11,
            NOISE_TABLE_BASE: 70,
        }.get(table_base, 0)

        self.pm.set_roster_mode("auto")
        best = self.pm._pick_best_player_table(
            [
                (PLAYER_TABLE_BASE, "module_base + real roster"),
                (NOISE_TABLE_BASE, "memory scan live match entities"),
            ]
        )

        self.assertEqual(best, PLAYER_TABLE_BASE)

    def test_table_without_birth_years_or_team_refs_is_not_promising(self):
        players = [
            ("Luka", "Doncic"),
            ("Austin", "Reaves"),
            ("Herbert", "Jones"),
            ("Daniel", "Gafford"),
        ]
        for index, (first_name, last_name) in enumerate(players):
            self._write_record(
                NOISE_TABLE_BASE,
                index,
                first_name=first_name,
                last_name=last_name,
                birth_year=None,
                overall=80,
                team_ptr=0x1234,
            )

        metrics = self.pm._score_player_table_base(NOISE_TABLE_BASE)

        self.assertEqual(metrics.valid_names, 4)
        self.assertEqual(metrics.valid_overall, 4)
        self.assertEqual(metrics.valid_birth_year, 0)
        self.assertEqual(metrics.valid_team_refs, 0)
        self.assertFalse(self.pm._is_promising_player_table(metrics))

    def test_auto_mode_prefers_currentish_roster_over_legend_heavy_snapshot(self):
        current_team = 0x970000
        legend_team = 0x980000
        self._write_team_record(current_team, "Lakers")
        self._write_team_record(legend_team, "Lakers")

        currentish_players = [
            ("Luka", "Doncic", 1999, current_team),
            ("Austin", "Reaves", 1998, current_team),
            ("Herbert", "Jones", 1998, current_team),
            ("Daniel", "Gafford", 1998, current_team),
            ("LeBron", "James", 1984, current_team),
            ("Stephen", "Curry", 1988, current_team),
            ("Jayson", "Tatum", 1998, current_team),
            ("Victor", "Wembanyama", 2004, current_team),
        ]
        legend_heavy_players = [
            ("Magic", "Johnson", 1959, legend_team),
            ("James", "Worthy", 1961, legend_team),
            ("Jerry", "West", 1938, legend_team),
            ("Elgin", "Baylor", 1934, legend_team),
            ("Vlade", "Divac", 1968, legend_team),
        ]

        for index in range(120):
            first_name, last_name, birth_year, team_ptr = currentish_players[index % len(currentish_players)]
            self._write_record(
                PLAYER_TABLE_BASE,
                index,
                first_name=first_name,
                last_name=last_name,
                birth_year=birth_year,
                overall=80,
                team_ptr=team_ptr,
            )

            first_name, last_name, birth_year, team_ptr = legend_heavy_players[index % len(legend_heavy_players)]
            self._write_record(
                NOISE_TABLE_BASE,
                index,
                first_name=first_name,
                last_name=last_name,
                birth_year=birth_year,
                overall=80,
                team_ptr=team_ptr,
            )

        self.pm.set_roster_mode("auto")
        best = self.pm._pick_best_player_table(
            [
                (PLAYER_TABLE_BASE, "mixed current save"),
                (NOISE_TABLE_BASE, "legend heavy snapshot"),
            ]
        )

        self.assertEqual(best, PLAYER_TABLE_BASE)

    def test_resolve_table_base_scans_past_weak_config_snapshot(self):
        self.pm.set_roster_mode("auto")

        weak_metrics = type(
            "Metrics",
            (),
            {
                "module_ref_count": 2,
                "valid_names": 24,
                "valid_birth_year": 24,
                "valid_team_refs": 24,
                "estimated_player_count": 275,
            },
        )()
        strong_metrics = type(
            "Metrics",
            (),
            {
                "module_ref_count": 10,
                "valid_names": 24,
                "valid_birth_year": 24,
                "valid_team_refs": 24,
                "estimated_player_count": 600,
            },
        )()

        self.pm._get_config_player_table_candidates = lambda: [(NOISE_TABLE_BASE, "module pointer")]
        self.pm._matches_requested_roster_mode = lambda _metrics: True

        def fake_pick(candidates, _progress_callback=None, *, include_module_refs=True):
            bases = {base for base, _source in candidates}
            if bases == {NOISE_TABLE_BASE}:
                return NOISE_TABLE_BASE
            if PLAYER_TABLE_BASE in bases:
                return PLAYER_TABLE_BASE
            return None

        def fake_score(table_base, include_module_refs=True):
            if table_base == NOISE_TABLE_BASE:
                return weak_metrics
            if table_base == PLAYER_TABLE_BASE:
                return strong_metrics
            raise AssertionError(f"unexpected table base 0x{table_base:X}")

        self.pm._pick_best_player_table = fake_pick
        self.pm._score_player_table_base = fake_score

        with patch("nba2k26_trainer.models.player.scan_for_player_table_candidates", return_value=[(PLAYER_TABLE_BASE, 50)]):
            resolved = self.pm._resolve_table_base()

        self.assertEqual(resolved, PLAYER_TABLE_BASE)
        self.assertEqual(self.pm._table_base, PLAYER_TABLE_BASE)

    def test_scan_players_retries_when_selected_table_is_duplicate_snapshot(self):
        duplicate_pattern = [
            ("George", "Mikan"),
            ("LeBron", "James"),
            ("Michael", "Jordan"),
            ("Luka", "Doncic"),
            ("LeBron", "James"),
            ("Luka", "Doncic"),
            ("Austin", "Reaves"),
            ("Rui", "Hachimura"),
        ]
        for index in range(600):
            first_name, last_name = duplicate_pattern[index % len(duplicate_pattern)]
            self._write_record(
                NOISE_TABLE_BASE,
                index,
                first_name=first_name,
                last_name=last_name,
                birth_year=1998,
                overall=80,
            )

        for index in range(600):
            self._write_record(
                PLAYER_TABLE_BASE,
                index,
                first_name=_alpha_name(index, "F"),
                last_name=_alpha_name(index, "L"),
                birth_year=1990 + (index % 10),
                overall=75 + (index % 20),
            )

        resolved_bases = iter([NOISE_TABLE_BASE, PLAYER_TABLE_BASE])
        self.pm._resolve_table_base = lambda progress_callback=None: next(resolved_bases)

        players = self.pm.scan_players()
        full_names = [player.full_name for player in players]

        self.assertEqual(self.pm._table_base, PLAYER_TABLE_BASE)
        self.assertEqual(len(players), 600)
        self.assertEqual(len(full_names), len(set(full_names)))

    def test_write_all_attributes_updates_multiple_contract_years(self):
        player = Player(
            index=0,
            record_address=PLAYER_TABLE_BASE,
            first_name="Luka",
            last_name="Doncic",
        )
        year1 = self.config.find_attribute_by_description("Year 1 Salary")
        year2 = self.config.find_attribute_by_description("Year 2 Salary")
        year3 = self.config.find_attribute_by_description("Year 3 Salary")
        year4 = self.config.find_attribute_by_description("Year 4 Salary")
        contract_years = self.config.find_attribute_by_description("Contract Years Left")

        self.mem.write_bitfield(
            player.record_address + contract_years.offset,
            contract_years.bit_start,
            contract_years.bit_length,
            1,
        )
        self.mem.write_bitfield(player.record_address + year1.offset, year1.bit_start, year1.bit_length, 45000000)
        self.mem.write_bitfield(player.record_address + year2.offset, year2.bit_start, year2.bit_length, 49000000)
        self.mem.write_bitfield(player.record_address + year3.offset, year3.bit_start, year3.bit_length, 53000000)
        self.mem.write_bitfield(player.record_address + year4.offset, year4.bit_start, year4.bit_length, 57000000)

        updates = {
            year2.name: 49111111,
            year3.name: 53222222,
            year4.name: 57333333,
        }
        results = self.pm.write_all_attributes(player, updates)

        self.assertTrue(results[year2.name])
        self.assertTrue(results[year3.name])
        self.assertTrue(results[year4.name])
        self.assertEqual(self.pm.read_attribute(player, year1), 45000000)
        self.assertEqual(self.pm.read_attribute(player, year2), 49111111)
        self.assertEqual(self.pm.read_attribute(player, year3), 53222222)
        self.assertEqual(self.pm.read_attribute(player, year4), 57333333)
        self.assertEqual(self.pm.read_attribute(player, contract_years), 4)

    def test_write_attribute_contract_years_expands_future_salary_slots(self):
        player = Player(
            index=0,
            record_address=PLAYER_TABLE_BASE,
            first_name="LeBron",
            last_name="James",
        )
        year1 = self.config.find_attribute_by_description("Year 1 Salary")
        year2 = self.config.find_attribute_by_description("Year 2 Salary")
        year3 = self.config.find_attribute_by_description("Year 3 Salary")
        year4 = self.config.find_attribute_by_description("Year 4 Salary")
        year5 = self.config.find_attribute_by_description("Year 5 Salary")
        contract_years = self.config.find_attribute_by_description("Contract Years Left")

        self.mem.write_bitfield(player.record_address + year1.offset, year1.bit_start, year1.bit_length, 52627153)
        self.mem.write_bitfield(player.record_address + year2.offset, year2.bit_start, year2.bit_length, 0)
        self.mem.write_bitfield(player.record_address + year3.offset, year3.bit_start, year3.bit_length, 0)
        self.mem.write_bitfield(player.record_address + year4.offset, year4.bit_start, year4.bit_length, 0)
        self.mem.write_bitfield(player.record_address + year5.offset, year5.bit_start, year5.bit_length, 7777777)
        self.mem.write_bitfield(
            player.record_address + contract_years.offset,
            contract_years.bit_start,
            contract_years.bit_length,
            1,
        )

        self.assertTrue(self.pm.write_attribute(player, contract_years, 4))
        self.assertEqual(self.pm.read_attribute(player, contract_years), 4)
        self.assertEqual(self.pm.read_attribute(player, year1), 52627153)
        self.assertEqual(self.pm.read_attribute(player, year2), 52627153)
        self.assertEqual(self.pm.read_attribute(player, year3), 52627153)
        self.assertEqual(self.pm.read_attribute(player, year4), 52627153)
        self.assertEqual(self.pm.read_attribute(player, year5), 0)

    def test_write_all_attributes_contract_years_truncates_future_salary_slots(self):
        player = Player(
            index=0,
            record_address=PLAYER_TABLE_BASE,
            first_name="Luka",
            last_name="Doncic",
        )
        salary_attrs = [
            self.config.find_attribute_by_description(f"Year {index} Salary")
            for index in range(1, 7)
        ]
        contract_years = self.config.find_attribute_by_description("Contract Years Left")
        starting_values = [45999660, 49641600, 53612928, 57584256, 1200000, 800000]
        for attr, value in zip(salary_attrs, starting_values):
            self.mem.write_bitfield(player.record_address + attr.offset, attr.bit_start, attr.bit_length, value)
        self.mem.write_bitfield(
            player.record_address + contract_years.offset,
            contract_years.bit_start,
            contract_years.bit_length,
            6,
        )

        results = self.pm.write_all_attributes(
            player,
            {
                contract_years.name: 2,
            },
        )

        self.assertTrue(results[contract_years.name])
        self.assertEqual(self.pm.read_attribute(player, contract_years), 2)
        self.assertEqual(self.pm.read_attribute(player, salary_attrs[0]), 45999660)
        self.assertEqual(self.pm.read_attribute(player, salary_attrs[1]), 49641600)
        self.assertEqual(self.pm.read_attribute(player, salary_attrs[2]), 0)
        self.assertEqual(self.pm.read_attribute(player, salary_attrs[3]), 0)
        self.assertEqual(self.pm.read_attribute(player, salary_attrs[4]), 0)
        self.assertEqual(self.pm.read_attribute(player, salary_attrs[5]), 0)

    def test_write_attribute_contract_years_clamps_to_six_salary_slots(self):
        player = Player(
            index=0,
            record_address=PLAYER_TABLE_BASE,
            first_name="LeBron",
            last_name="James",
        )
        salary_attrs = [
            self.config.find_attribute_by_description(f"Year {index} Salary")
            for index in range(1, 7)
        ]
        contract_years = self.config.find_attribute_by_description("Contract Years Left")

        self.mem.write_bitfield(
            player.record_address + contract_years.offset,
            contract_years.bit_start,
            contract_years.bit_length,
            1,
        )
        self.mem.write_bitfield(
            player.record_address + salary_attrs[0].offset,
            salary_attrs[0].bit_start,
            salary_attrs[0].bit_length,
            52627153,
        )

        self.assertTrue(self.pm.write_attribute(player, contract_years, 7))
        self.assertEqual(self.pm.read_attribute(player, contract_years), 6)
        for attr in salary_attrs:
            self.assertEqual(self.pm.read_attribute(player, attr), 52627153)


if __name__ == "__main__":
    unittest.main()
