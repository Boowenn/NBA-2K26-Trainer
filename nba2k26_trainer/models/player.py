"""Player scanning and attribute read/write helpers."""

from __future__ import annotations

import datetime
import struct
import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ..core.memory import GameMemory
from ..core.offsets import AttributeDef, OffsetConfig
from ..core.scanner import (
    enum_candidate_regions,
    scan_for_base_pointer,
    scan_for_player_table_candidates,
)


TEAM_PTR_OFFSET = 96
TEAM_PTR_OFFSET_CANDIDATES = (96, 104, 184, 208, 216)
MAX_VALID_POINTER = 0x7FFFFFFFFFFF
PLAYER_TABLE_SAMPLE_SIZE = 24
PLAYER_TABLE_POPULATION_SAMPLE_SIZE = 24
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
MIN_ACCEPTABLE_PLAYER_COUNT = 450
MAX_ACCEPTABLE_DUPLICATE_NAME_INSTANCES = 12
MAX_ACCEPTABLE_NAME_REPEAT = 3
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
MATCH_COMPACT_HANDLE_OFFSET = 0x60
MATCH_COMPACT_HANDLE_SIZE = 8
MATCH_COMPACT_REGION_MAX_SIZE = 0x400000
MATCH_COMPACT_MIN_TEAM_HITS = 3
MATCH_COMPACT_MAX_REGIONS = 12
MATCH_COMPACT_REGION_SCAN_CHUNK_SIZE = 0x40000
MATCH_COMPACT_MIRROR_BLOCKS: Tuple[Tuple[int, int, int], ...] = (
    (0x258, 0x000, 0x76),
    (0x2CF, 0x077, 0x116),
    (0x402, 0x1AA, 0x011),
    (0x41D, 0x1C5, 0x013),
    (0x432, 0x1DA, 0x024),
    (0x458, 0x200, 0x040),
)
MATCH_COMPACT_VALIDATION_SLICES: Tuple[Tuple[int, int, int], ...] = (
    (0x258, 0x000, 12),
    (0x2B8, MATCH_COMPACT_HANDLE_OFFSET, 16),
    (0x404, 0x1AC, 12),
)

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

CONTRACT_YEARS_LEFT_DESCRIPTION = "Contract Years Left"
CONTRACT_SALARY_DESCRIPTIONS = tuple(f"Year {index} Salary" for index in range(1, 7))

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

GOD_MODE_PROFILE_VALUES: Dict[str, int | str] = {
    "Avg Potential %": "max",
    "Boom % (positive growth)": "max",
    "Bust % (negative growth)": "min",
    "Min Potential": "max",
    "Max Potential": "max",
    "Peak Start Age": "min",
    "Peak End Age": "max",
    "Shot Under Basket": "max",
    "Shot Close": "max",
    "Shot Mid": "max",
    "Shot 3pt": "max",
    "Contested 3pt": 35,
    "Contested Mid": 40,
    "Stepback 3pt": 90,
    "Drive Pull Up 3pt": 90,
    "Drive Pull Up Mid": 92,
    "Transition Pull Up 3pt": 88,
    "Off Screen 3pt": 92,
    "Driving Layup Tendency": 99,
    "Standing Dunk Tendency": 95,
    "Driving Dunk Tendency": 99,
    "Flashy Dunk": 80,
    "Alley-Oop": 95,
    "Putback": 90,
    "Crash": 90,
    "Euro Step": 90,
    "Hop Step Layup": 90,
    "Floater": 88,
    "Spin Layup": 88,
    "Step Through Shot": 88,
    "Drive": 99,
    "Spot Up Drive": 90,
    "Drive Right": 50,
    "Off Screen Drive": 88,
    "Driving Hesitation": 85,
    "Behind The Back": 85,
    "Double Crossover": 85,
    "Half Spin": 80,
    "In And Out": 85,
    "Step Back": 90,
    "Attack Strong": 99,
    "Dish To Open Man": 82,
    "Flashy Pass": 45,
    "Alley Oop Pass": 75,
    "Block Shot": 95,
    "Contest Shot": 99,
    "Foul": "min",
    "Hard Foul": "min",
    "On Ball Steal": 92,
    "Pass Interception": 92,
    "Take Charge": "min",
    "Post Face Up": 90,
    "Post Back Down": 90,
    "Shoot From Post": 90,
    "Post Drive": 88,
    "Post Spin": 88,
    "Post Fade Left": 90,
    "Post Fade Right": 90,
    "Post Hook Left": 90,
    "Post Hook Right": 90,
    "Post Drop Step": 88,
    "Post Hop Shot": 88,
    "Post Hop Step": 85,
    "Post Step Back": 88,
    "Post Shimmy": 82,
    "Post Up And Under": 88,
    "Touches": "max",
    "Roll Vs Pop": 50,
    "Transition Spot Up": "max",
    "ISO vs Poor Defender": "max",
    "ISO vs Average Defender": "max",
    "ISO vs Good Defender": "max",
    "ISO vs Elite Defender": "max",
    "Play Discipline": "max",
}

PERFECT_SHOT_MATCH_PROFILE_VALUES: Dict[str, int] = {
    "Driving Layup": 99,
    "Float Game": 4,
    "Layup Mix Master": 4,
    "Paint Prodigy": 4,
    "Physical Finisher": 4,
    "Posterizer": 4,
    "Rise Up": 4,
    "Off Screen 3pt": 99,
    "Contested 3pt": 99,
    "Contested Mid": 99,
    "Stepback 3pt": 99,
    "Drive Pull Up 3pt": 99,
    "Drive Pull Up Mid": 99,
    "Transition Pull Up 3pt": 99,
    "Drive": 99,
    "Spot Up Drive": 99,
    "Attack Strong": 99,
    "Contest Shot": 99,
    "Deadeye": 4,
    "Limitless Range": 4,
    "Mini Marksman": 4,
    "Shifty Shooter": 4,
}
PERFECT_SHOT_ROSTER_PROFILE_VALUES: Dict[str, int] = {
    "Close Shot": 99,
    "Mid-Range Shot": 99,
    "Three-Point Shot": 99,
    "Free Throw": 99,
    "Driving Layup": 99,
    "Shot IQ": 99,
    "Offensive Consistency": 99,
    "Deadeye": 4,
    "Limitless Range": 4,
    "Mini Marksman": 4,
    "Shifty Shooter": 4,
    "Layup Mix Master": 4,
    "Shot Under Basket": 99,
    "Shot Close": 99,
    "Shot Mid": 99,
    "Shot 3pt": 99,
    "Contested 3pt": 99,
    "Contested Mid": 99,
    "Drive Pull Up Mid": 99,
    "Driving Layup Tendency": 99,
    "Contest Shot": 99,
}
PERFECT_SHOT_MATCH_REFRESH_INTERVAL = 25
# These runtime/legacy patch groups are shared across the live shot container.
# Keep them disabled until we can reliably scope them to the selected team.
PERFECT_SHOT_SHARED_RUNTIME_PATCHES_ENABLED = False
PERFECT_SHOT_SHARED_LEGACY_PATCHES_ENABLED = False

PERFECT_SHOT_MANAGER_SLOT_OFFSET = 0x789A170
PERFECT_SHOT_ENTRY_COUNT_OFFSET = 0x17F8
PERFECT_SHOT_ENTRY_ARRAY_OFFSET = 0x1800
PERFECT_SHOT_ENTRY_STRIDE = 0x1050
PERFECT_SHOT_ENABLE_OFFSET = 0x10
PERFECT_SHOT_LOCK_TIMER_OFFSET = 0x1C4
PERFECT_SHOT_LOCK_TIMER_ALT_OFFSET = 0x364
PERFECT_SHOT_FORCED_ENABLE_VALUE = 1
PERFECT_SHOT_FORCED_LOCK_VALUE = 0x7FFFFFFF
PERFECT_SHOT_MAX_ENTRY_COUNT = 8
PERFECT_SHOT_LEGACY_STATE_PATCHES: Tuple[Tuple[int, bytes], ...] = (
    (0x452, b"\x01\x01"),
    (0xBF2, b"\x01\x01"),
)
SHOT_RUNTIME_GLOBAL_PTR_SLOT = 0x14683DE68
SHOT_RUNTIME_CONTAINER_OFFSET = 0xA8
SHOT_RUNTIME_ENTRY_COUNT_OFFSET = 0x4B0
SHOT_RUNTIME_ENTRY_BASE_OFFSET = 0x4B8
SHOT_RUNTIME_ENTRY_STRIDE = 0xC1B8
SHOT_RUNTIME_MAX_ENTRY_COUNT = 4
SHOT_RUNTIME_AI_TEAM_DELTA_OFFSET = 0x1570
SHOT_RUNTIME_AI_HUMAN_DELTA_OFFSET = 0x1590
SHOT_RUNTIME_COVERAGE_DELTA_OFFSET = 0x15B0
SHOT_RUNTIME_IMPACT_DELTA_OFFSET = 0x23C0
SHOT_RUNTIME_TIMING_DELTA_SIZE = 0x20
SHOT_RUNTIME_AI_HUMAN_DELTA_SIZE = SHOT_RUNTIME_TIMING_DELTA_SIZE


def _pack_u16_pair(first: int, second: int) -> bytes:
    return struct.pack("<HH", first & 0xFFFF, second & 0xFFFF)


