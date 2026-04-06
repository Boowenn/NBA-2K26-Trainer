"""Offset 管理 - 从 JSON 配置加载球员属性内存偏移"""

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class AttributeDef:
    """单个属性的定义"""
    name: str
    offset: int
    type: str = "uint8"        # uint8, uint16, uint32, int32, float, bitfield, wstring, ascii
    bit_start: int = 0         # bitfield 专用
    bit_length: int = 0        # bitfield 专用
    min_val: int = 0
    max_val: int = 99
    category: str = "其他"
    string_length: int = 32    # string 类型的最大长度
    description: str = ""


@dataclass
class PlayerTableDef:
    """球员表定义"""
    signature: str = ""        # AOB 特征码
    pointer_offsets: List[int] = field(default_factory=list)  # 指针链
    stride: int = 712          # 每个球员记录的字节大小
    count_offset: int = 0      # 球员数量的偏移
    max_players: int = 600
    name_offset: int = 0       # 姓名字段相对于记录起始的偏移
    first_name_offset: int = 0
    last_name_offset: int = 16
    team_id_offset: int = 48


@dataclass
class OffsetConfig:
    """完整的 offset 配置"""
    version: str = ""
    game_version: str = ""
    player_table: PlayerTableDef = field(default_factory=PlayerTableDef)
    attributes: Dict[str, List[AttributeDef]] = field(default_factory=dict)

    def all_attributes(self) -> List[AttributeDef]:
        result = []
        for attrs in self.attributes.values():
            result.extend(attrs)
        return result

    def get_attribute(self, name: str) -> Optional[AttributeDef]:
        for attrs in self.attributes.values():
            for a in attrs:
                if a.name == name:
                    return a
        return None

    def categories(self) -> List[str]:
        return list(self.attributes.keys())


def load_offsets(filepath: str) -> OffsetConfig:
    """从 JSON 文件加载 offset 配置"""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    config = OffsetConfig()
    config.version = data.get("version", "")
    config.game_version = data.get("game_version", "")

    pt = data.get("player_table", {})
    config.player_table = PlayerTableDef(
        signature=pt.get("signature", ""),
        pointer_offsets=pt.get("pointer_offsets", []),
        stride=pt.get("stride", 712),
        count_offset=pt.get("count_offset", 0),
        max_players=pt.get("max_players", 600),
        name_offset=pt.get("name_offset", 0),
        first_name_offset=pt.get("first_name_offset", 0),
        last_name_offset=pt.get("last_name_offset", 16),
        team_id_offset=pt.get("team_id_offset", 48),
    )

    attrs_data = data.get("attributes", {})
    for category, attr_list in attrs_data.items():
        defs = []
        for a in attr_list:
            defs.append(AttributeDef(
                name=a["name"],
                offset=a["offset"],
                type=a.get("type", "uint8"),
                bit_start=a.get("bit_start", 0),
                bit_length=a.get("bit_length", 0),
                min_val=a.get("min", 0),
                max_val=a.get("max", 99),
                category=category,
                string_length=a.get("string_length", 32),
                description=a.get("description", ""),
            ))
        config.attributes[category] = defs

    return config


def get_default_offsets_path() -> str:
    """获取默认 offset 配置文件路径"""
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "config", "offsets_2k26.json")


_current_config: Optional[OffsetConfig] = None


def initialize_offsets(filepath: Optional[str] = None) -> OffsetConfig:
    """初始化并缓存 offset 配置"""
    global _current_config
    if filepath is None:
        filepath = get_default_offsets_path()
    _current_config = load_offsets(filepath)
    return _current_config


def get_offsets() -> Optional[OffsetConfig]:
    """获取当前 offset 配置"""
    return _current_config
