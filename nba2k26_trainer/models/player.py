"""Player scanning and attribute read/write helpers."""

from __future__ import annotations

import datetime
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ..core.memory import GameMemory
from ..core.offsets import AttributeDef, OffsetConfig
from ..core.scanner import scan_for_base_pointer, scan_for_player_table_candidates


TEAM_PTR_OFFSET = 96
TEAM_PTR_OFFSET_CANDIDATES = (96, 104, 184, 208, 216)
MAX_VALID_POINTER = 0x7FFFFFFFFFFF
PLAYER_TABLE_SAMPLE_SIZE = 24
TEAM_PTR_SAMPLE_SIZE = 120
ROSTER_HINT_SAMPLE_SIZE = 160
TEAM_TABLE_SAMPLE_SIZE = 40
MODULE_REF_CHUNK_SIZE = 0x400000
ACTIVE_TABLE_MIN_MODULE_REFS = 24
CACHED_TABLE_MIN_MODULE_REFS = 8
DETAILED_MODULE_REF_CANDIDATE_LIMIT = 8
LIVE_OVERALL_SAMPLE_SIZE = 160
LIVE_OVERALL_TARGET_MEAN = 76.0
LIVE_OVERALL_TARGET_STDDEV = 7.0
FREE_AGENT_TEAM_ID = -2
UNKNOWN_TEAM_ID = -3
PACKED_RATING_OFFSET_MIN = 993
PACKED_RATING_OFFSET_MAX = 1045
LIVE_BADGE_OFFSET_MIN = 1148
LIVE_BADGE_OFFSET_MAX = 1161
LIVE_BADGE_MAX_TIER = 4
BODY_RECORD_PTR_OFFSET = 120
BODY_HEIGHT_INCHES_OFFSET = 1
BODY_WINGSPAN_INCHES_OFFSET = 3
BODY_TRUNK_SCALE_OFFSET = 4
BODY_SHOULDER_SCALE_OFFSET = 8
BODY_ARM_SCALE_OFFSET = 16
BODY_NECK_SCALE_OFFSET = 20
POUNDS_PER_KG = 2.2046226218

DEFAULT_TEAM_NAMES = {
    0: "ATL Hawks",
    1: "BOS Celtics",
    2: "BKN Nets",
    3: "CHA Hornets",
    4: "CHI Bulls",
    5: "CLE Cavaliers",
    6: "DAL Mavericks",
    7: "DEN Nuggets",
    8: "DET Pistons",
    9: "GSW Warriors",
    10: "HOU Rockets",
    11: "IND Pacers",
    12: "LAC Clippers",
    13: "LAL Lakers",
    14: "MEM Grizzlies",
    15: "MIA Heat",
    16: "MIL Bucks",
    17: "MIN Timberwolves",
    18: "NOP Pelicans",
    19: "NYK Knicks",
    20: "OKC Thunder",
    21: "ORL Magic",
    22: "PHI 76ers",
    23: "PHX Suns",
    24: "POR Trail Blazers",
    25: "SAC Kings",
    26: "SAS Spurs",
    27: "TOR Raptors",
    28: "UTA Jazz",
    29: "WAS Wizards",
}

TEAM_NAMES = DEFAULT_TEAM_NAMES
POSITION_MAP = {0: "PG", 1: "SG", 2: "SF", 3: "PF", 4: "C"}

LEGEND_FULL_NAMES = {
    ("Magic", "Johnson"),
    ("Michael", "Jordan"),
    ("Scottie", "Pippen"),
    ("Larry", "Bird"),
    ("Kobe", "Bryant"),
    ("Kareem", "Abdul-Jabbar"),
    ("Shaquille", "O'Neal"),
    ("Tim", "Duncan"),
    ("Manu", "Ginobili"),
    ("Tony", "Parker"),
    ("Allen", "Iverson"),
    ("Dirk", "Nowitzki"),
    ("Tracy", "McGrady"),
    ("Paul", "Pierce"),
    ("Dwyane", "Wade"),
    ("Steve", "Francis"),
    ("Baron", "Davis"),
    ("Hedo", "Turkoglu"),
    ("Lamar", "Odom"),
    ("Yao", "Ming"),
    ("Ming", "Yao"),
    ("John", "Paxson"),
    ("Horace", "Grant"),
    ("James", "Worthy"),
    ("A.C.", "Green"),
    ("Michael", "Cooper"),
    ("Vlade", "Divac"),
}

MODERN_FULL_NAMES = {
    ("LeBron", "James"),
    ("Stephen", "Curry"),
    ("Kevin", "Durant"),
    ("Nikola", "Jokic"),
    ("Luka", "Doncic"),
    ("Jayson", "Tatum"),
    ("Victor", "Wembanyama"),
    ("Devin", "Booker"),
    ("Joel", "Embiid"),
    ("Ja", "Morant"),
    ("Zion", "Williamson"),
    ("Shai", "Gilgeous-Alexander"),
    ("Tyrese", "Haliburton"),
    ("Anthony", "Edwards"),
    ("Anthony", "Davis"),
    ("Paul", "George"),
    ("Jamal", "Murray"),
    ("Michael", "Porter Jr."),
    ("RJ", "Barrett"),
    ("Christian", "Braun"),
    ("Dorian", "Finney-Smith"),
    ("Jordan", "Goodwin"),
}

LIVE_OVERALL_ATTR_CANDIDATES = (
    AttributeDef(
        name="Live Overall Rating (bit418)",
        offset=418,
        type="bitfield",
        bit_start=1,
        bit_length=7,
        min_val=0,
        max_val=99,
        category="Misc",
        description="Live Overall Rating",
    ),
    AttributeDef(
        name="Live Overall Rating (bit1028)",
        offset=1028,
        type="bitfield",
        bit_start=1,
        bit_length=7,
        min_val=0,
        max_val=99,
        category="Misc",
        description="Live Overall Rating Alt",
    ),
)


@dataclass
class Player:
    index: int
    record_address: int
    first_name: str = ""
    last_name: str = ""
    team_id: int = UNKNOWN_TEAM_ID
    team_name: str = ""
    overall: int = 0
    age: int = 0
    birth_year: int = 0
    position: str = ""

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


