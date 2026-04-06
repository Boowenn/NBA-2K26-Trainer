"""球员数据模型 - 扫描球员列表、读写属性"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from ..core.memory import GameMemory
from ..core.offsets import OffsetConfig, AttributeDef


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
    position: str = ""

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


# NBA 球队 ID -> 名称映射
TEAM_NAMES = {
    0: "ATL Hawks", 1: "BOS Celtics", 2: "BKN Nets", 3: "CHA Hornets",
    4: "CHI Bulls", 5: "CLE Cavaliers", 6: "DAL Mavericks", 7: "DEN Nuggets",
    8: "DET Pistons", 9: "GSW Warriors", 10: "HOU Rockets", 11: "IND Pacers",
    12: "LAC Clippers", 13: "LAL Lakers", 14: "MEM Grizzlies", 15: "MIA Heat",
    16: "MIL Bucks", 17: "MIN Timberwolves", 18: "NOP Pelicans", 19: "NYK Knicks",
    20: "OKC Thunder", 21: "ORL Magic", 22: "PHI 76ers", 23: "PHX Suns",
    24: "POR Trail Blazers", 25: "SAC Kings", 26: "SAS Spurs", 27: "TOR Raptors",
    28: "UTA Jazz", 29: "WAS Wizards",
}

POSITION_MAP = {0: "PG", 1: "SG", 2: "SF", 3: "PF", 4: "C"}


class PlayerManager:
    """球员管理器 - 扫描和读写球员数据"""

    def __init__(self, mem: GameMemory, config: OffsetConfig):
        self.mem = mem
        self.config = config
        self.players: List[Player] = []
        self._table_base: Optional[int] = None

    def _resolve_table_base(self) -> Optional[int]:
        """解析球员表基地址"""
        pt = self.config.player_table
        if pt.pointer_offsets:
            base = self.mem.resolve_pointer_chain(
                self.mem.base_address, pt.pointer_offsets
            )
            return base
        return None

    def scan_players(self) -> List[Player]:
        """扫描内存中的球员列表"""
        self._table_base = self._resolve_table_base()
        if self._table_base is None:
            return []

        pt = self.config.player_table
        players = []

        for i in range(pt.max_players):
            record_addr = self._table_base + i * pt.stride

            first_name = self.mem.read_wstring(record_addr + pt.first_name_offset, 16)
            last_name = self.mem.read_wstring(record_addr + pt.last_name_offset, 16)

            if not first_name and not last_name:
                continue
            if first_name is None:
                first_name = ""
            if last_name is None:
                last_name = ""

            # 跳过空记录
            if len(first_name.strip()) == 0 and len(last_name.strip()) == 0:
                continue

            team_id_val = self.mem.read_uint32(record_addr + pt.team_id_offset)
            team_id = team_id_val if team_id_val is not None else -1

            player = Player(
                index=i,
                record_address=record_addr,
                first_name=first_name.strip(),
                last_name=last_name.strip(),
                team_id=team_id,
                team_name=TEAM_NAMES.get(team_id, f"Team {team_id}"),
            )

            # 读取年龄和综合评分
            age_attr = self.config.get_attribute("年龄")
            if age_attr:
                player.age = self.read_attribute(player, age_attr) or 0

            ovr_attr = self.config.get_attribute("综合评分")
            if ovr_attr:
                player.overall = self.read_attribute(player, ovr_attr) or 0

            pos_attr = self.config.get_attribute("位置")
            if pos_attr:
                pos_val = self.read_attribute(player, pos_attr)
                player.position = POSITION_MAP.get(pos_val, "?") if pos_val is not None else "?"

            players.append(player)

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
            value = max(attr.min_val, min(attr.max_val, int(value) if t != "float" else value))

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
