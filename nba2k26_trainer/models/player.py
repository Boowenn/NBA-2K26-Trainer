"""球员数据模型 - 扫描球员列表、读写属性"""

import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from ..core.memory import GameMemory
from ..core.offsets import OffsetConfig, AttributeDef
from ..core.scanner import scan_for_player_table, scan_for_base_pointer


@dataclass
class Player:
    """球员数据"""
    index: int
    record_address: int
    first_name: str = ""
    last_name: str = ""
    team_id: int = -1
    team_name: str = ""
    overall: int = 0
    age: int = 0
    birth_year: int = 0
    position: str = ""

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


# Player record offsets for team pointer resolution
TEAM_PTR_OFFSET = 96         # 0x60 - uint64 pointer to team record
TEAM_NAME_OFFSET = 738       # 0x2E2 - wstring in team record
TEAM_NAME_LENGTH = 24        # max chars
TEAM_STRIDE = 5672           # team record stride

POSITION_MAP = {0: "PG", 1: "SG", 2: "SF", 3: "PF", 4: "C"}


def _is_valid_name(text: str) -> bool:
    """Check if a string looks like a valid player/team name"""
    if not text or len(text) < 2:
        return False
    # Reject strings with control chars or replacement chars
    for c in text:
        code = ord(c)
        if code < 32 or code == 0xFFFD:
            return False
    return True


def birth_year_to_age(birth_year: int) -> int:
    """出生年份转换为当前年龄"""
    if birth_year <= 0 or birth_year > 2020:
        return 0
    current_year = datetime.datetime.now().year
    return current_year - birth_year


def age_to_birth_year(age: int) -> int:
    """年龄转换为出生年份"""
    current_year = datetime.datetime.now().year
    return current_year - age