@dataclass
class TableMetrics:
    non_empty: int = 0
    valid_names: int = 0
    valid_overall: int = 0
    valid_birth_year: int = 0
    valid_team_refs: int = 0
    score: int = 0
    team_ptr_offset: int = TEAM_PTR_OFFSET
    team_ptr_quality: int = 0
    legend_hits: int = 0
    modern_hits: int = 0
    module_ref_count: int = 0
    selection_score: int = 0


def _normalize_text(text: Optional[str]) -> str:
    return (text or "").strip()


def _is_pointer_like(value: Optional[int]) -> bool:
    return bool(value) and 0x10000 < int(value) < MAX_VALID_POINTER


def _is_valid_name(text: str) -> bool:
    text = _normalize_text(text)
    if len(text) < 2 or len(text) > 32:
        return False

    letters = 0
    weird = 0
    for char in text:
        code = ord(char)
        if code < 32 or code == 0xFFFD:
            return False
        if char.isalpha():
            letters += 1
            continue
        if char.isdigit() or char in " .'-&":
            continue
        weird += 1

    if letters < 2:
        return False
    return weird <= max(1, len(text) // 5)


def _is_valid_team_name(text: str) -> bool:
    text = _normalize_text(text)
    if not _is_valid_name(text):
        return False

    keywords = (
        "hawks",
        "celtics",
        "nets",
        "hornets",
        "bulls",
        "cavaliers",
        "mavericks",
        "nuggets",
        "pistons",
        "warriors",
        "rockets",
        "pacers",
        "clippers",
        "lakers",
        "grizzlies",
        "heat",
        "bucks",
        "timberwolves",
        "pelicans",
        "knicks",
        "thunder",
        "magic",
        "76ers",
        "suns",
        "trail blazers",
        "kings",
        "spurs",
        "raptors",
        "jazz",
        "wizards",
        "free agent",
    )
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords) or len(text) >= 4


def birth_year_to_age(birth_year: int) -> int:
    if birth_year <= 0 or birth_year > datetime.datetime.now().year:
        return 0
    return datetime.datetime.now().year - birth_year


def age_to_birth_year(age: int) -> int:
    return datetime.datetime.now().year - age