SHOT_RUNTIME_PERFECT_PATCHES: Tuple[Tuple[str, int, bytes], ...] = (
    ("ai_team_delta", SHOT_RUNTIME_AI_TEAM_DELTA_OFFSET, bytes(SHOT_RUNTIME_TIMING_DELTA_SIZE)),
    ("human_team_delta", SHOT_RUNTIME_AI_HUMAN_DELTA_OFFSET, bytes(SHOT_RUNTIME_TIMING_DELTA_SIZE)),
    ("coverage_delta", SHOT_RUNTIME_COVERAGE_DELTA_OFFSET, bytes(SHOT_RUNTIME_TIMING_DELTA_SIZE)),
    ("impact_delta", SHOT_RUNTIME_IMPACT_DELTA_OFFSET, bytes(SHOT_RUNTIME_TIMING_DELTA_SIZE)),
    ("three_point_height_mod", 0x15EC, bytes(4)),
    ("shot_chance_penalty_after_fake", 0x15F4, bytes(4)),
    ("very_easy_shot_threshold", 0x15FC, bytes(4)),
    ("min_chance_excellent", 0x15D4, bytes(4)),
    ("max_defense_excellent_shots", 0x15DC, _pack_u16_pair(10000, 10000)),
    ("max_defense_excellent_layups", 0x15E4, _pack_u16_pair(10000, 10000)),
    ("timing_variability_high_defense", 0x1604, bytes(4)),
    ("timing_variability_great_shooter", 0x160C, bytes(4)),
    ("timing_variability_good_shooter", 0x1614, bytes(4)),
    ("timing_variability_bad_shooter", 0x161C, bytes(4)),
    ("ai_timing_variance_standard", 0x1624, bytes(4)),
    ("ai_timing_variance_reduced", 0x162C, bytes(4)),
    ("max_timing_error_pct_for_forced_make", 0x16FC, _pack_u16_pair(10000, 10000)),
    ("min_timing_error_pct_for_forced_miss", 0x1704, _pack_u16_pair(10000, 10000)),
    ("forced_shot_result_max_variance", 0x170C, bytes(4)),
    ("min_shot_chance_for_forced_make", 0x1714, bytes(4)),
    ("max_shot_chance_for_forced_miss", 0x171C, bytes(4)),
)
SHOT_RUNTIME_TEAM_BLOCK_OFFSET = 0x110
SHOT_RUNTIME_TEAM_BLOCK_SIZE = 0x7A0
SHOT_RUNTIME_TEAM_LINK_MAX_OBJECTS = 220
SHOT_RUNTIME_TEAM_LINK_START_RELS: Tuple[int, ...] = (
    0x00,
    0x08,
    0x10,
    0x20,
    0x28,
    0x30,
    0x40,
    0x48,
    0x50,
    0x58,
    0x60,
    0x68,
    0x70,
    0x78,
    0x80,
    0x88,
    0x98,
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
    estimated_player_count: int = 0
    duplicate_name_instances: int = 0
    duplicate_name_count: int = 0
    max_name_repeat: int = 0
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

    latin_letters = 0
    weird = 0
    for char in text:
        code = ord(char)
        if code < 32 or code == 0xFFFD:
            return False
        if char.isalpha():
            if "LATIN" not in unicodedata.name(char, ""):
                return False
            latin_letters += 1
            continue
        if char.isdigit() or char in " .'-&":
            continue
        weird += 1

    if latin_letters < 2:
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
        self._match_compact_region_cache: Dict[int, List[Tuple[int, int, int, int]]] = {}
        self._match_compact_entry_cache: Dict[int, List[int]] = {}
        self._perfect_shot_match_attr_cache: Optional[List[Tuple[AttributeDef, int]]] = None
        self._perfect_shot_roster_attr_cache: Optional[List[Tuple[AttributeDef, int]]] = None
        self._perfect_shot_beta_state: Optional[Dict[str, Any]] = None
        self._shot_runtime_team_block_cache: Dict[Tuple[int, int], Optional[int]] = {}
        self._rejected_table_bases: set[int] = set()

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
        self._match_compact_region_cache.clear()
        self._match_compact_entry_cache.clear()
        self._shot_runtime_team_block_cache.clear()

    def begin_refresh(self, *, force_rescan: bool = False) -> None:
        if force_rescan:
            self._table_base = None
            self._team_table_base = None
            self._team_ptr_offset_cache.clear()
            self._live_team_ptr_offset_cache.clear()
            self._live_overall_attr_cache.clear()
            self._module_ref_count_cache.clear()
            self._match_compact_region_cache.clear()
            self._match_compact_entry_cache.clear()
            self._shot_runtime_team_block_cache.clear()
            self._rejected_table_bases.clear()

    def _discard_table_base(self, table_base: Optional[int]) -> None:
        if table_base is None:
            return
        self._rejected_table_bases.add(table_base)
        self._team_ptr_offset_cache.pop(table_base, None)
        self._live_team_ptr_offset_cache.pop(table_base, None)
        self._live_overall_attr_cache.pop(table_base, None)
        self._module_ref_count_cache.pop(table_base, None)
        self._match_compact_region_cache.clear()
        self._match_compact_entry_cache.clear()
        self._shot_runtime_team_block_cache.clear()

    def _is_cached_table_base_valid(self, table_base: int) -> bool:
        if table_base in self._rejected_table_bases:
            return False
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

    def _get_contract_years_left_attr(self) -> Optional[AttributeDef]:
        return self.config.find_attribute_by_description(CONTRACT_YEARS_LEFT_DESCRIPTION)

    def _is_overall_attr(self, attr: Optional[AttributeDef]) -> bool:
        return bool(attr) and attr.description.strip().lower() == "overall rating"

    def _is_contract_salary_attr(self, attr: Optional[AttributeDef]) -> bool:
        if not attr:
            return False
        return (attr.description or "").strip() in CONTRACT_SALARY_DESCRIPTIONS

    def _is_contract_years_left_attr(self, attr: Optional[AttributeDef]) -> bool:
        if not attr:
            return False
        return (attr.description or "").strip() == CONTRACT_YEARS_LEFT_DESCRIPTION

    def _get_table_base_for_player(self, player: Player) -> Optional[int]:
        if self._table_base is not None:
            return self._table_base
        if player.index < 0:
            return None
        return player.record_address - player.index * self.config.player_table.stride

    def _map_match_compact_offset(self, record_offset: int) -> Optional[int]:
        for record_start, entry_start, size in MATCH_COMPACT_MIRROR_BLOCKS:
            if record_start <= record_offset < record_start + size:
                return entry_start + (record_offset - record_start)
        return None

    def _get_match_compact_handle(self, player: Player) -> bytes:
        handle = self.mem.read_bytes(player.record_address + 0x2B8, MATCH_COMPACT_HANDLE_SIZE) or b""
        if len(handle) != MATCH_COMPACT_HANDLE_SIZE or handle == b"\x00" * MATCH_COMPACT_HANDLE_SIZE:
            return b""
        return handle

    def _scan_match_compact_region_hits(
        self,
        base: int,
        size: int,
        patterns: List[bytes],
        *,
        max_hits: Optional[int] = None,
    ) -> int:
        if size <= 0:
            return 0

        found: set[bytes] = set()
        overlap = max(0, MATCH_COMPACT_HANDLE_SIZE - 1)

        for chunk_offset in range(0, size, MATCH_COMPACT_REGION_SCAN_CHUNK_SIZE):
            read_size = min(MATCH_COMPACT_REGION_SCAN_CHUNK_SIZE + overlap, size - chunk_offset)
            data = self.mem.read_bytes(base + chunk_offset, read_size) or b""
            if not data:
                continue

            for pattern in patterns:
                if pattern in found:
                    continue
                if data.find(pattern) != -1:
                    found.add(pattern)
                    if max_hits is not None and len(found) >= max_hits:
                        return len(found)

        return len(found)

    def _find_match_compact_regions_for_handle(
        self,
        handle: bytes,
        *,
        max_regions: int = 4,
    ) -> List[Tuple[int, int, int, int]]:
        if not handle:
            return []

        regions: List[Tuple[int, int, int, int]] = []
        for base, size, protect, mem_type in enum_candidate_regions(
            self.mem.handle,
            private_only=True,
            writable_only=True,
        ):
            if size > MATCH_COMPACT_REGION_MAX_SIZE:
                continue
            hits = self._scan_match_compact_region_hits(
                base,
                size,
                [handle],
                max_hits=1,
            )
            if hits <= 0:
                continue
            regions.append((base, size, protect, mem_type))
            if len(regions) >= max_regions:
                break
        return regions

    def _discover_match_compact_regions(self, player: Player) -> List[Tuple[int, int, int, int]]:
        team_key = player.team_id
        cached = self._match_compact_region_cache.get(team_key)
        if cached is not None:
            return cached

        player_handle = self._get_match_compact_handle(player)
        regions = self._find_match_compact_regions_for_handle(
            player_handle,
            max_regions=min(MATCH_COMPACT_MAX_REGIONS, 4),
        )
        self._match_compact_region_cache[team_key] = regions
        return regions

    def _is_valid_match_compact_entry(self, player: Player, entry_base: int) -> bool:
        if entry_base <= 0x10000:
            return False

        handle = self._get_match_compact_handle(player)
        if not handle:
            return False

        entry_handle = self.mem.read_bytes(entry_base + MATCH_COMPACT_HANDLE_OFFSET, len(handle))
        if not entry_handle or entry_handle != handle:
            return False

        return True

    def _get_match_compact_entry_bases(self, player: Player) -> List[int]:
        cached = self._match_compact_entry_cache.get(player.record_address)
        if cached is not None:
            return cached

        handle = self._get_match_compact_handle(player)
        if not handle:
            self._match_compact_entry_cache[player.record_address] = []
            return []

        def _append_from_regions(regions: List[Tuple[int, int, int, int]], entries: List[int]) -> None:
            for region_base, region_size, _, _ in regions:
                data = self.mem.read_bytes(region_base, region_size)
                if not data:
                    continue

                start = 0
                while True:
                    index = data.find(handle, start)
                    if index == -1:
                        break
                    start = index + 1

                    if index < MATCH_COMPACT_HANDLE_OFFSET:
                        continue
                    entry_base = region_base + index - MATCH_COMPACT_HANDLE_OFFSET
                    if entry_base < region_base or entry_base + MATCH_COMPACT_HANDLE_OFFSET + len(handle) > region_base + region_size:
                        continue
                    if entry_base in entries:
                        continue
                    if self._is_valid_match_compact_entry(player, entry_base):
                        entries.append(entry_base)

        entry_bases: List[int] = []
        regions = list(self._discover_match_compact_regions(player))
        _append_from_regions(regions, entry_bases)

        if not entry_bases:
            fallback_regions = self._find_match_compact_regions_for_handle(
                handle,
                max_regions=min(MATCH_COMPACT_MAX_REGIONS, 4),
            )
            if fallback_regions:
                team_regions = self._match_compact_region_cache.setdefault(player.team_id, [])
                existing_bases = {base for base, _, _, _ in team_regions}
                for region in fallback_regions:
                    if region[0] not in existing_bases:
                        team_regions.append(region)
                        existing_bases.add(region[0])
                _append_from_regions(fallback_regions, entry_bases)

        self._match_compact_entry_cache[player.record_address] = entry_bases
        return entry_bases

    def get_match_compact_entry_bases(self, player: Player) -> List[int]:
        return list(self._get_match_compact_entry_bases(player))

    def _read_value_at(self, record_address: int, attr: Optional[AttributeDef]) -> Optional[Any]:
        if attr is None:
            return None
        player = Player(index=-1, record_address=record_address)
        return self._read_attribute_direct(player, attr)

    def _summarize_duplicate_player_names(self, players: List[Player]) -> Tuple[int, int, int]:
        counts: Counter[str] = Counter()
        for player in players:
            first_name = _normalize_text(player.first_name)
            last_name = _normalize_text(player.last_name)
            if not _is_valid_name(first_name) or not _is_valid_name(last_name):
                continue
            counts[f"{first_name} {last_name}"] += 1

        duplicate_instances = sum(count - 1 for count in counts.values() if count > 1)
        duplicate_names = sum(1 for count in counts.values() if count > 1)
        max_repeat = max(counts.values(), default=0)
        return duplicate_instances, duplicate_names, max_repeat

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

    def _resolve_god_mode_value(self, attr: AttributeDef) -> Optional[int]:
        if attr.type in ("wstring", "ascii"):
            return None

        if self._is_overall_attr(attr) or self._is_live_packed_rating_attr(attr):
            return self._effective_attr_max(attr)

        if self._is_live_badge_attr(attr):
            return self._effective_attr_max(attr)

        if attr.type == "uint8" and 1028 <= attr.offset <= 1043:
            return self._effective_attr_max(attr)

        description = (attr.description or attr.name or "").strip()
        if not description:
            return None

        if "Hot Zone" in description:
            return self._effective_attr_max(attr)

        profile_value = GOD_MODE_PROFILE_VALUES.get(description)
        if profile_value is None:
            return None

        if profile_value == "max":
            return self._effective_attr_max(attr)
        if profile_value == "min":
            return attr.min_val

        return max(attr.min_val, min(self._effective_attr_max(attr), int(profile_value)))

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

    def _read_blob_slice(self, blob: Optional[bytes], offset: int, size: int) -> Optional[bytes]:
        if not blob or offset < 0 or size < 0:
            return None
        end = offset + size
        if end > len(blob):
            return None
        return blob[offset:end]

    def _read_wstring_from_blob(self, blob: Optional[bytes], offset: int, max_len: int) -> Optional[str]:
        data = self._read_blob_slice(blob, offset, max_len * 2)
        if not data:
            return None
        for index in range(0, len(data) - 1, 2):
            if data[index] == 0 and data[index + 1] == 0:
                data = data[:index]
                break
        return data.decode("utf-16-le", errors="replace")

    def _read_ascii_from_blob(self, blob: Optional[bytes], offset: int, max_len: int) -> Optional[str]:
        data = self._read_blob_slice(blob, offset, max_len)
        if not data:
            return None
        try:
            data = data[: data.index(0)]
        except ValueError:
            pass
        return data.decode("ascii", errors="replace")

    def _read_bitfield_from_blob(
        self,
        blob: Optional[bytes],
        offset: int,
        bit_start: int,
        bit_length: int,
    ) -> Optional[int]:
        byte_offset = bit_start // 8
        total_bits = bit_start % 8 + bit_length
        total_bytes = (total_bits + 7) // 8
        data = self._read_blob_slice(blob, offset + byte_offset, total_bytes)
        if not data:
            return None
        value = int.from_bytes(data, byteorder="little")
        shift = bit_start % 8
        mask = (1 << bit_length) - 1
        return (value >> shift) & mask

    def _read_attribute_value_from_blob(self, blob: Optional[bytes], attr: AttributeDef) -> Optional[Any]:
        if blob is None:
            return None

        if self._is_live_packed_rating_attr(attr):
            value = self._read_bitfield_from_blob(blob, attr.offset, 1, 7)
            if value is None:
                return None
            return min(self._effective_attr_max(attr), value)

        attr_type = attr.type
        if attr_type == "uint8":
            data = self._read_blob_slice(blob, attr.offset, 1)
            return data[0] if data else None
        if attr_type == "int8":
            data = self._read_blob_slice(blob, attr.offset, 1)
            return int.from_bytes(data, byteorder="little", signed=True) if data else None
        if attr_type == "uint16":
            data = self._read_blob_slice(blob, attr.offset, 2)
            return int.from_bytes(data, byteorder="little") if data else None
        if attr_type == "int16":
            data = self._read_blob_slice(blob, attr.offset, 2)
            return int.from_bytes(data, byteorder="little", signed=True) if data else None
        if attr_type == "uint32":
            data = self._read_blob_slice(blob, attr.offset, 4)
            return int.from_bytes(data, byteorder="little") if data else None
        if attr_type == "int32":
            data = self._read_blob_slice(blob, attr.offset, 4)
            return int.from_bytes(data, byteorder="little", signed=True) if data else None
        if attr_type == "uint64":
            data = self._read_blob_slice(blob, attr.offset, 8)
            return int.from_bytes(data, byteorder="little") if data else None
        if attr_type == "float":
            data = self._read_blob_slice(blob, attr.offset, 4)
            return struct.unpack("<f", data)[0] if data and len(data) == 4 else None
        if attr_type == "bitfield":
            value = self._read_bitfield_from_blob(blob, attr.offset, attr.bit_start, attr.bit_length)
            if value is None:
                return None
            if self._is_live_badge_attr(attr):
                return min(LIVE_BADGE_MAX_TIER, value)
            return value
        if attr_type == "wstring":
            return self._read_wstring_from_blob(blob, attr.offset, attr.string_length)
        if attr_type == "ascii":
            return self._read_ascii_from_blob(blob, attr.offset, attr.string_length)
        return None

    def _read_body_attr_from_blobs(
        self,
        player: Player,
        attr: AttributeDef,
        record_blob: Optional[bytes],
        body_blob: Optional[bytes],
    ) -> Optional[Any]:
        description = attr.description
        if description == "Weight (kg)":
            data = self._read_blob_slice(record_blob, attr.offset, 4)
            if not data or len(data) != 4:
                return None
            pounds = struct.unpack("<f", data)[0]
            return round(float(pounds) / POUNDS_PER_KG, 2)

        if body_blob is None:
            return None

        if description == "Height in cm":
            data = self._read_blob_slice(body_blob, BODY_HEIGHT_INCHES_OFFSET, 1)
            return int(round(float(data[0]) * 2.54)) if data else None

        if description == "Wingspan in cm":
            data = self._read_blob_slice(body_blob, BODY_WINGSPAN_INCHES_OFFSET, 1)
            return int(round(float(data[0]) * 2.54)) if data else None

        scale_offsets = {
            "Trunk Length": BODY_TRUNK_SCALE_OFFSET,
            "Shoulder Width": BODY_SHOULDER_SCALE_OFFSET,
            "Arm Scale": BODY_ARM_SCALE_OFFSET,
            "Neck Length": BODY_NECK_SCALE_OFFSET,
        }
        scale_offset = scale_offsets.get(description)
        if scale_offset is None:
            return None

        data = self._read_blob_slice(body_blob, scale_offset, 4)
        if not data or len(data) != 4:
            return None
        return round(struct.unpack("<f", data)[0] * 100.0, 2)

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
            if base in self._rejected_table_bases:
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

    def _count_roster_player_hits(self, players: List[Player]) -> Tuple[int, int]:
        legend_hits = 0
        modern_hits = 0

        for player in players[:ROSTER_HINT_SAMPLE_SIZE]:
            full_name = (_normalize_text(player.first_name), _normalize_text(player.last_name))
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

        sparse_valid = 0
        sparse_total = 0
        sparse_step = max(1, pt.max_players // max(1, PLAYER_TABLE_POPULATION_SAMPLE_SIZE))
        for index in range(0, pt.max_players, sparse_step):
            record_address = table_base + index * pt.stride
            last_name = _normalize_text(
                self.mem.read_wstring(record_address + pt.last_name_offset, pt.name_string_length)
            )
            first_name = _normalize_text(
                self.mem.read_wstring(record_address + pt.first_name_offset, pt.name_string_length)
            )
            if _is_valid_name(first_name) or _is_valid_name(last_name):
                sparse_valid += 1
            sparse_total += 1
            if sparse_total >= PLAYER_TABLE_POPULATION_SAMPLE_SIZE:
                break
        if sparse_total > 0:
            metrics.estimated_player_count = int(round(pt.max_players * (sparse_valid / sparse_total)))

        sample_name_counts: Counter[str] = Counter()
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
                if _is_valid_name(first_name) and _is_valid_name(last_name):
                    sample_name_counts[f"{first_name} {last_name}"] += 1

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

        metrics.duplicate_name_instances = sum(
            count - 1 for count in sample_name_counts.values() if count > 1
        )
        metrics.duplicate_name_count = sum(
            1 for count in sample_name_counts.values() if count > 1
        )
        metrics.max_name_repeat = max(sample_name_counts.values(), default=0)

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
            + min(160, metrics.estimated_player_count // 4)
        )
        if metrics.estimated_player_count < MIN_ACCEPTABLE_PLAYER_COUNT:
            metrics.selection_score -= (MIN_ACCEPTABLE_PLAYER_COUNT - metrics.estimated_player_count)
        if metrics.legend_hits >= 2 and metrics.modern_hits >= 2:
            metrics.selection_score -= metrics.duplicate_name_instances * 40
            metrics.selection_score -= max(0, metrics.max_name_repeat - 1) * 30
        return metrics

    def _is_promising_player_table(self, metrics: TableMetrics) -> bool:
        if metrics.non_empty == 0:
            return False

        required_names = min(4, metrics.non_empty)
        required_birth_year = min(2, metrics.non_empty)
        required_team_refs = min(2, metrics.non_empty)

        # Names remain the strongest signal, but we require at least one
        # structural roster clue as well. This filters out the in-match
        # entity tables that still carry readable names and a few packed
        # ratings but no usable birth years or team assignments.
        has_structural_signal = (
            metrics.valid_birth_year >= required_birth_year
            or metrics.valid_team_refs >= required_team_refs
        )
        duplicate_heavy_sample = (
            metrics.duplicate_name_instances >= 4
            or metrics.max_name_repeat >= 3
        )
        mixed_era_duplicate_sample = duplicate_heavy_sample and metrics.legend_hits >= 2 and metrics.modern_hits >= 2

        return (
            metrics.valid_names >= required_names
            and has_structural_signal
            and metrics.score >= 18
            and not mixed_era_duplicate_sample
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
        currentish_candidates = [
            entry
            for entry in promising
            if entry[2].modern_hits >= 4 and entry[2].modern_hits > entry[2].legend_hits
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

        ordered_candidates: List[Tuple[int, str, TableMetrics]]
        if self.roster_mode == "legend" and legend_candidates:
            ordered_candidates = sorted(legend_candidates, key=candidate_rank, reverse=True)
        elif self.roster_mode == "current" and modern_candidates:
            ordered_candidates = sorted(modern_candidates, key=candidate_rank, reverse=True)
        elif self.roster_mode == "auto" and active_candidates:
            ordered_candidates = sorted(active_candidates, key=candidate_rank, reverse=True)
        elif self.roster_mode == "auto" and currentish_candidates:
            ordered_candidates = sorted(
                currentish_candidates,
                key=lambda entry: (
                    candidate_rank(entry),
                    entry[2].modern_hits - entry[2].legend_hits,
                    entry[2].modern_hits,
                ),
                reverse=True,
            )
        elif self.roster_mode == "auto" and legend_candidates and modern_candidates:
            best_legend = max(legend_candidates, key=candidate_rank)
            best_modern = max(modern_candidates, key=candidate_rank)
            if (
                best_legend[2].team_ptr_quality >= best_modern[2].team_ptr_quality + 70
                and best_legend[2].legend_hits >= best_modern[2].modern_hits + 8
            ):
                remaining = [entry for entry in promising if entry[0] != best_legend[0]]
                ordered_candidates = [best_legend]
                ordered_candidates.extend(sorted(remaining, key=candidate_rank, reverse=True))
            else:
                ordered_candidates = sorted(promising, key=candidate_rank, reverse=True)
        else:
            ordered_candidates = sorted(promising, key=candidate_rank, reverse=True)

        for base, source, metrics in ordered_candidates:
            final_metrics = self._score_player_table_base(base, include_module_refs=False)
            if not self._is_promising_player_table(final_metrics):
                if progress_callback:
                    progress_callback(
                        f"Skipping unstable player table {source}: 0x{base:X} "
                        f"(names={final_metrics.valid_names}, birth={final_metrics.valid_birth_year}, "
                        f"teams={final_metrics.valid_team_refs}, score={final_metrics.score})"
                    )
                continue
            if not self._matches_requested_roster_mode(final_metrics):
                continue
            if progress_callback:
                progress_callback(
                    f"Using player table from {source}: 0x{base:X} "
                    f"(team_off=0x{metrics.team_ptr_offset:X}, "
                    f"module_refs={metrics.module_ref_count}, mode={self.roster_mode})"
                )
            return base
        return None

    def _build_roster_signature(self, table_base: int) -> Tuple[int, int, Tuple[str, ...]]:
        pt = self.config.player_table
        overall_attr = self._resolve_live_overall_attr(table_base)
        team_table_base = self._resolve_team_table_base()
        team_ptr_offset, _ = self._resolve_live_team_ptr_offset(table_base, team_table_base)

        sample_slots = 12
        step = max(1, pt.max_players // sample_slots)
        sample_indices: List[int] = []
        for index in range(0, pt.max_players, step):
            sample_indices.append(index)
            if len(sample_indices) >= sample_slots:
                break
        tail_index = max(0, pt.max_players - 1)
        if tail_index not in sample_indices:
            sample_indices.append(tail_index)

        signature_parts: List[str] = []
        for index in sample_indices:
            record_address = table_base + index * pt.stride
            first_name = _normalize_text(
                self.mem.read_wstring(record_address + pt.first_name_offset, pt.name_string_length)
            )
            last_name = _normalize_text(
                self.mem.read_wstring(record_address + pt.last_name_offset, pt.name_string_length)
            )
            overall = self._read_value_at(record_address, overall_attr)
            team_ptr = int(self.mem.read_uint64(record_address + team_ptr_offset) or 0)
            signature_parts.append(
                f"{index}:{first_name}|{last_name}|{overall if isinstance(overall, int) else -1}|{team_ptr & 0xFFFFFFFF:X}"
            )

        return (table_base, team_ptr_offset, tuple(signature_parts))

    def get_live_roster_signature(self, *, force_refresh: bool = False) -> Optional[Tuple[int, int, Tuple[str, ...]]]:
        table_base = self._resolve_table_base(use_cached=not force_refresh)
        if table_base is None:
            return None
        return self._build_roster_signature(table_base)

    def _resolve_table_base(self, progress_callback=None, *, use_cached: bool = True) -> Optional[int]:
        cached_base = self._table_base
        if use_cached and cached_base is not None:
            if self._is_cached_table_base_valid(cached_base):
                if progress_callback:
                    progress_callback(f"Using cached player table: 0x{cached_base:X}")
                return cached_base
            self._table_base = None

        pt = self.config.player_table
        candidates = self._get_config_player_table_candidates()
        fallback_config_base: Optional[int] = None

        best_base = self._pick_best_player_table(
            candidates,
            progress_callback,
            include_module_refs=True,
        )
        if best_base is not None:
            best_metrics = self._score_player_table_base(
                best_base,
                include_module_refs=True,
            )
            weak_config_snapshot = (
                self.roster_mode in {"auto", "current"}
                and best_metrics.module_ref_count < CACHED_TABLE_MIN_MODULE_REFS
                and best_metrics.estimated_player_count < MIN_ACCEPTABLE_PLAYER_COUNT
            )
            if self._matches_requested_roster_mode(best_metrics) and not weak_config_snapshot:
                self._table_base = best_base
                return best_base
            fallback_config_base = best_base
            if progress_callback:
                if weak_config_snapshot:
                    progress_callback(
                        "Configured pointer resolved to a weak in-match roster snapshot "
                        f"(module_refs={best_metrics.module_ref_count}). "
                        "Scanning memory for a stronger active save roster..."
                    )
                else:
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
            if fallback_config_base is not None:
                self._table_base = fallback_config_base
                return fallback_config_base
            return None

        scan_candidates: List[Tuple[int, str]] = []
        for scanned_base, valid_count in scanned_candidates:
            scan_candidates.append((scanned_base, f"memory scan ({valid_count} names)"))
            nested = self.mem.read_uint64(scanned_base)
            if _is_pointer_like(nested):
                scan_candidates.append((int(nested), f"memory scan ({valid_count} names) -> deref"))

        best_base = self._pick_best_player_table(
            scan_candidates,
            progress_callback,
            include_module_refs=True,
        )
        if best_base is None:
            if fallback_config_base is not None:
                self._table_base = fallback_config_base
                return fallback_config_base
            if cached_base is not None and self._is_cached_table_base_valid(cached_base):
                self._table_base = cached_base
                return cached_base
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

    def _collect_players_from_table(
        self,
        table_base: int,
        team_table_base: Optional[int],
    ) -> List[Player]:
        team_ptr_offset, _ = self._resolve_live_team_ptr_offset(table_base, team_table_base)
        player_table = self.config.player_table
        players: List[Player] = []
        team_cache: Dict[int, Tuple[str, int]] = {}
        next_dynamic_team_id = 1000
        overall_attr = self._resolve_live_overall_attr(table_base)
        birth_year_attr = self._get_birth_year_attr()
        table_blob = self.mem.read_bytes(table_base, player_table.max_players * player_table.stride)

        for index in range(player_table.max_players):
            record_address = table_base + index * player_table.stride
            record_blob = None
            if table_blob:
                start = index * player_table.stride
                end = start + player_table.stride
                if end <= len(table_blob):
                    record_blob = table_blob[start:end]
            last_name = _normalize_text(
                self._read_wstring_from_blob(record_blob, player_table.last_name_offset, player_table.name_string_length)
                if record_blob is not None
                else self.mem.read_wstring(record_address + player_table.last_name_offset, player_table.name_string_length)
            )
            first_name = _normalize_text(
                self._read_wstring_from_blob(record_blob, player_table.first_name_offset, player_table.name_string_length)
                if record_blob is not None
                else self.mem.read_wstring(record_address + player_table.first_name_offset, player_table.name_string_length)
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

            team_ptr_bytes = self._read_blob_slice(record_blob, team_ptr_offset, 8) if record_blob is not None else None
            team_ptr = (
                int.from_bytes(team_ptr_bytes, byteorder="little")
                if team_ptr_bytes and len(team_ptr_bytes) == 8
                else self.mem.read_uint64(record_address + team_ptr_offset)
            )
            (player.team_name, player.team_id), next_dynamic_team_id = self._resolve_team_info(
                team_ptr,
                team_table_base,
                team_cache,
                next_dynamic_team_id,
            )

            overall = (
                self._read_attribute_value_from_blob(record_blob, overall_attr)
                if record_blob is not None and overall_attr is not None
                else self._read_value_at(record_address, overall_attr)
            )
            if isinstance(overall, int) and 0 <= overall <= 99:
                player.overall = overall

            birth_year = (
                self._read_attribute_value_from_blob(record_blob, birth_year_attr)
                if record_blob is not None and birth_year_attr is not None
                else self._read_value_at(record_address, birth_year_attr)
            )
            if isinstance(birth_year, int) and 1950 <= birth_year <= datetime.datetime.now().year:
                player.birth_year = birth_year
                player.age = birth_year_to_age(birth_year)

            players.append(player)

        return players

    def scan_players(self, progress_callback=None) -> List[Player]:
        for attempt in range(2):
            self._table_base = self._resolve_table_base(progress_callback)
            if self._table_base is None:
                self.players = []
                return []

            team_table_base = self._resolve_team_table_base(progress_callback)
            players = self._collect_players_from_table(self._table_base, team_table_base)
            duplicate_instances, duplicate_names, max_repeat = self._summarize_duplicate_player_names(players)
            legend_hits, modern_hits = self._count_roster_player_hits(players)
            duplicate_snapshot = (
                (
                    duplicate_instances >= MAX_ACCEPTABLE_DUPLICATE_NAME_INSTANCES
                    or max_repeat > MAX_ACCEPTABLE_NAME_REPEAT
                )
                and legend_hits >= 2
                and modern_hits >= 2
            )

            if len(players) >= MIN_ACCEPTABLE_PLAYER_COUNT and not duplicate_snapshot:
                self.players = players
                return players

            if duplicate_snapshot and attempt == 1:
                self.players = []
                return []

            bad_base = self._table_base
            if progress_callback:
                if duplicate_snapshot:
                    progress_callback(
                        f"Selected player table 0x{bad_base:X} looks like a duplicate-heavy snapshot "
                        f"({duplicate_names} repeated names, max repeat {max_repeat}). "
                        "Retrying with a fresh scan..."
                    )
                else:
                    progress_callback(
                        f"Selected player table 0x{bad_base:X} produced only {len(players)} players. "
                        "Retrying with a fresh scan..."
                    )
            self._discard_table_base(bad_base)
            self._table_base = None

        self.players = players
        return players

    def _read_attribute_direct(self, player: Player, attr: AttributeDef) -> Optional[Any]:
        address = player.record_address + attr.offset

        if self._is_body_attr(attr):
            return self._read_body_attr(player, attr)

        return self._read_attribute_value_at(address, attr)

    def _read_attribute_value_at(self, address: int, attr: AttributeDef) -> Optional[Any]:
        attr_type = attr.type

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

    def read_match_compact_attribute_values(self, player: Player, attr: AttributeDef) -> List[Any]:
        if self._is_body_attr(attr) or attr.type in ("wstring", "ascii"):
            return []

        mapped_offset = self._map_match_compact_offset(attr.offset)
        if mapped_offset is None:
            return []

        values: List[Any] = []
        for entry_base in self._get_match_compact_entry_bases(player):
            value = self._read_attribute_value_at(entry_base + mapped_offset, attr)
            if value is not None:
                values.append(value)
        return values

    def summarize_live_gameplay_state(self, player: Player) -> Dict[str, Any]:
        watch_list = (
            "Three-Point Shot",
            "Mid-Range Shot",
            "Close Shot",
            "Driving Layup",
            "Stamina",
            "Deadeye",
            "Spot Up Drive",
            "Contest Shot",
        )
        entry_bases = self._get_match_compact_entry_bases(player)
        summary: Dict[str, Any] = {
            "match_compact_entries": len(entry_bases),
            "match_compact_bases": [hex(base) for base in entry_bases],
            "attributes": {},
        }

        for description in watch_list:
            attr = self.config.find_attribute_by_description(description)
            if attr is None:
                continue
            summary["attributes"][description] = {
                "current": self.read_attribute(player, attr),
                "match_copies": self.read_match_compact_attribute_values(player, attr),
            }

        return summary

    def _coerce_attribute_value(self, attr: AttributeDef, value: Any) -> Any:
        attr_type = attr.type
        effective_max = self._effective_attr_max(attr)

        if isinstance(value, (int, float)) and attr_type not in ("wstring", "ascii"):
            if attr_type == "float":
                return max(float(attr.min_val), min(float(attr.max_val), float(value)))
            return max(attr.min_val, min(effective_max, int(value)))

        return value

    def _write_attribute_value_at(self, address: int, attr: AttributeDef, value: Any) -> bool:
        attr_type = attr.type

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

    def _write_match_compact_attribute(self, player: Player, attr: AttributeDef, value: Any) -> int:
        if self._is_body_attr(attr) or attr.type in ("wstring", "ascii"):
            return 0

        mapped_offset = self._map_match_compact_offset(attr.offset)
        if mapped_offset is None:
            return 0

        writes = 0
        for entry_base in self._get_match_compact_entry_bases(player):
            address = entry_base + mapped_offset
            if self._write_attribute_value_at(address, attr, value):
                writes += 1

        return writes

    def _get_perfect_shot_match_attrs(self) -> List[Tuple[AttributeDef, int]]:
        if self._perfect_shot_match_attr_cache is not None:
            return self._perfect_shot_match_attr_cache

        attrs: List[Tuple[AttributeDef, int]] = []
        for description, target_value in PERFECT_SHOT_MATCH_PROFILE_VALUES.items():
            attr = self.config.find_attribute_by_description(description)
            if attr is None:
                continue
            if self._map_match_compact_offset(attr.offset) is None:
                continue
            attrs.append((attr, self._coerce_attribute_value(attr, target_value)))

        self._perfect_shot_match_attr_cache = attrs
        return attrs

    def _get_perfect_shot_roster_attrs(self) -> List[Tuple[AttributeDef, int]]:
        if self._perfect_shot_roster_attr_cache is not None:
            return self._perfect_shot_roster_attr_cache

        attrs: List[Tuple[AttributeDef, int]] = []
        for description, target_value in PERFECT_SHOT_ROSTER_PROFILE_VALUES.items():
            attr = self.config.find_attribute_by_description(description)
            if attr is None:
                continue
            attrs.append((attr, self._coerce_attribute_value(attr, target_value)))

        self._perfect_shot_roster_attr_cache = attrs
        return attrs

    def _iter_team_players(self, team_id: int, team_name: Optional[str]) -> List[Player]:
        if not self.players:
            self.scan_players()

        normalized_team_name = _normalize_text(team_name).lower()
        team_players: List[Player] = []
        for candidate in self.players:
            same_team_id = candidate.team_id == team_id
            same_team_name = bool(normalized_team_name) and _normalize_text(candidate.team_name).lower() == normalized_team_name
            if same_team_id or same_team_name:
                team_players.append(candidate)
        return team_players

    def _clear_match_compact_cache_for_team(self, team_id: int, team_name: Optional[str]) -> None:
        for candidate in self._iter_team_players(team_id, team_name):
            self._match_compact_entry_cache.pop(candidate.record_address, None)

    def _apply_perfect_shot_roster_boosts(
        self,
        team_id: int,
        team_name: Optional[str],
        originals: Dict[Tuple[int, str], Any],
    ) -> Dict[str, int]:
        attrs = self._get_perfect_shot_roster_attrs()
        if not attrs:
            return {
                "roster_boost_players": 0,
                "roster_boost_writes": 0,
            }

        boosted_players = 0
        boosted_writes = 0
        for player in self._iter_team_players(team_id, team_name):
            player_writes = 0
            for attr, target_value in attrs:
                key = (int(player.record_address), attr.name)
                if key not in originals:
                    originals[key] = self._read_attribute_direct(player, attr)
                if self._write_attribute_direct(player, attr, target_value):
                    player_writes += 1
            if player_writes > 0:
                boosted_players += 1
                boosted_writes += player_writes

        return {
            "roster_boost_players": boosted_players,
            "roster_boost_writes": boosted_writes,
        }

    def _restore_perfect_shot_roster_boosts(self, originals: Dict[Tuple[int, str], Any]) -> int:
        restored_writes = 0
        player_map = {int(player.record_address): player for player in self.players}

        for (record_address, attr_name), original_value in originals.items():
            if original_value is None:
                continue
            attr = self.config.get_attribute(attr_name)
            if attr is None:
                continue
            player = player_map.get(int(record_address))
            if player is None:
                player = Player(index=-1, record_address=int(record_address))
            if self._write_attribute_direct(player, attr, original_value):
                restored_writes += 1

        return restored_writes

    def _apply_perfect_shot_match_boosts(
        self,
        team_id: int,
        team_name: Optional[str],
        originals: Dict[Tuple[int, str], Any],
    ) -> Dict[str, int]:
        attrs = self._get_perfect_shot_match_attrs()
        if not attrs:
            return {
                "match_boost_players": 0,
                "match_boost_entries": 0,
                "match_boost_writes": 0,
            }

        boosted_players = 0
        boosted_writes = 0
        seen_entries: set[int] = set()

        for player in self._iter_team_players(team_id, team_name):
            entry_bases = self._get_match_compact_entry_bases(player)
            if not entry_bases:
                continue

            boosted_players += 1
            seen_entries.update(entry_bases)

            for attr, target_value in attrs:
                mapped_offset = self._map_match_compact_offset(attr.offset)
                if mapped_offset is None:
                    continue

                for entry_base in entry_bases:
                    key = (entry_base, attr.name)
                    if key not in originals:
                        originals[key] = self._read_attribute_value_at(entry_base + mapped_offset, attr)

                boosted_writes += self._write_match_compact_attribute(player, attr, target_value)

        return {
            "match_boost_players": boosted_players,
            "match_boost_entries": len(seen_entries),
            "match_boost_writes": boosted_writes,
        }

    def _restore_perfect_shot_match_boosts(self, originals: Dict[Tuple[int, str], Any]) -> int:
        restored_writes = 0
        for (entry_base, attr_name), original_value in originals.items():
            if original_value is None:
                continue
            attr = self.config.get_attribute(attr_name)
            if attr is None:
                continue
            mapped_offset = self._map_match_compact_offset(attr.offset)
            if mapped_offset is None:
                continue
            if self._write_attribute_value_at(entry_base + mapped_offset, attr, original_value):
                restored_writes += 1
        return restored_writes

    def _infer_contract_years_left(self, player: Player) -> int:
        highest_nonzero_year = 0
        for description in CONTRACT_SALARY_DESCRIPTIONS:
            attr = self.config.find_attribute_by_description(description)
            if attr is None:
                continue
            value = self._read_attribute_direct(player, attr)
            if isinstance(value, int) and value > 0:
                try:
                    year_number = int(description.split()[1])
                except (IndexError, ValueError):
                    continue
                highest_nonzero_year = max(highest_nonzero_year, year_number)
        return highest_nonzero_year

    def _get_contract_salary_attrs(self) -> List[AttributeDef]:
        attrs: List[AttributeDef] = []
        for description in CONTRACT_SALARY_DESCRIPTIONS:
            attr = self.config.find_attribute_by_description(description)
            if attr is not None:
                attrs.append(attr)
        return attrs

    def _normalize_contract_write_values(
        self,
        player: Player,
        values: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized = dict(values)
        contract_years_attr = self._get_contract_years_left_attr()
        if contract_years_attr is None:
            return normalized
        if contract_years_attr.name not in normalized:
            return normalized

        try:
            target_years = int(normalized[contract_years_attr.name])
        except (TypeError, ValueError):
            return normalized

        target_years = max(contract_years_attr.min_val, min(contract_years_attr.max_val, target_years))
        normalized[contract_years_attr.name] = target_years

        salary_attrs = self._get_contract_salary_attrs()
        if not salary_attrs:
            return normalized

        planned_values: Dict[int, int] = {}
        fallback_salary = 0
        for year_index, attr in enumerate(salary_attrs, start=1):
            raw_value = normalized.get(attr.name, self.read_attribute(player, attr))
            try:
                planned_value = int(raw_value or 0)
            except (TypeError, ValueError):
                planned_value = 0
            planned_value = max(attr.min_val, min(attr.max_val, planned_value))
            planned_values[year_index] = planned_value
            if planned_value > 0:
                fallback_salary = planned_value

        if fallback_salary <= 0:
            first_year_attr = salary_attrs[0]
            fallback_salary = max(1_000_000, first_year_attr.min_val)

        for year_index, attr in enumerate(salary_attrs, start=1):
            planned_value = planned_values[year_index]
            if year_index <= target_years:
                if planned_value <= 0:
                    planned_value = fallback_salary
                else:
                    fallback_salary = planned_value
            else:
                planned_value = 0
            normalized[attr.name] = max(attr.min_val, min(attr.max_val, planned_value))

        return normalized

    def _write_contract_years_left(self, player: Player, value: Any) -> bool:
        contract_years_attr = self._get_contract_years_left_attr()
        if contract_years_attr is None:
            return False

        updates = self._normalize_contract_write_values(
            player,
            {
                contract_years_attr.name: value,
            },
        )

        success = True
        for attr in self._get_contract_salary_attrs():
            if attr.name not in updates:
                continue
            if not self._write_attribute_direct(player, attr, updates[attr.name]):
                success = False

        if not self._write_attribute_direct(player, contract_years_attr, updates[contract_years_attr.name]):
            success = False

        return success

    def _sync_contract_years_left(self, player: Player) -> bool:
        contract_years_attr = self._get_contract_years_left_attr()
        if contract_years_attr is None:
            return False

        target_years = self._infer_contract_years_left(player)
        target_years = max(contract_years_attr.min_val, min(contract_years_attr.max_val, target_years))
        current_years = self._read_attribute_direct(player, contract_years_attr)
        if current_years == target_years:
            return True

        return self._write_attribute_direct(player, contract_years_attr, target_years)

    def read_attribute(self, player: Player, attr: AttributeDef) -> Optional[Any]:
        resolved_attr = attr
        if self._is_overall_attr(attr):
            resolved_attr = self._resolve_live_overall_attr(self._get_table_base_for_player(player)) or attr
        return self._read_attribute_direct(player, resolved_attr)

    def _write_attribute_direct(self, player: Player, attr: AttributeDef, value: Any) -> bool:
        address = player.record_address + attr.offset
        value = self._coerce_attribute_value(attr, value)

        if self._is_body_attr(attr):
            return self._write_body_attr(player, attr, value)

        success = self._write_attribute_value_at(address, attr, value)
        if success:
            self._write_match_compact_attribute(player, attr, value)
        return success

    def write_attribute(self, player: Player, attr: AttributeDef, value: Any) -> bool:
        resolved_attr = attr
        if self._is_overall_attr(attr):
            resolved_attr = self._resolve_live_overall_attr(self._get_table_base_for_player(player)) or attr
        if self._is_contract_years_left_attr(resolved_attr):
            return self._write_contract_years_left(player, value)
        success = self._write_attribute_direct(player, resolved_attr, value)
        if success and self._is_contract_salary_attr(resolved_attr):
            self._sync_contract_years_left(player)
        return success

    def read_all_attributes(self, player: Player) -> Dict[str, Any]:
        record_blob = self.mem.read_bytes(player.record_address, self.config.player_table.stride)
        body_blob = None
        body_base = self._get_body_record_base(player)
        if body_base is not None:
            body_blob = self.mem.read_bytes(body_base, 0x20)
        table_base = self._get_table_base_for_player(player)
        result: Dict[str, Any] = {}
        for attrs in self.config.attributes.values():
            for attr in attrs:
                resolved_attr = attr
                if self._is_overall_attr(attr):
                    resolved_attr = self._resolve_live_overall_attr(table_base) or attr

                if self._is_body_attr(resolved_attr):
                    value = self._read_body_attr_from_blobs(player, resolved_attr, record_blob, body_blob)
                else:
                    value = self._read_attribute_value_from_blob(record_blob, resolved_attr)

                if value is None:
                    value = self.read_attribute(player, attr)
                result[attr.name] = value
        return result

    def write_all_attributes(self, player: Player, values: Dict[str, Any]) -> Dict[str, bool]:
        results: Dict[str, bool] = {}
        pending_values = self._normalize_contract_write_values(player, values)
        contract_years_attr = self._get_contract_years_left_attr()
        ordered_names = list(pending_values.keys())
        if contract_years_attr is not None and contract_years_attr.name in ordered_names:
            ordered_names.remove(contract_years_attr.name)
            ordered_names.append(contract_years_attr.name)

        for name in ordered_names:
            value = pending_values[name]
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
        for attr in self.config.all_attributes():
            target_value = self._resolve_god_mode_value(attr)
            if target_value is None:
                continue
            if self.write_attribute(player, attr, target_value):
                count += 1

        return count

    def apply_god_mode_to_team(self, team_id: int, team_name: Optional[str] = None) -> Dict[str, Any]:
        if not self.players:
            self.scan_players()

        normalized_team_name = _normalize_text(team_name).lower()
        players = []
        for candidate in self.players:
            same_team_id = candidate.team_id == team_id
            same_team_name = bool(normalized_team_name) and _normalize_text(candidate.team_name).lower() == normalized_team_name
            if same_team_id or same_team_name:
                players.append(candidate)

        boosted_players = 0
        boosted_attributes = 0
        for player in players:
            boosted_attributes += self.apply_god_mode(player)
            boosted_players += 1
        return {
            "boosted_players": boosted_players,
            "boosted_attributes": boosted_attributes,
        }

    def _resolve_shot_runtime_entry_bases(self) -> List[int]:
        global_obj = int(self.mem.read_uint64(SHOT_RUNTIME_GLOBAL_PTR_SLOT) or 0)
        if global_obj <= 0:
            return []

        container = int(self.mem.read_uint64(global_obj + SHOT_RUNTIME_CONTAINER_OFFSET) or 0)
        if container <= 0:
            return []

        count = int(self.mem.read_uint32(container + SHOT_RUNTIME_ENTRY_COUNT_OFFSET) or 0)
        entries_base = int(self.mem.read_uint64(container + SHOT_RUNTIME_ENTRY_BASE_OFFSET) or 0)
        if count <= 0 or entries_base <= 0:
            return []

        bases: List[int] = []
        for index in range(min(count, SHOT_RUNTIME_MAX_ENTRY_COUNT)):
            entry_base = entries_base + index * SHOT_RUNTIME_ENTRY_STRIDE
            if self.mem.read_bytes(entry_base, 0x20) is None:
                continue
            bases.append(entry_base)
        return bases

    def _get_player_team_ptr(self, player: Player) -> int:
        table_base = self._get_table_base_for_player(player)
        if table_base is None:
            return 0
        team_table_base = self._resolve_team_table_base()
        team_ptr_offset, _ = self._resolve_live_team_ptr_offset(table_base, team_table_base)
        return int(self.mem.read_uint64(player.record_address + team_ptr_offset) or 0)

    def _team_block_contains_targets(
        self,
        block_base: int,
        targets: Dict[int, str],
    ) -> List[str]:
        hits: List[str] = []
        seen: set[int] = set()
        queue: List[Tuple[str, int, int]] = [
            (f"+0x{rel:03X}", int(self.mem.read_uint64(block_base + rel) or 0), 0)
            for rel in SHOT_RUNTIME_TEAM_LINK_START_RELS
        ]
        explored = 0

        while queue and explored < SHOT_RUNTIME_TEAM_LINK_MAX_OBJECTS:
            label, ptr, depth = queue.pop(0)
            if ptr <= 0 or ptr in seen or ptr > MAX_VALID_POINTER:
                continue

            seen.add(ptr)
            explored += 1
            if ptr in targets:
                hits.append(f"direct:{targets[ptr]}:{label}:{depth}")

            blob = self.mem.read_bytes(ptr, 0x200) or b""
            if not blob:
                continue

            for target, target_name in targets.items():
                qword = target.to_bytes(8, "little")
                dword = (target & 0xFFFFFFFF).to_bytes(4, "little")
                if blob.find(qword) >= 0 or blob.find(dword) >= 0:
                    hits.append(f"ref:{target_name}:{label}:{depth}")

            if depth >= 2:
                continue

            for offset in range(0, min(len(blob), 0x80), 8):
                child = int.from_bytes(blob[offset: offset + 8], "little")
                if child and child not in seen:
                    queue.append((f"{label}->0x{offset:02X}", child, depth + 1))

        return hits

    def _resolve_shot_runtime_team_block_index(self, entry_base: int, player: Player) -> Optional[int]:
        team_ptr = self._get_player_team_ptr(player)
        if team_ptr <= 0:
            return None

        cache_key = (entry_base, team_ptr)
        cached = self._shot_runtime_team_block_cache.get(cache_key)
        if cache_key in self._shot_runtime_team_block_cache:
            return cached

        targets: Dict[int, str] = {
            int(player.record_address): "player_record",
            team_ptr: "team_ptr",
        }
        summary = self.summarize_live_gameplay_state(player)
        for index, base_hex in enumerate(summary.get("match_compact_bases", [])):
            try:
                targets[int(base_hex, 16)] = f"match_compact_{index}"
            except (TypeError, ValueError):
                continue

        scored_hits: List[Tuple[int, int]] = []
        for block_index in (0, 1):
            block_base = entry_base + SHOT_RUNTIME_TEAM_BLOCK_OFFSET + block_index * SHOT_RUNTIME_TEAM_BLOCK_SIZE
            hits = self._team_block_contains_targets(block_base, targets)
            if hits:
                scored_hits.append((len(hits), block_index))

        result: Optional[int] = None
        if scored_hits:
            scored_hits.sort(reverse=True)
            result = scored_hits[0][1]

        self._shot_runtime_team_block_cache[cache_key] = result
        return result

    def _resolve_perfect_shot_team_target(
        self,
        entry_base: int,
        preferred_player: Optional[Player] = None,
        team_id: Optional[int] = None,
        team_name: Optional[str] = None,
    ) -> Optional[Tuple[Player, int, str, int]]:
        candidates: List[Player] = []
        normalized_team_name = _normalize_text(team_name).lower()

        if preferred_player is not None:
            candidates.append(preferred_player)
            if team_id is None:
                team_id = preferred_player.team_id
            if not team_name:
                team_name = preferred_player.team_name
                normalized_team_name = _normalize_text(team_name).lower()

        if team_id is not None or normalized_team_name:
            seen_records = {candidate.record_address for candidate in candidates}
            for candidate in self._iter_team_players(
                team_id if team_id is not None else UNKNOWN_TEAM_ID,
                team_name,
            ):
                if candidate.record_address in seen_records:
                    continue
                candidates.append(candidate)
                seen_records.add(candidate.record_address)

        if not candidates and self.players:
            candidates.extend(self.players)

        best: Optional[Tuple[Player, int, str, int, int]] = None
        for candidate in candidates:
            block_index = self._resolve_shot_runtime_team_block_index(entry_base, candidate)
            if block_index is None:
                continue

            match_entry_count = len(self._get_match_compact_entry_bases(candidate))
            score = match_entry_count * 100
            if preferred_player is not None and candidate.record_address == preferred_player.record_address:
                score += 10

            if best is None or score > best[4]:
                best = (
                    candidate,
                    candidate.team_id,
                    candidate.team_name or team_name or "Unknown",
                    block_index,
                    score,
                )

                if preferred_player is not None and match_entry_count > 0:
                    break

        if best is None:
            return None

        player, resolved_team_id, resolved_team_name, block_index, _ = best
        return player, resolved_team_id, resolved_team_name, block_index

    def _resolve_perfect_shot_state_player(self, state: Dict[str, Any]) -> Optional[Player]:
        try:
            team_id = int(state.get("team_id"))
        except (TypeError, ValueError):
            team_id = UNKNOWN_TEAM_ID

        team_name = state.get("team_name")
        preferred_name = _normalize_text(str(state.get("representative_player") or ""))
        candidates = self._iter_team_players(team_id, team_name)
        if preferred_name:
            for candidate in candidates:
                if _normalize_text(candidate.full_name) == preferred_name:
                    return candidate
        return candidates[0] if candidates else None

    def _validate_perfect_shot_context(
        self,
        state: Dict[str, Any],
    ) -> Tuple[bool, Optional[Player], str]:
        entry_base = int(state.get("entry_base") or 0)
        if entry_base <= 0:
            return False, None, "No live shot runtime entry is active."

        current_entries = self._resolve_shot_runtime_entry_bases()
        if entry_base not in current_entries:
            return False, None, "The live shot runtime entry is no longer active."

        player = self._resolve_perfect_shot_state_player(state)
        if player is None:
            return False, None, "The target team is no longer available in the current roster."

        self._match_compact_entry_cache.pop(player.record_address, None)
        live_match_entries = self._get_match_compact_entry_bases(player)
        if not live_match_entries:
            return False, player, "No active in-match copies were found for the selected team."

        target = self._resolve_perfect_shot_team_target(
            entry_base,
            preferred_player=player,
            team_id=player.team_id,
            team_name=player.team_name,
        )
        if target is None:
            return False, player, "Failed to resolve the selected team's live shot context."

        target_player, resolved_team_id, resolved_team_name, block_index = target
        state["team_id"] = resolved_team_id
        state["team_name"] = resolved_team_name
        state["team_block_index"] = block_index
        state["representative_player"] = target_player.full_name
        state["representative_record_address"] = int(target_player.record_address)
        return True, target_player, ""

    def _clear_legacy_perfect_shot_state(self) -> bool:
        cleared = False
        for entry_base in self._get_perfect_shot_beta_entry_bases():
            cleared = self.mem.write_uint8(entry_base + PERFECT_SHOT_ENABLE_OFFSET, 0) or cleared
            cleared = self.mem.write_uint32(entry_base + PERFECT_SHOT_LOCK_TIMER_OFFSET, 0) or cleared
            cleared = self.mem.write_uint32(entry_base + PERFECT_SHOT_LOCK_TIMER_ALT_OFFSET, 0) or cleared
        return cleared

    def _capture_runtime_perfect_shot_patches(self, entry_base: int) -> Dict[str, Dict[str, Any]]:
        originals: Dict[str, Dict[str, Any]] = {}
        for name, offset, patch_bytes in SHOT_RUNTIME_PERFECT_PATCHES:
            address = entry_base + offset
            original_bytes = self.mem.read_bytes(address, len(patch_bytes))
            if not original_bytes or len(original_bytes) != len(patch_bytes):
                continue
            originals[name] = {
                "address": address,
                "original": original_bytes,
                "patch": patch_bytes,
            }
        return originals

    def _apply_runtime_perfect_shot_patches(
        self,
        originals: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        writes = 0
        applied: Dict[str, bool] = {}
        for name, patch_state in originals.items():
            address = int(patch_state["address"])
            patch_bytes = bytes(patch_state["patch"])
            current_bytes = self.mem.read_bytes(address, len(patch_bytes)) or b""
            if current_bytes != patch_bytes and self.mem.write_bytes(address, patch_bytes):
                writes += 1
                current_bytes = self.mem.read_bytes(address, len(patch_bytes)) or b""
            applied[name] = current_bytes == patch_bytes
        return {
            "writes": writes,
            "applied": applied,
        }

    def _restore_runtime_perfect_shot_patches(
        self,
        originals: Dict[str, Dict[str, Any]],
    ) -> int:
        writes = 0
        for patch_state in originals.values():
            if self.mem.write_bytes(int(patch_state["address"]), bytes(patch_state["original"])):
                writes += 1
        return writes

    def _capture_legacy_perfect_shot_patches(self) -> Dict[Tuple[int, int], bytes]:
        originals: Dict[Tuple[int, int], bytes] = {}
        for entry_base in self._get_perfect_shot_beta_entry_bases():
            for offset, patch_bytes in PERFECT_SHOT_LEGACY_STATE_PATCHES:
                original_bytes = self.mem.read_bytes(entry_base + offset, len(patch_bytes))
                if not original_bytes or len(original_bytes) != len(patch_bytes):
                    continue
                originals[(entry_base, offset)] = original_bytes
        return originals

    def _apply_legacy_perfect_shot_patches(self, originals: Dict[Tuple[int, int], bytes]) -> int:
        writes = 0
        for (entry_base, offset), original_bytes in originals.items():
            patch_bytes = next(
                (
                    candidate
                    for candidate_offset, candidate in PERFECT_SHOT_LEGACY_STATE_PATCHES
                    if candidate_offset == offset
                ),
                None,
            )
            if patch_bytes is None or original_bytes == patch_bytes:
                continue
            if self.mem.write_bytes(entry_base + offset, patch_bytes):
                writes += 1
        return writes

    def _restore_legacy_perfect_shot_patches(self, originals: Dict[Tuple[int, int], bytes]) -> int:
        writes = 0
        for (entry_base, offset), original_bytes in originals.items():
            if self.mem.write_bytes(entry_base + offset, original_bytes):
                writes += 1
        return writes

    def start_perfect_shot_beta(self, player: Player) -> Dict[str, Any]:
        return self.start_perfect_shot_beta_for_team(
            team_id=player.team_id,
            team_name=player.team_name,
            preferred_player=player,
        )

    def start_perfect_shot_beta_for_team(
        self,
        team_id: Optional[int] = None,
        team_name: Optional[str] = None,
        preferred_player: Optional[Player] = None,
    ) -> Dict[str, Any]:
        if self._perfect_shot_beta_state is not None:
            self.stop_perfect_shot_beta()

        entry_bases = self._resolve_shot_runtime_entry_bases()
        if not entry_bases:
            return {
                "active": False,
                "error": "No shot runtime entry was found.",
            }

        entry_base = entry_bases[0]
        target = self._resolve_perfect_shot_team_target(
            entry_base,
            preferred_player=preferred_player,
            team_id=team_id,
            team_name=team_name,
        )
        if target is None:
            return {
                "active": False,
                "error": "Failed to resolve the live MyGM team block.",
            }
        target_player, resolved_team_id, target_team_name, team_block_index = target
        self._match_compact_entry_cache.pop(target_player.record_address, None)
        if not self._get_match_compact_entry_bases(target_player):
            return {
                "active": False,
                "error": "No active in-match copies were found for the selected team. Start Lock Green only during a live game.",
            }

        runtime_patch_originals: Dict[str, Dict[str, Any]] = {}
        runtime_patch_summary = {
            "writes": 0,
            "applied": {},
        }
        if PERFECT_SHOT_SHARED_RUNTIME_PATCHES_ENABLED:
            runtime_patch_originals = self._capture_runtime_perfect_shot_patches(entry_base)
            if "human_team_delta" not in runtime_patch_originals:
                return {
                    "active": False,
                    "error": "Failed to read the live shot timing buffers.",
                }
            runtime_patch_summary = self._apply_runtime_perfect_shot_patches(runtime_patch_originals)
        runtime_applied = runtime_patch_summary.get("applied", {})
        legacy_cleared = self._clear_legacy_perfect_shot_state()
        legacy_state_originals: Dict[Tuple[int, int], bytes] = {}
        legacy_state_writes = 0
        if PERFECT_SHOT_SHARED_LEGACY_PATCHES_ENABLED:
            legacy_state_originals = self._capture_legacy_perfect_shot_patches()
            legacy_state_writes = self._apply_legacy_perfect_shot_patches(legacy_state_originals)
        match_copy_originals: Dict[Tuple[int, str], Any] = {}
        match_boost_summary = self._apply_perfect_shot_match_boosts(
            resolved_team_id,
            target_team_name,
            match_copy_originals,
        )
        roster_originals: Dict[Tuple[int, str], Any] = {}
        roster_boost_summary = self._apply_perfect_shot_roster_boosts(
            resolved_team_id,
            target_team_name,
            roster_originals,
        )

        self._perfect_shot_beta_state = {
            "entry_base": entry_base,
            "runtime_patch_originals": runtime_patch_originals,
            "runtime_patch_writes": int(runtime_patch_summary["writes"]),
            "team_id": resolved_team_id,
            "team_name": target_team_name,
            "team_block_index": team_block_index,
            "representative_player": target_player.full_name,
            "representative_record_address": int(target_player.record_address),
            "refresh_counter": 0,
            "legacy_state_originals": legacy_state_originals,
            "legacy_state_writes": legacy_state_writes,
            "roster_originals": roster_originals,
            "roster_boost_players": roster_boost_summary["roster_boost_players"],
            "roster_boost_writes": roster_boost_summary["roster_boost_writes"],
            "match_copy_originals": match_copy_originals,
            "match_boost_players": match_boost_summary["match_boost_players"],
            "match_boost_entries": match_boost_summary["match_boost_entries"],
            "match_boost_writes": match_boost_summary["match_boost_writes"],
            "shared_runtime_patches_enabled": PERFECT_SHOT_SHARED_RUNTIME_PATCHES_ENABLED,
            "shared_legacy_patches_enabled": PERFECT_SHOT_SHARED_LEGACY_PATCHES_ENABLED,
        }
        self._perfect_shot_beta_state.update(runtime_applied)

        return {
            "active": True,
            "entry_base": hex(entry_base),
            "target_team_name": target_team_name,
            "team_block_index": team_block_index,
            "ai_delta_written": bool(
                runtime_applied.get("ai_team_delta") or runtime_applied.get("human_team_delta")
            ),
            "ai_team_delta_written": bool(runtime_applied.get("ai_team_delta")),
            "human_team_delta_written": bool(runtime_applied.get("human_team_delta")),
            "coverage_delta_written": bool(runtime_applied.get("coverage_delta")),
            "impact_delta_written": bool(runtime_applied.get("impact_delta")),
            "runtime_patch_writes": int(runtime_patch_summary["writes"]),
            "legacy_cleared": legacy_cleared,
            "legacy_state_writes": legacy_state_writes,
            "roster_boost_players": roster_boost_summary["roster_boost_players"],
            "roster_boost_writes": roster_boost_summary["roster_boost_writes"],
            "representative_player": target_player.full_name,
            "match_boost_players": match_boost_summary["match_boost_players"],
            "match_boost_entries": match_boost_summary["match_boost_entries"],
            "match_boost_writes": match_boost_summary["match_boost_writes"],
        }

    def refresh_perfect_shot_beta(self) -> Dict[str, Any]:
        state = self._perfect_shot_beta_state
        if not state:
            return {"active": False}

        is_live, _, reason = self._validate_perfect_shot_context(state)
        if not is_live:
            stop_summary = self.stop_perfect_shot_beta(restore_live_memory=False, reason=reason)
            stop_summary["auto_stopped"] = True
            return stop_summary

        runtime_patch_summary = {
            "writes": 0,
            "applied": {},
        }
        if state.get("shared_runtime_patches_enabled"):
            runtime_patch_summary = self._apply_runtime_perfect_shot_patches(
                state.get("runtime_patch_originals", {})
            )
        runtime_applied = runtime_patch_summary.get("applied", {})
        legacy_state_writes = 0
        if state.get("shared_legacy_patches_enabled"):
            legacy_state_writes = self._apply_legacy_perfect_shot_patches(
                state.get("legacy_state_originals", {})
            )
        state.update(runtime_applied)
        state["runtime_patch_writes"] = int(runtime_patch_summary["writes"])
        state["legacy_state_writes"] = legacy_state_writes
        state["refresh_counter"] = int(state.get("refresh_counter", 0)) + 1
        match_boost_players = int(state.get("match_boost_players", 0))
        match_boost_entries = int(state.get("match_boost_entries", 0))
        match_boost_writes = 0

        if state["refresh_counter"] % PERFECT_SHOT_MATCH_REFRESH_INTERVAL == 0:
            self._clear_match_compact_cache_for_team(int(state["team_id"]), state["team_name"])
            match_boost_summary = self._apply_perfect_shot_match_boosts(
                int(state["team_id"]),
                state["team_name"],
                state["match_copy_originals"],
            )
            state["match_boost_players"] = match_boost_summary["match_boost_players"]
            state["match_boost_entries"] = match_boost_summary["match_boost_entries"]
            state["match_boost_writes"] = match_boost_summary["match_boost_writes"]
            match_boost_players = match_boost_summary["match_boost_players"]
            match_boost_entries = match_boost_summary["match_boost_entries"]
            match_boost_writes = match_boost_summary["match_boost_writes"]

        return {
            "active": True,
            "entry_base": hex(int(state["entry_base"])),
            "target_team_name": state["team_name"],
            "team_block_index": state["team_block_index"],
            "ai_delta_written": bool(
                runtime_applied.get("ai_team_delta") or runtime_applied.get("human_team_delta")
            ),
            "ai_team_delta_written": bool(runtime_applied.get("ai_team_delta")),
            "human_team_delta_written": bool(runtime_applied.get("human_team_delta")),
            "coverage_delta_written": bool(runtime_applied.get("coverage_delta")),
            "impact_delta_written": bool(runtime_applied.get("impact_delta")),
            "runtime_patch_writes": int(runtime_patch_summary["writes"]),
            "legacy_state_writes": legacy_state_writes,
            "match_boost_players": match_boost_players,
            "match_boost_entries": match_boost_entries,
            "match_boost_writes": match_boost_writes,
        }

    def stop_perfect_shot_beta(
        self,
        *,
        restore_live_memory: bool = True,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        state = self._perfect_shot_beta_state
        if not state:
            return {"active": False, "restored": False}

        restored_runtime_writes = 0
        restored_roster_writes = 0
        restored_match_writes = 0
        restored_legacy_state_writes = 0
        legacy_cleared = False

        if restore_live_memory:
            if state.get("shared_runtime_patches_enabled"):
                restored_runtime_writes = self._restore_runtime_perfect_shot_patches(
                    state.get("runtime_patch_originals", {})
                )
            restored_roster_writes = self._restore_perfect_shot_roster_boosts(
                state.get("roster_originals", {})
            )
            restored_match_writes = self._restore_perfect_shot_match_boosts(
                state.get("match_copy_originals", {})
            )
            if state.get("shared_legacy_patches_enabled"):
                restored_legacy_state_writes = self._restore_legacy_perfect_shot_patches(
                    state.get("legacy_state_originals", {})
                )
            legacy_cleared = self._clear_legacy_perfect_shot_state()

        team_name = state.get("team_name", "Unknown")
        self._perfect_shot_beta_state = None
        result = {
            "active": False,
            "restored": (restored_runtime_writes + restored_roster_writes + restored_match_writes) > 0,
            "restored_runtime_writes": restored_runtime_writes,
            "restored_roster_writes": restored_roster_writes,
            "restored_match_writes": restored_match_writes,
            "restored_legacy_state_writes": restored_legacy_state_writes,
            "legacy_cleared": legacy_cleared,
            "target_team_name": team_name,
            "restore_skipped": not restore_live_memory,
        }
        if reason:
            result["reason"] = reason
        return result

    def _resolve_perfect_shot_manager_base(self) -> Optional[int]:
        module_base = int(self.mem.base_address or 0)
        if module_base <= 0:
            return None
        manager_slot = module_base + PERFECT_SHOT_MANAGER_SLOT_OFFSET
        manager_base = self.mem.read_uint64(manager_slot)
        if not isinstance(manager_base, int) or manager_base <= 0:
            return None
        return int(manager_base)

    def _get_perfect_shot_beta_entry_bases(self) -> List[int]:
        manager_base = self._resolve_perfect_shot_manager_base()
        if manager_base is None:
            return []

        count = int(self.mem.read_uint32(manager_base + PERFECT_SHOT_ENTRY_COUNT_OFFSET) or 0)
        entries_base = int(self.mem.read_uint64(manager_base + PERFECT_SHOT_ENTRY_ARRAY_OFFSET) or 0)
        if count <= 0 or entries_base <= 0:
            return []

        entry_bases: List[int] = []
        for index in range(min(count, PERFECT_SHOT_MAX_ENTRY_COUNT)):
            entry_base = entries_base + index * PERFECT_SHOT_ENTRY_STRIDE
            if self.mem.read_bytes(entry_base + PERFECT_SHOT_ENABLE_OFFSET, 1) is None:
                continue
            entry_bases.append(entry_base)
        return entry_bases

    def get_perfect_shot_beta_state(self) -> Dict[str, Any]:
        state = self._perfect_shot_beta_state or {}
        legacy_manager_base = self._resolve_perfect_shot_manager_base()
        legacy_entries: List[Dict[str, Any]] = []
        for entry_base in self._get_perfect_shot_beta_entry_bases():
            legacy_entries.append(
                {
                    "base": hex(entry_base),
                    "enable_byte": int(self.mem.read_uint8(entry_base + PERFECT_SHOT_ENABLE_OFFSET) or 0),
                    "lock_timer": int(self.mem.read_uint32(entry_base + PERFECT_SHOT_LOCK_TIMER_OFFSET) or 0),
                    "lock_timer_alt": int(
                        self.mem.read_uint32(entry_base + PERFECT_SHOT_LOCK_TIMER_ALT_OFFSET) or 0
                    ),
                }
            )

        return {
            "active": bool(state),
            "entry_base": hex(int(state["entry_base"])) if state.get("entry_base") else None,
            "target_team_name": state.get("team_name"),
            "team_block_index": state.get("team_block_index"),
            "representative_player": state.get("representative_player"),
            "match_boost_players": state.get("match_boost_players", 0),
            "match_boost_entries": state.get("match_boost_entries", 0),
            "match_boost_writes": state.get("match_boost_writes", 0),
            "roster_boost_players": state.get("roster_boost_players", 0),
            "roster_boost_writes": state.get("roster_boost_writes", 0),
            "runtime_patch_writes": state.get("runtime_patch_writes", 0),
            "ai_team_delta_written": bool(state.get("ai_team_delta")),
            "human_team_delta_written": bool(state.get("human_team_delta")),
            "coverage_delta_written": bool(state.get("coverage_delta")),
            "impact_delta_written": bool(state.get("impact_delta")),
            "legacy_state_writes": state.get("legacy_state_writes", 0),
            "legacy_manager_base": hex(legacy_manager_base) if legacy_manager_base is not None else None,
            "legacy_entries": legacy_entries,
        }

    def enforce_perfect_shot_beta(self) -> Dict[str, Any]:
        return self.refresh_perfect_shot_beta()