class PlayerManager:
    """球员管理器 - 扫描和读写球员数据"""

    def __init__(self, mem: GameMemory, config: OffsetConfig):
        self.mem = mem
        self.config = config
        self.players: List[Player] = []
        self._table_base: Optional[int] = None

    def _resolve_table_base(self, progress_callback=None) -> Optional[int]:
        """解析球员表基地址 - 先尝试配置的指针，失败后动态扫描"""
        if self._table_base is not None:
            return self._table_base

        pt = self.config.player_table

        # Method 1: configured pointer (RVA from module base)
        if pt.direct_table and pt.base_pointer > 0:
            table_ptr = self.mem.read_uint64(self.mem.base_address + pt.base_pointer)
            if table_ptr and table_ptr != 0:
                # Validate it looks like a real player table
                if self._validate_table_ptr(table_ptr):
                    return table_ptr
            # Try absolute address
            table_ptr = self.mem.read_uint64(pt.base_pointer)
            if table_ptr and table_ptr != 0:
                if self._validate_table_ptr(table_ptr):
                    return table_ptr

        # Method 2: pointer chain
        if pt.pointer_offsets:
            base = self.mem.resolve_pointer_chain(
                self.mem.base_address, pt.pointer_offsets
            )
            if base and self._validate_table_ptr(base):
                return base

        # Method 3: Dynamic memory scan (fallback)
        if progress_callback:
            progress_callback("Config pointer failed, scanning memory for player table...")
        table_base = scan_for_player_table(
            self.mem,
            stride=pt.stride,
            last_name_offset=pt.last_name_offset,
            first_name_offset=pt.first_name_offset,
            name_max_chars=pt.name_string_length,
            max_players=pt.max_players,
            progress_callback=progress_callback,
        )
        if table_base is not None:
            # Try to find the pointer RVA for future use
            new_rva = scan_for_base_pointer(
                self.mem, table_base, self.mem.base_address
            )
            if new_rva is not None and progress_callback:
                progress_callback(
                    f"Found new base_pointer RVA: 0x{new_rva:X} ({new_rva}). "
                    f"Update config/offsets_2k26.json base_pointer to {new_rva}."
                )
        return table_base

    def _validate_table_ptr(self, table_ptr: int) -> bool:
        """Quick validation: check if first few records have valid player names"""
        pt = self.config.player_table
        valid = 0
        for i in range(min(6, pt.max_players)):
            record = table_ptr + i * pt.stride
            last = self.mem.read_wstring(record + pt.last_name_offset, pt.name_string_length)
            first = self.mem.read_wstring(record + pt.first_name_offset, pt.name_string_length)
            last = (last or "").strip()
            first = (first or "").strip()
            if last and first and len(last) >= 2 and len(first) >= 2:
                if all(32 <= ord(c) <= 126 for c in last + first):
                    valid += 1
        return valid >= 2

    def scan_players(self, progress_callback=None) -> List[Player]:
        """扫描内存中的球员列表"""
        self._table_base = self._resolve_table_base(progress_callback)
        if self._table_base is None:
            return []

        pt = self.config.player_table
        players = []
        name_len = pt.name_string_length

        # Team pointer cache: team_ptr -> (team_name, team_id)
        team_cache: Dict[int, tuple] = {}
        team_id_counter = 0

        for i in range(pt.max_players):
            record_addr = self._table_base + i * pt.stride

            # 读取姓名
            last_name = self.mem.read_wstring(record_addr + pt.last_name_offset, name_len)
            first_name = self.mem.read_wstring(record_addr + pt.first_name_offset, name_len)

            last_name = (last_name or "").strip()
            first_name = (first_name or "").strip()

            # 跳过空记录
            if not first_name and not last_name:
                continue

            # 跳过乱码记录 - 名字必须是可读字符
            if not _is_valid_name(first_name) and not _is_valid_name(last_name):
                continue

            player = Player(
                index=i,
                record_address=record_addr,
                first_name=first_name,
                last_name=last_name,
            )

            # 读取球队指针 -> 解析球队名称和ID
            team_ptr = self.mem.read_uint64(record_addr + TEAM_PTR_OFFSET)
            if team_ptr and 0x10000 < team_ptr < 0x7FFFFFFFFFFF:
                if team_ptr in team_cache:
                    player.team_name, player.team_id = team_cache[team_ptr]
                else:
                    tname = self.mem.read_wstring(team_ptr + TEAM_NAME_OFFSET, TEAM_NAME_LENGTH)
                    tname = (tname or "").strip()
                    if _is_valid_name(tname):
                        tid = team_id_counter
                        team_id_counter += 1
                        team_cache[team_ptr] = (tname, tid)
                        player.team_name = tname
                        player.team_id = tid
                    elif team_ptr == 0:
                        team_cache[team_ptr] = ("Free Agent", -2)
                        player.team_name = "Free Agent"
                        player.team_id = -2
                    else:
                        # Team pointer valid but name unreadable - try alternate offsets
                        found_team = False
                        for alt_off in [0, 40, 80, 692, 824]:
                            alt_name = self.mem.read_wstring(team_ptr + alt_off, 24)
                            alt_name = (alt_name or "").strip()
                            if _is_valid_name(alt_name) and len(alt_name) >= 3:
                                tid = team_id_counter
                                team_id_counter += 1
                                team_cache[team_ptr] = (alt_name, tid)
                                player.team_name = alt_name
                                player.team_id = tid
                                found_team = True
                                break
                        if not found_team:
                            team_cache[team_ptr] = ("Unknown", -2)
                            player.team_name = "Unknown"
                            player.team_id = -2

            # 读取综合评分
            ovr_attr = self.config.get_attribute("综合评分")
            if ovr_attr:
                val = self.read_attribute(player, ovr_attr)
                player.overall = val if val is not None else 0

            # 读取出生年份 -> 计算年龄
            birth_attr = self.config.get_attribute("出生年份")
            if birth_attr:
                val = self.read_attribute(player, birth_attr)
                if val is not None and 1950 < val < 2020:
                    player.birth_year = val
                    player.age = birth_year_to_age(val)

            players.append(player)

        # Store discovered teams for the UI
        self._discovered_teams = {tid: name for name, tid in team_cache.values() if tid >= 0}
        self.players = players
        return players

    def read_attribute(self, player: Player, attr: AttributeDef) -> Optional[Any]:
        """读取球员的单个属性"""
        addr = player.record_address + attr.offset
        t = attr.type

        if t == "uint8":
            return self.mem.read_uint8(addr)
        elif t == "int8":
            return self.mem.read_int8(addr)
        elif t == "uint16":
            return self.mem.read_uint16(addr)
        elif t == "int16":
            return self.mem.read_int16(addr)
        elif t == "uint32":
            return self.mem.read_uint32(addr)
        elif t == "int32":
            return self.mem.read_int32(addr)
        elif t == "uint64":
            return self.mem.read_uint64(addr)
        elif t == "float":
            return self.mem.read_float(addr)
        elif t == "bitfield":
            return self.mem.read_bitfield(addr, attr.bit_start, attr.bit_length)
        elif t == "wstring":
            return self.mem.read_wstring(addr, attr.string_length)
        elif t == "ascii":
            return self.mem.read_ascii(addr, attr.string_length)
        return None

    def write_attribute(self, player: Player, attr: AttributeDef, value: Any) -> bool:
        """写入球员的单个属性"""
        addr = player.record_address + attr.offset
        t = attr.type

        # 数值范围校验
        if isinstance(value, (int, float)) and t not in ("wstring", "ascii"):
            if t == "float":
                value = max(float(attr.min_val), min(float(attr.max_val), float(value)))
            else:
                value = max(attr.min_val, min(attr.max_val, int(value)))

        if t == "uint8":
            return self.mem.write_uint8(addr, value)
        elif t == "int8":
            return self.mem.write_int8(addr, value)
        elif t == "uint16":
            return self.mem.write_uint16(addr, value)
        elif t == "int16":
            return self.mem.write_int16(addr, value)
        elif t == "uint32":
            return self.mem.write_uint32(addr, value)
        elif t == "int32":
            return self.mem.write_int32(addr, value)
        elif t == "uint64":
            return self.mem.write_uint64(addr, value)
        elif t == "float":
            return self.mem.write_float(addr, value)
        elif t == "bitfield":
            return self.mem.write_bitfield(addr, attr.bit_start, attr.bit_length, value)
        elif t == "wstring":
            return self.mem.write_wstring(addr, str(value), attr.string_length)
        elif t == "ascii":
            encoded = str(value).encode("ascii", errors="replace")[:attr.string_length]
            padded = encoded.ljust(attr.string_length, b'\x00')
            return self.mem.write_bytes(addr, padded)
        return False

    def read_all_attributes(self, player: Player) -> Dict[str, Any]:
        """读取球员的全部属性"""
        result = {}
        for category, attrs in self.config.attributes.items():
            for attr in attrs:
                val = self.read_attribute(player, attr)
                result[attr.name] = val
        return result

    def write_all_attributes(self, player: Player, values: Dict[str, Any]) -> Dict[str, bool]:
        """批量写入球员属性"""
        results = {}
        for name, value in values.items():
            attr = self.config.get_attribute(name)
            if attr is not None:
                results[name] = self.write_attribute(player, attr, value)
        return results

    def set_all_to_max(self, player: Player, categories: Optional[List[str]] = None) -> int:
        """将指定分类的所有属性设为最大值"""
        count = 0
        for category, attrs in self.config.attributes.items():
            if categories and category not in categories:
                continue
            for attr in attrs:
                if attr.type in ("wstring", "ascii"):
                    continue
                if self.write_attribute(player, attr, attr.max_val):
                    count += 1
        return count

    def apply_god_mode(self, player: Player) -> int:
        """超级模式 - 所有能力99 + 全徽章满级 + 全倾向拉满 + 全耐久满"""
        count = 0
        # 所有能力属性设为99
        ability_cats = ["进攻能力", "防守能力", "体能属性", "篮球智商"]
        for cat in ability_cats:
            attrs = self.config.attributes.get(cat, [])
            for attr in attrs:
                if attr.type in ("wstring", "ascii"):
                    continue
                if self.write_attribute(player, attr, attr.max_val):
                    count += 1

        # 所有徽章满级
        badge_cats = [c for c in self.config.categories() if "徽章" in c]
        for cat in badge_cats:
            attrs = self.config.attributes.get(cat, [])
            for attr in attrs:
                if self.write_attribute(player, attr, attr.max_val):
                    count += 1

        # 所有倾向拉满
        tendency_cats = [c for c in self.config.categories()
                         if "倾向" in c or "风格" in c]
        for cat in tendency_cats:
            attrs = self.config.attributes.get(cat, [])
            for attr in attrs:
                if self.write_attribute(player, attr, attr.max_val):
                    count += 1

        # 耐久性满
        dur_attrs = self.config.attributes.get("耐久性", [])
        for attr in dur_attrs:
            if self.write_attribute(player, attr, attr.max_val):
                count += 1

        # 潜力拉满
        pot_attrs = self.config.attributes.get("潜力与成长", [])
        for attr in pot_attrs:
            if self.write_attribute(player, attr, attr.max_val):
                count += 1

        return count