class PlayerManager:
    def __init__(self, mem: GameMemory, config: OffsetConfig):
        self.mem = mem
        self.config = config
        self.roster_mode = "auto"
        self.players: List[Player] = []
        self._table_base: Optional[int] = None
        self._team_table_base: Optional[int] = None
        self._overall_attr: Optional[AttributeDef] = None
        self._birth_year_attr: Optional[AttributeDef] = None
        self._module_scan_ranges: Optional[List[Tuple[int, int]]] = None
        self._team_ptr_offset_cache: Dict[int, Tuple[int, int]] = {}
        self._live_team_ptr_offset_cache: Dict[int, Tuple[int, int]] = {}
        self._live_overall_attr_cache: Dict[int, Tuple[AttributeDef, int]] = {}
        self._module_ref_count_cache: Dict[int, int] = {}

    def set_roster_mode(self, mode: str) -> None:
        mode = (mode or "auto").strip().lower()
        if mode not in {"auto", "current", "legend"}:
            mode = "auto"
        if self.roster_mode == mode:
            return
        self.roster_mode = mode
        self._table_base = None
        self._team_ptr_offset_cache.clear()
        self._live_team_ptr_offset_cache.clear()
        self._live_overall_attr_cache.clear()
        self._module_ref_count_cache.clear()

    def begin_refresh(self, *, force_rescan: bool = False) -> None:
        if force_rescan:
            self._table_base = None
            self._team_table_base = None
            self._team_ptr_offset_cache.clear()
            self._live_team_ptr_offset_cache.clear()
            self._live_overall_attr_cache.clear()
            self._module_ref_count_cache.clear()

    def _is_cached_table_base_valid(self, table_base: int) -> bool:
        pt = self.config.player_table
        valid_names = 0

        for index in range(min(8, pt.max_players)):
            record_address = table_base + index * pt.stride
            last_name = _normalize_text(
                self.mem.read_wstring(record_address + pt.last_name_offset, pt.name_string_length)
            )
            first_name = _normalize_text(
                self.mem.read_wstring(record_address + pt.first_name_offset, pt.name_string_length)
            )
            if _is_valid_name(first_name) or _is_valid_name(last_name):
                valid_names += 1

        if valid_names < 3:
            return False

        if self.roster_mode == "auto":
            config_candidates = {base for base, _ in self._get_config_player_table_candidates()}
            if config_candidates and table_base not in config_candidates:
                return self._count_module_pointer_refs(table_base) >= ACTIVE_TABLE_MIN_MODULE_REFS
            return self._count_module_pointer_refs(table_base) >= CACHED_TABLE_MIN_MODULE_REFS

        return True

    def _get_module_scan_ranges(self) -> List[Tuple[int, int]]:
        if self._module_scan_ranges is not None:
            return self._module_scan_ranges

        module_base = int(self.mem.base_address or 0)
        if module_base <= 0:
            self._module_scan_ranges = []
            return self._module_scan_ranges

        pe_header_offset = self.mem.read_uint32(module_base + 0x3C)
        if not isinstance(pe_header_offset, int) or pe_header_offset <= 0:
            self._module_scan_ranges = []
            return self._module_scan_ranges

        number_of_sections = self.mem.read_uint16(module_base + pe_header_offset + 6)
        size_of_optional_header = self.mem.read_uint16(module_base + pe_header_offset + 20)
        if not isinstance(number_of_sections, int) or not isinstance(size_of_optional_header, int):
            self._module_scan_ranges = []
            return self._module_scan_ranges

        section_base = module_base + pe_header_offset + 24 + size_of_optional_header
        ranges: List[Tuple[int, int]] = []

        for index in range(number_of_sections):
            header_address = section_base + index * 40
            virtual_size = self.mem.read_uint32(header_address + 8)
            virtual_address = self.mem.read_uint32(header_address + 12)
            raw_size = self.mem.read_uint32(header_address + 16)
            characteristics = self.mem.read_uint32(header_address + 36)

            if not all(isinstance(value, int) for value in (virtual_size, virtual_address, raw_size, characteristics)):
                continue
            if not (characteristics & 0x40000000):
                continue

            section_size = max(int(virtual_size), int(raw_size))
            if section_size <= 0:
                continue
            ranges.append((module_base + int(virtual_address), section_size))

        self._module_scan_ranges = ranges
        return ranges

    def _count_module_pointer_refs(self, table_base: int) -> int:
        cached = self._module_ref_count_cache.get(table_base)
        if cached is not None:
            return cached

        ranges = self._get_module_scan_ranges()
        if not ranges:
            self._module_ref_count_cache[table_base] = 0
            return 0

        target = int(table_base).to_bytes(8, byteorder="little")
        count = 0

        for range_base, range_size in ranges:
            offset = 0
            while offset < range_size:
                read_size = min(MODULE_REF_CHUNK_SIZE + 7, range_size - offset)
                data = self.mem.read_bytes(range_base + offset, read_size)
                if data:
                    index = data.find(target)
                    while index != -1:
                        absolute = range_base + offset + index
                        if absolute % 8 == 0:
                            count += 1
                        index = data.find(target, index + 1)
                offset += MODULE_REF_CHUNK_SIZE

        self._module_ref_count_cache[table_base] = count
        return count

    def _find_attribute(
        self, names: Tuple[str, ...], description: Optional[str] = None
    ) -> Optional[AttributeDef]:
        for name in names:
            attr = self.config.get_attribute(name)
            if attr is not None:
                return attr
        if description:
            return self.config.find_attribute_by_description(description)
        return None

    def _get_overall_attr(self) -> Optional[AttributeDef]:
        if self._overall_attr is None:
            self._overall_attr = self._find_attribute(("综合评分",), "Overall Rating")
        return self._overall_attr

    def _get_birth_year_attr(self) -> Optional[AttributeDef]:
        if self._birth_year_attr is None:
            self._birth_year_attr = self._find_attribute(("出生年份",), "Birth Year")
        return self._birth_year_attr

    def _is_overall_attr(self, attr: Optional[AttributeDef]) -> bool:
        return bool(attr) and attr.description.strip().lower() == "overall rating"

    def _get_table_base_for_player(self, player: Player) -> Optional[int]:
        if self._table_base is not None:
            return self._table_base
        if player.index < 0:
            return None
        return player.record_address - player.index * self.config.player_table.stride

    def _read_value_at(self, record_address: int, attr: Optional[AttributeDef]) -> Optional[Any]:
        if attr is None:
            return None
        player = Player(index=-1, record_address=record_address)
        return self._read_attribute_direct(player, attr)

    def _is_live_packed_rating_attr(self, attr: AttributeDef) -> bool:
        return (
            attr.type == "uint8"
            and PACKED_RATING_OFFSET_MIN <= attr.offset <= PACKED_RATING_OFFSET_MAX
            and attr.max_val <= 99
        )

    def _is_live_badge_attr(self, attr: AttributeDef) -> bool:
        return (
            attr.type == "bitfield"
            and attr.bit_length == 3
            and LIVE_BADGE_OFFSET_MIN <= attr.offset <= LIVE_BADGE_OFFSET_MAX
        )

    def _effective_attr_max(self, attr: AttributeDef) -> int:
        if self._is_live_badge_attr(attr):
            return LIVE_BADGE_MAX_TIER
        return attr.max_val

    def _is_body_attr(self, attr: AttributeDef) -> bool:
        return attr.description in {
            "Height in cm",
            "Wingspan in cm",
            "Weight (kg)",
            "Trunk Length",
            "Shoulder Width",
            "Arm Scale",
            "Neck Length",
        }

    def _get_body_record_base(self, player: Player) -> Optional[int]:
        ptr = self.mem.read_uint64(player.record_address + BODY_RECORD_PTR_OFFSET)
        if _is_pointer_like(ptr):
            return int(ptr)
        return None

    def _read_body_attr(self, player: Player, attr: AttributeDef) -> Optional[Any]:
        description = attr.description
        if description == "Weight (kg)":
            pounds = self.mem.read_float(player.record_address + attr.offset)
            if pounds is None:
                return None
            return round(float(pounds) / POUNDS_PER_KG, 2)

        body_base = self._get_body_record_base(player)
        if body_base is None:
            return None

        if description == "Height in cm":
            inches = self.mem.read_uint8(body_base + BODY_HEIGHT_INCHES_OFFSET)
            if inches is None:
                return None
            return int(round(float(inches) * 2.54))

        if description == "Wingspan in cm":
            inches = self.mem.read_uint8(body_base + BODY_WINGSPAN_INCHES_OFFSET)
            if inches is None:
                return None
            return int(round(float(inches) * 2.54))

        scale_offsets = {
            "Trunk Length": BODY_TRUNK_SCALE_OFFSET,
            "Shoulder Width": BODY_SHOULDER_SCALE_OFFSET,
            "Arm Scale": BODY_ARM_SCALE_OFFSET,
            "Neck Length": BODY_NECK_SCALE_OFFSET,
        }
        scale_offset = scale_offsets.get(description)
        if scale_offset is None:
            return None

        scale = self.mem.read_float(body_base + scale_offset)
        if scale is None:
            return None
        return round(float(scale) * 100.0, 2)

    def _write_body_attr(self, player: Player, attr: AttributeDef, value: Any) -> bool:
        description = attr.description
        if description == "Weight (kg)":
            pounds = float(value) * POUNDS_PER_KG
            return self.mem.write_float(player.record_address + attr.offset, pounds)

        body_base = self._get_body_record_base(player)
        if body_base is None:
            return False

        if description == "Height in cm":
            inches = int(round(float(value) / 2.54))
            return self.mem.write_uint8(body_base + BODY_HEIGHT_INCHES_OFFSET, inches)

        if description == "Wingspan in cm":
            inches = int(round(float(value) / 2.54))
            return self.mem.write_uint8(body_base + BODY_WINGSPAN_INCHES_OFFSET, inches)

        scale_offsets = {
            "Trunk Length": BODY_TRUNK_SCALE_OFFSET,
            "Shoulder Width": BODY_SHOULDER_SCALE_OFFSET,
            "Arm Scale": BODY_ARM_SCALE_OFFSET,
            "Neck Length": BODY_NECK_SCALE_OFFSET,
        }
        scale_offset = scale_offsets.get(description)
        if scale_offset is None:
            return False

        scale = float(value) / 100.0
        return self.mem.write_float(body_base + scale_offset, scale)

    def _append_pointer_candidates(
        self, candidates: List[Tuple[int, str]], raw_value: Optional[int], source: str
    ) -> None:
        if not _is_pointer_like(raw_value):
            return

        value = int(raw_value)
        candidates.append((value, source))

        nested = self.mem.read_uint64(value)
        if _is_pointer_like(nested):
            candidates.append((int(nested), f"{source} -> deref"))

    def _get_config_player_table_candidates(self) -> List[Tuple[int, str]]:
        pt = self.config.player_table
        candidates: List[Tuple[int, str]] = []

        if pt.direct_table and pt.base_pointer > 0:
            self._append_pointer_candidates(
                candidates,
                self.mem.read_uint64(self.mem.base_address + pt.base_pointer),
                f"module_base + 0x{pt.base_pointer:X}",
            )
            self._append_pointer_candidates(
                candidates,
                self.mem.read_uint64(pt.base_pointer),
                f"absolute 0x{pt.base_pointer:X}",
            )

        if pt.pointer_offsets:
            pointer_chain = self.mem.resolve_pointer_chain(self.mem.base_address, pt.pointer_offsets)
            self._append_pointer_candidates(candidates, pointer_chain, "pointer chain")

        unique_candidates: List[Tuple[int, str]] = []
        seen = set()
        for base, source in candidates:
            if base in seen:
                continue
            seen.add(base)
            unique_candidates.append((base, source))
        return unique_candidates

    def _count_roster_name_hits(self, table_base: int) -> Tuple[int, int]:
        pt = self.config.player_table
        legend_hits = 0
        modern_hits = 0

        for index in range(min(ROSTER_HINT_SAMPLE_SIZE, pt.max_players)):
            record_address = table_base + index * pt.stride
            last_name = _normalize_text(
                self.mem.read_wstring(record_address + pt.last_name_offset, pt.name_string_length)
            )
            first_name = _normalize_text(
                self.mem.read_wstring(record_address + pt.first_name_offset, pt.name_string_length)
            )
            if not first_name and not last_name:
                continue

            full_name = (first_name, last_name)
            if full_name in LEGEND_FULL_NAMES:
                legend_hits += 1
            if full_name in MODERN_FULL_NAMES:
                modern_hits += 1

        return legend_hits, modern_hits

    def _read_team_name_from_pointer(
        self, team_ptr: Optional[int], team_table_base: Optional[int]
    ) -> str:
        if not _is_pointer_like(team_ptr):
            return ""

        team_table = self.config.team_table
        ptr_value = int(team_ptr)
        if team_table_base is not None and team_table.stride > 0:
            relative = ptr_value - team_table_base
            table_size = team_table.stride * max(team_table.max_teams, 64)
            if 0 <= relative < table_size:
                team_index = relative // team_table.stride
                record_base = team_table_base + team_index * team_table.stride
                team_name = self._read_team_name_from_base(record_base)
                if team_name:
                    return team_name
                return DEFAULT_TEAM_NAMES.get(team_index, "")

        return self._read_team_name_from_base(ptr_value)

    def _score_team_ptr_offset(
        self,
        table_base: int,
        team_ptr_offset: int,
        team_table_base: Optional[int],
    ) -> int:
        pt = self.config.player_table
        pointer_counts: Counter[int] = Counter()
        zero_count = 0

        for index in range(min(TEAM_PTR_SAMPLE_SIZE, pt.max_players)):
            record_address = table_base + index * pt.stride
            last_name = _normalize_text(
                self.mem.read_wstring(record_address + pt.last_name_offset, pt.name_string_length)
            )
            first_name = _normalize_text(
                self.mem.read_wstring(record_address + pt.first_name_offset, pt.name_string_length)
            )
            if not first_name and not last_name:
                continue

            team_ptr = self.mem.read_uint64(record_address + team_ptr_offset)
            if not team_ptr:
                zero_count += 1
                continue
            if not _is_pointer_like(team_ptr):
                continue
            pointer_counts[int(team_ptr)] += 1

        named_groups = 0
        named_players = 0
        repeated_players = sum(count for count in pointer_counts.values() if count >= 2)

        for team_ptr, count in pointer_counts.items():
            if count < 2:
                continue
            team_name = self._read_team_name_from_pointer(team_ptr, team_table_base)
            if team_name:
                named_groups += 1
                named_players += count

        score = named_players * 5 + repeated_players * 2 + named_groups * 10 - len(pointer_counts)
        if zero_count > TEAM_PTR_SAMPLE_SIZE * 3 // 4:
            score -= 25
        return score

    def _resolve_team_ptr_offset(
        self, table_base: int, team_table_base: Optional[int]
    ) -> Tuple[int, int]:
        cached = self._team_ptr_offset_cache.get(table_base)
        if cached is not None:
            return cached

        best_offset = TEAM_PTR_OFFSET
        best_score = -10**9
        for candidate_offset in TEAM_PTR_OFFSET_CANDIDATES:
            score = self._score_team_ptr_offset(table_base, candidate_offset, team_table_base)
            if score > best_score:
                best_offset = candidate_offset
                best_score = score

        result = (best_offset, best_score)
        self._team_ptr_offset_cache[table_base] = result
        return result

    def _score_live_team_ptr_offset(
        self,
        table_base: int,
        team_ptr_offset: int,
        team_table_base: Optional[int],
    ) -> int:
        player_table = self.config.player_table
        named_players = 0
        team_name_counts: Counter[str] = Counter()

        for index in range(player_table.max_players):
            record_address = table_base + index * player_table.stride
            last_name = _normalize_text(
                self.mem.read_wstring(
                    record_address + player_table.last_name_offset,
                    player_table.name_string_length,
                )
            )
            first_name = _normalize_text(
                self.mem.read_wstring(
                    record_address + player_table.first_name_offset,
                    player_table.name_string_length,
                )
            )
            if not first_name and not last_name:
                continue

            team_ptr = self.mem.read_uint64(record_address + team_ptr_offset)
            team_name = self._read_team_name_from_pointer(team_ptr, team_table_base)
            if team_name:
                named_players += 1
                team_name_counts[team_name] += 1

        if named_players == 0:
            return -10**9

        return named_players * 2 + len(team_name_counts) * 10

    def _resolve_live_team_ptr_offset(
        self, table_base: int, team_table_base: Optional[int]
    ) -> Tuple[int, int]:
        cached = self._live_team_ptr_offset_cache.get(table_base)
        if cached is not None:
            return cached

        best_offset = TEAM_PTR_OFFSET
        best_score = -10**9
        for candidate_offset in TEAM_PTR_OFFSET_CANDIDATES:
            score = self._score_live_team_ptr_offset(table_base, candidate_offset, team_table_base)
            if score > best_score or (score == best_score and candidate_offset < best_offset):
                best_offset = candidate_offset
                best_score = score

        result = (best_offset, best_score)
        self._live_team_ptr_offset_cache[table_base] = result
        return result

    def _iter_live_overall_candidates(self) -> List[AttributeDef]:
        candidates: List[AttributeDef] = []
        overall_attr = self._get_overall_attr()
        if overall_attr is not None:
            candidates.append(overall_attr)
        candidates.extend(LIVE_OVERALL_ATTR_CANDIDATES)
        return candidates

    def _score_live_overall_attr(self, table_base: int, attr: AttributeDef) -> int:
        pt = self.config.player_table
        valid_values: List[int] = []
        named_values: List[int] = []
        low_named = 0
        low_all = 0

        for index in range(min(LIVE_OVERALL_SAMPLE_SIZE, pt.max_players)):
            record_address = table_base + index * pt.stride
            last_name = _normalize_text(
                self.mem.read_wstring(record_address + pt.last_name_offset, pt.name_string_length)
            )
            first_name = _normalize_text(
                self.mem.read_wstring(record_address + pt.first_name_offset, pt.name_string_length)
            )
            if not first_name and not last_name:
                continue

            value = self._read_value_at(record_address, attr)
            if not isinstance(value, int) or not (25 <= value <= 99):
                continue

            valid_values.append(value)
            if value < 50:
                low_all += 1

            full_name = (first_name, last_name)
            if full_name in MODERN_FULL_NAMES or full_name in LEGEND_FULL_NAMES:
                named_values.append(value)
                if value < 70:
                    low_named += 1

        if len(valid_values) < 8:
            return -10**9

        average = sum(valid_values) / len(valid_values)
        variance = sum((value - average) ** 2 for value in valid_values) / len(valid_values)
        stddev = variance ** 0.5
        named_high = sum(value >= 80 for value in named_values)
        named_elite = sum(value >= 90 for value in named_values)

        score = len(valid_values) * 6
        score += len(named_values) * 18
        score += named_high * 8
        score += named_elite * 5
        score -= low_named * 40
        score -= int(round(abs(average - LIVE_OVERALL_TARGET_MEAN) * 14))
        score -= int(round(abs(stddev - LIVE_OVERALL_TARGET_STDDEV) * 8))

        low_all_threshold = max(4, len(valid_values) // 6)
        if low_all > low_all_threshold:
            score -= (low_all - low_all_threshold) * 8

        return score

    def _resolve_live_overall_attr(self, table_base: Optional[int]) -> Optional[AttributeDef]:
        if table_base is None:
            return self._get_overall_attr()

        cached = self._live_overall_attr_cache.get(table_base)
        if cached is not None:
            return cached[0]

        candidates = self._iter_live_overall_candidates()
        if not candidates:
            return None

        best_attr = candidates[0]
        best_score = -10**9
        for candidate in candidates:
            score = self._score_live_overall_attr(table_base, candidate)
            if score > best_score:
                best_attr = candidate
                best_score = score

        self._live_overall_attr_cache[table_base] = (best_attr, best_score)
        return best_attr

    def _score_player_table_base(
        self,
        table_base: int,
        *,
        include_module_refs: bool = True,
    ) -> TableMetrics:
        metrics = TableMetrics()
        pt = self.config.player_table
        overall_attr = self._resolve_live_overall_attr(table_base)
        birth_year_attr = self._get_birth_year_attr()
        team_table_base = self._resolve_team_table_base()
        if include_module_refs:
            metrics.module_ref_count = self._count_module_pointer_refs(table_base)
        metrics.team_ptr_offset, metrics.team_ptr_quality = self._resolve_team_ptr_offset(
            table_base, team_table_base
        )
        metrics.legend_hits, metrics.modern_hits = self._count_roster_name_hits(table_base)

        for index in range(min(PLAYER_TABLE_SAMPLE_SIZE, pt.max_players)):
            record_address = table_base + index * pt.stride
            last_name = _normalize_text(
                self.mem.read_wstring(record_address + pt.last_name_offset, pt.name_string_length)
            )
            first_name = _normalize_text(
                self.mem.read_wstring(record_address + pt.first_name_offset, pt.name_string_length)
            )

            if not first_name and not last_name:
                continue

            metrics.non_empty += 1

            if _is_valid_name(first_name) or _is_valid_name(last_name):
                metrics.valid_names += 1

            overall = self._read_value_at(record_address, overall_attr)
            if isinstance(overall, int) and 25 <= overall <= 99:
                metrics.valid_overall += 1

            birth_year = self._read_value_at(record_address, birth_year_attr)
            if isinstance(birth_year, int) and 1950 <= birth_year <= datetime.datetime.now().year:
                metrics.valid_birth_year += 1

            team_ptr = self.mem.read_uint64(record_address + metrics.team_ptr_offset)
            if team_ptr == 0:
                metrics.valid_team_refs += 1
            else:
                team_name = self._read_team_name_from_pointer(team_ptr, team_table_base)
                if team_name:
                    metrics.valid_team_refs += 1

        metrics.score = (
            metrics.valid_names * 5
            + metrics.valid_overall * 4
            + metrics.valid_birth_year * 3
            + metrics.valid_team_refs * 2
        )
        if metrics.non_empty > metrics.valid_names:
            metrics.score -= (metrics.non_empty - metrics.valid_names) * 3
        metrics.selection_score = (
            metrics.score
            + min(80, metrics.team_ptr_quality // 16)
            + min(180, metrics.module_ref_count * 3)
        )
        return metrics

    def _is_promising_player_table(self, metrics: TableMetrics) -> bool:
        if metrics.non_empty == 0:
            return False

        required_names = min(4, metrics.non_empty)
        required_overall = min(3, metrics.non_empty)
        required_birth_year = min(2, metrics.non_empty)
        required_team_refs = min(2, metrics.non_empty)

        # Names remain the strongest signal, but we no longer hard-fail if a
        # single attribute offset such as OVR drifts after a patch.
        has_secondary_signal = (
            metrics.valid_birth_year >= required_birth_year
            or metrics.valid_overall >= required_overall
            or (
                metrics.valid_team_refs >= required_team_refs
                and (metrics.valid_birth_year >= 1 or metrics.valid_overall >= 1)
            )
        )

        return (
            metrics.valid_names >= required_names
            and has_secondary_signal
            and metrics.score >= 18
        )

    def _matches_requested_roster_mode(self, metrics: TableMetrics) -> bool:
        if self.roster_mode == "legend":
            return (
                metrics.legend_hits >= 8
                and metrics.modern_hits <= 2
                and metrics.team_ptr_quality >= 600
            )
        if self.roster_mode == "current":
            return metrics.modern_hits >= 4 and metrics.legend_hits <= 2
        return True

    def _pick_best_player_table(
        self,
        candidates: List[Tuple[int, str]],
        progress_callback=None,
        *,
        include_module_refs: bool = True,
    ) -> Optional[int]:
        seen = set()
        profiled_candidates: List[Tuple[int, str, TableMetrics]] = []

        for base, source in candidates:
            if base in seen:
                continue
            seen.add(base)

            metrics = self._score_player_table_base(base, include_module_refs=False)
            profiled_candidates.append((base, source, metrics))
            if progress_callback:
                progress_callback(
                    "Player table candidate "
                    f"{source}: 0x{base:X} "
                    f"(names={metrics.valid_names}, ovr={metrics.valid_overall}, "
                    f"birth={metrics.valid_birth_year}, teams={metrics.valid_team_refs}, "
                    f"team_off=0x{metrics.team_ptr_offset:X}, team_q={metrics.team_ptr_quality}, "
                    f"legend={metrics.legend_hits}, modern={metrics.modern_hits}, "
                    "module_refs=pending, "
                    f"score={metrics.score})"
                )

        promising = [
            (base, source, metrics)
            for base, source, metrics in profiled_candidates
            if self._is_promising_player_table(metrics)
        ]

        if not promising:
            return None

        def preliminary_rank(entry: Tuple[int, str, TableMetrics]) -> Tuple[int, int, int]:
            _, source, metrics = entry
            source_bonus = 25 if "module_base" in source else 0
            return (
                metrics.selection_score + source_bonus,
                metrics.team_ptr_quality,
                metrics.valid_names,
            )

        if include_module_refs:
            detailed_candidates = sorted(
                promising,
                key=preliminary_rank,
                reverse=True,
            )[:DETAILED_MODULE_REF_CANDIDATE_LIMIT]
            rescored_metrics: Dict[int, TableMetrics] = {}

            for base, source, _ in detailed_candidates:
                rescored = self._score_player_table_base(base, include_module_refs=True)
                rescored_metrics[base] = rescored
                if progress_callback:
                    progress_callback(
                        "Detailed player table candidate "
                        f"{source}: 0x{base:X} "
                        f"(team_off=0x{rescored.team_ptr_offset:X}, "
                        f"team_q={rescored.team_ptr_quality}, legend={rescored.legend_hits}, "
                        f"modern={rescored.modern_hits}, module_refs={rescored.module_ref_count}, "
                        f"score={rescored.score})"
                    )

            promising = [
                (base, source, rescored_metrics.get(base, metrics))
                for base, source, metrics in promising
            ]

        def candidate_rank(entry: Tuple[int, str, TableMetrics]) -> Tuple[int, int, int, int, int]:
            _, source, metrics = entry
            source_bonus = 25 if "module_base" in source else 0
            return (
                metrics.selection_score + source_bonus,
                metrics.module_ref_count,
                metrics.team_ptr_quality,
                metrics.valid_names,
                metrics.valid_team_refs,
            )

        modern_candidates = [
            entry
            for entry in promising
            if entry[2].modern_hits >= 4 and entry[2].legend_hits <= 2 and entry[2].team_ptr_quality >= 500
        ]
        legend_candidates = [
            entry
            for entry in promising
            if entry[2].legend_hits >= 8 and entry[2].modern_hits <= 2 and entry[2].team_ptr_quality >= 700
        ]
        active_candidates = [
            entry
            for entry in promising
            if entry[2].module_ref_count >= 8
        ]

        selected: Tuple[int, str, TableMetrics]
        if self.roster_mode == "legend" and legend_candidates:
            selected = max(legend_candidates, key=candidate_rank)
        elif self.roster_mode == "current" and modern_candidates:
            selected = max(modern_candidates, key=candidate_rank)
        elif self.roster_mode == "auto" and active_candidates:
            selected = max(active_candidates, key=candidate_rank)
        elif self.roster_mode == "auto" and legend_candidates and modern_candidates:
            best_legend = max(legend_candidates, key=candidate_rank)
            best_modern = max(modern_candidates, key=candidate_rank)
            if (
                best_legend[2].team_ptr_quality >= best_modern[2].team_ptr_quality + 70
                and best_legend[2].legend_hits >= best_modern[2].modern_hits + 8
            ):
                selected = best_legend
            else:
                selected = max(promising, key=candidate_rank)
        else:
            selected = max(promising, key=candidate_rank)

        best_base, best_source, best_metrics = selected
        if best_base is not None:
            if progress_callback:
                progress_callback(
                    f"Using player table from {best_source}: 0x{best_base:X} "
                    f"(team_off=0x{best_metrics.team_ptr_offset:X}, "
                    f"module_refs={best_metrics.module_ref_count}, mode={self.roster_mode})"
                )
            return best_base
        return None

    def _resolve_table_base(self, progress_callback=None) -> Optional[int]:
        if self._table_base is not None:
            if self._is_cached_table_base_valid(self._table_base):
                if progress_callback:
                    progress_callback(f"Using cached player table: 0x{self._table_base:X}")
                return self._table_base
            self._table_base = None

        pt = self.config.player_table
        candidates = self._get_config_player_table_candidates()

        best_base = self._pick_best_player_table(
            candidates,
            progress_callback,
            include_module_refs=False,
        )
        if best_base is not None:
            best_metrics = self._score_player_table_base(
                best_base,
                include_module_refs=False,
            )
            if self._matches_requested_roster_mode(best_metrics):
                self._table_base = best_base
                return best_base
            if progress_callback:
                progress_callback(
                    "Configured pointers found a roster table, but it does not match the selected roster mode. "
                    "Scanning memory for a better match..."
                )

        if progress_callback:
            progress_callback("Config pointers did not validate. Scanning memory for a better player table...")

        scanned_candidates = scan_for_player_table_candidates(
            self.mem,
            stride=pt.stride,
            last_name_offset=pt.last_name_offset,
            first_name_offset=pt.first_name_offset,
            name_max_chars=pt.name_string_length,
            max_players=pt.max_players,
            progress_callback=progress_callback,
        )

        if not scanned_candidates:
            return None

        scan_candidates: List[Tuple[int, str]] = []
        for scanned_base, valid_count in scanned_candidates:
            scan_candidates.append((scanned_base, f"memory scan ({valid_count} names)"))
            nested = self.mem.read_uint64(scanned_base)
            if _is_pointer_like(nested):
                scan_candidates.append((int(nested), f"memory scan ({valid_count} names) -> deref"))

        best_base = self._pick_best_player_table(scan_candidates, progress_callback)
        if best_base is None:
            return None

        new_rva = scan_for_base_pointer(self.mem, best_base, self.mem.base_address)
        if new_rva is not None and progress_callback:
            progress_callback(
                f"Suggested player_table.base_pointer update: 0x{new_rva:X} ({new_rva})"
            )

        self._table_base = best_base
        return best_base

    def _read_team_name_from_base(self, record_base: int) -> str:
        team_table = self.config.team_table
        offsets_to_try = [
            team_table.team_name_offset,
            0,
            40,
            80,
            692,
            824,
        ]
        seen = set()
        for offset in offsets_to_try:
            if offset in seen:
                continue
            seen.add(offset)
            name = _normalize_text(self.mem.read_wstring(record_base + offset, team_table.team_name_length))
            if _is_valid_team_name(name):
                return name
        return ""

    def _score_team_table_base(self, table_base: int) -> int:
        team_table = self.config.team_table
        valid = 0
        bonus = 0

        for index in range(min(TEAM_TABLE_SAMPLE_SIZE, max(team_table.max_teams, 32))):
            record_base = table_base + index * team_table.stride
            name = self._read_team_name_from_base(record_base)
            if not name:
                continue
            valid += 1
            if name in DEFAULT_TEAM_NAMES.values():
                bonus += 1

        return valid * 2 + bonus

    def _resolve_team_table_base(self, progress_callback=None) -> Optional[int]:
        if self._team_table_base is not None:
            return self._team_table_base

        team_table = self.config.team_table
        if team_table.base_pointer <= 0:
            return None

        candidates: List[Tuple[int, str]] = []
        self._append_pointer_candidates(
            candidates,
            self.mem.read_uint64(self.mem.base_address + team_table.base_pointer),
            f"team module_base + 0x{team_table.base_pointer:X}",
        )
        self._append_pointer_candidates(
            candidates,
            self.mem.read_uint64(team_table.base_pointer),
            f"team absolute 0x{team_table.base_pointer:X}",
        )

        seen = set()
        best_base: Optional[int] = None
        best_score = -1

        for base, source in candidates:
            if base in seen:
                continue
            seen.add(base)

            score = self._score_team_table_base(base)
            if progress_callback:
                progress_callback(
                    f"Team table candidate {source}: 0x{base:X} (score={score})"
                )

            if score > best_score:
                best_base = base
                best_score = score

        if best_base is not None and best_score >= 10:
            self._team_table_base = best_base
            return best_base
        return None

    def _resolve_team_info(
        self,
        team_ptr: Optional[int],
        team_table_base: Optional[int],
        team_cache: Dict[int, Tuple[str, int]],
        next_dynamic_team_id: int,
    ) -> Tuple[Tuple[str, int], int]:
        cache_key = int(team_ptr or 0)
        if cache_key in team_cache:
            return team_cache[cache_key], next_dynamic_team_id

        if not team_ptr:
            team_cache[cache_key] = ("Free Agent", FREE_AGENT_TEAM_ID)
            return team_cache[cache_key], next_dynamic_team_id

        if not _is_pointer_like(team_ptr):
            team_cache[cache_key] = ("Unknown", UNKNOWN_TEAM_ID)
            return team_cache[cache_key], next_dynamic_team_id

        resolved: Optional[Tuple[str, int]] = None
        team_table = self.config.team_table

        if team_table_base is not None and team_table.stride > 0:
            relative = int(team_ptr) - team_table_base
            table_size = team_table.stride * max(team_table.max_teams, 64)
            if 0 <= relative < table_size:
                team_index = relative // team_table.stride
                record_base = team_table_base + team_index * team_table.stride
                team_name = self._read_team_name_from_base(record_base)
                if not team_name:
                    team_name = DEFAULT_TEAM_NAMES.get(team_index, "")
                if team_name:
                    resolved = (team_name, team_index)

        if resolved is None:
            team_name = self._read_team_name_from_pointer(int(team_ptr), team_table_base)
            if team_name:
                resolved = (team_name, next_dynamic_team_id)
                next_dynamic_team_id += 1

        if resolved is None:
            resolved = ("Unknown", UNKNOWN_TEAM_ID)

        team_cache[cache_key] = resolved
        return resolved, next_dynamic_team_id

    def scan_players(self, progress_callback=None) -> List[Player]:
        self._table_base = self._resolve_table_base(progress_callback)
        if self._table_base is None:
            return []

        team_table_base = self._resolve_team_table_base(progress_callback)
        team_ptr_offset, _ = self._resolve_live_team_ptr_offset(self._table_base, team_table_base)
        player_table = self.config.player_table
        players: List[Player] = []
        team_cache: Dict[int, Tuple[str, int]] = {}
        next_dynamic_team_id = 1000
        overall_attr = self._resolve_live_overall_attr(self._table_base)
        birth_year_attr = self._get_birth_year_attr()

        for index in range(player_table.max_players):
            record_address = self._table_base + index * player_table.stride
            last_name = _normalize_text(
                self.mem.read_wstring(record_address + player_table.last_name_offset, player_table.name_string_length)
            )
            first_name = _normalize_text(
                self.mem.read_wstring(record_address + player_table.first_name_offset, player_table.name_string_length)
            )

            if not first_name and not last_name:
                continue
            if not _is_valid_name(first_name) and not _is_valid_name(last_name):
                continue

            player = Player(
                index=index,
                record_address=record_address,
                first_name=first_name,
                last_name=last_name,
            )

            team_ptr = self.mem.read_uint64(record_address + team_ptr_offset)
            (player.team_name, player.team_id), next_dynamic_team_id = self._resolve_team_info(
                team_ptr,
                team_table_base,
                team_cache,
                next_dynamic_team_id,
            )

            overall = self._read_value_at(record_address, overall_attr)
            if isinstance(overall, int) and 0 <= overall <= 99:
                player.overall = overall

            birth_year = self._read_value_at(record_address, birth_year_attr)
            if isinstance(birth_year, int) and 1950 <= birth_year <= datetime.datetime.now().year:
                player.birth_year = birth_year
                player.age = birth_year_to_age(birth_year)

            players.append(player)

        self.players = players
        return players

    def _read_attribute_direct(self, player: Player, attr: AttributeDef) -> Optional[Any]:
        address = player.record_address + attr.offset
        attr_type = attr.type

        if self._is_body_attr(attr):
            return self._read_body_attr(player, attr)

        if self._is_live_packed_rating_attr(attr):
            value = self.mem.read_bitfield(address, 1, 7)
            if value is None:
                return None
            return min(self._effective_attr_max(attr), value)

        if attr_type == "uint8":
            return self.mem.read_uint8(address)
        if attr_type == "int8":
            return self.mem.read_int8(address)
        if attr_type == "uint16":
            return self.mem.read_uint16(address)
        if attr_type == "int16":
            return self.mem.read_int16(address)
        if attr_type == "uint32":
            return self.mem.read_uint32(address)
        if attr_type == "int32":
            return self.mem.read_int32(address)
        if attr_type == "uint64":
            return self.mem.read_uint64(address)
        if attr_type == "float":
            return self.mem.read_float(address)
        if attr_type == "bitfield":
            value = self.mem.read_bitfield(address, attr.bit_start, attr.bit_length)
            if value is None:
                return None
            if self._is_live_badge_attr(attr):
                return min(LIVE_BADGE_MAX_TIER, value)
            return value
        if attr_type == "wstring":
            return self.mem.read_wstring(address, attr.string_length)
        if attr_type == "ascii":
            return self.mem.read_ascii(address, attr.string_length)
        return None

    def read_attribute(self, player: Player, attr: AttributeDef) -> Optional[Any]:
        resolved_attr = attr
        if self._is_overall_attr(attr):
            resolved_attr = self._resolve_live_overall_attr(self._get_table_base_for_player(player)) or attr
        return self._read_attribute_direct(player, resolved_attr)

    def _write_attribute_direct(self, player: Player, attr: AttributeDef, value: Any) -> bool:
        address = player.record_address + attr.offset
        attr_type = attr.type
        effective_max = self._effective_attr_max(attr)

        if isinstance(value, (int, float)) and attr_type not in ("wstring", "ascii"):
            if attr_type == "float":
                value = max(float(attr.min_val), min(float(attr.max_val), float(value)))
            else:
                value = max(attr.min_val, min(effective_max, int(value)))

        if self._is_body_attr(attr):
            return self._write_body_attr(player, attr, value)

        if self._is_live_packed_rating_attr(attr):
            return self.mem.write_bitfield(address, 1, 7, int(value))

        if attr_type == "uint8":
            return self.mem.write_uint8(address, value)
        if attr_type == "int8":
            return self.mem.write_int8(address, value)
        if attr_type == "uint16":
            return self.mem.write_uint16(address, value)
        if attr_type == "int16":
            return self.mem.write_int16(address, value)
        if attr_type == "uint32":
            return self.mem.write_uint32(address, value)
        if attr_type == "int32":
            return self.mem.write_int32(address, value)
        if attr_type == "uint64":
            return self.mem.write_uint64(address, value)
        if attr_type == "float":
            return self.mem.write_float(address, value)
        if attr_type == "bitfield":
            return self.mem.write_bitfield(address, attr.bit_start, attr.bit_length, value)
        if attr_type == "wstring":
            return self.mem.write_wstring(address, str(value), attr.string_length)
        if attr_type == "ascii":
            encoded = str(value).encode("ascii", errors="replace")[: attr.string_length]
            padded = encoded.ljust(attr.string_length, b"\x00")
            return self.mem.write_bytes(address, padded)
        return False

    def write_attribute(self, player: Player, attr: AttributeDef, value: Any) -> bool:
        resolved_attr = attr
        if self._is_overall_attr(attr):
            resolved_attr = self._resolve_live_overall_attr(self._get_table_base_for_player(player)) or attr
        return self._write_attribute_direct(player, resolved_attr, value)

    def read_all_attributes(self, player: Player) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for attrs in self.config.attributes.values():
            for attr in attrs:
                result[attr.name] = self.read_attribute(player, attr)
        return result

    def write_all_attributes(self, player: Player, values: Dict[str, Any]) -> Dict[str, bool]:
        results: Dict[str, bool] = {}
        for name, value in values.items():
            attr = self.config.get_attribute(name)
            if attr is not None:
                results[name] = self.write_attribute(player, attr, value)
        return results

    def set_all_to_max(self, player: Player, categories: Optional[List[str]] = None) -> int:
        count = 0
        for category, attrs in self.config.attributes.items():
            if categories and category not in categories:
                continue
            for attr in attrs:
                if attr.type in ("wstring", "ascii"):
                    continue
                if self.write_attribute(player, attr, self._effective_attr_max(attr)):
                    count += 1
        return count

    def apply_god_mode(self, player: Player) -> int:
        count = 0
        overall_attr = self._get_overall_attr()
        if overall_attr is not None and self.write_attribute(
            player, overall_attr, self._effective_attr_max(overall_attr)
        ):
            count += 1

        ability_categories = ["进攻能力", "防守能力", "体能属性", "篮球智商"]
        for category in ability_categories:
            for attr in self.config.attributes.get(category, []):
                if attr.type in ("wstring", "ascii"):
                    continue
                if self.write_attribute(player, attr, self._effective_attr_max(attr)):
                    count += 1

        for category in self.config.categories():
            if "徽章" in category:
                for attr in self.config.attributes.get(category, []):
                    if self.write_attribute(player, attr, self._effective_attr_max(attr)):
                        count += 1

        for category in self.config.categories():
            if "倾向" in category or "风格" in category:
                for attr in self.config.attributes.get(category, []):
                    if self.write_attribute(player, attr, self._effective_attr_max(attr)):
                        count += 1

        for attr in self.config.attributes.get("耐久性", []):
            if self.write_attribute(player, attr, self._effective_attr_max(attr)):
                count += 1

        for attr in self.config.attributes.get("潜力与成长", []):
            if self.write_attribute(player, attr, self._effective_attr_max(attr)):
                count += 1

        return count
