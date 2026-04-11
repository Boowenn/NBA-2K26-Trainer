"""Offset loading and schema definitions."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class AttributeDef:
    name: str
    offset: int
    type: str = "uint8"
    bit_start: int = 0
    bit_length: int = 0
    min_val: int = 0
    max_val: int = 99
    category: str = "Misc"
    string_length: int = 32
    description: str = ""


@dataclass
class PlayerTableDef:
    signature: str = ""
    base_pointer: int = 0
    pointer_offsets: List[int] = field(default_factory=list)
    stride: int = 1176
    count_offset: int = 0
    max_players: int = 600
    name_offset: int = 0
    first_name_offset: int = 40
    last_name_offset: int = 0
    team_id_offset: int = -1
    name_string_length: int = 20
    direct_table: bool = True


@dataclass
class TeamTableDef:
    base_pointer: int = 0
    stride: int = 5672
    team_name_offset: int = 738
    team_name_length: int = 24
    max_teams: int = 64


@dataclass
class OffsetConfig:
    version: str = ""
    game_version: str = ""
    player_table: PlayerTableDef = field(default_factory=PlayerTableDef)
    team_table: TeamTableDef = field(default_factory=TeamTableDef)
    attributes: Dict[str, List[AttributeDef]] = field(default_factory=dict)

    def all_attributes(self) -> List[AttributeDef]:
        result: List[AttributeDef] = []
        for attrs in self.attributes.values():
            result.extend(attrs)
        return result

    def get_attribute(self, name: str) -> Optional[AttributeDef]:
        for attrs in self.attributes.values():
            for attr in attrs:
                if attr.name == name:
                    return attr
        return None

    def find_attribute_by_description(self, description: str) -> Optional[AttributeDef]:
        target = description.strip().lower()
        for attr in self.all_attributes():
            if attr.description.strip().lower() == target:
                return attr
        return None

    def categories(self) -> List[str]:
        return list(self.attributes.keys())


def load_offsets(filepath: str) -> OffsetConfig:
    with open(filepath, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    config = OffsetConfig()
    config.version = data.get("version", "")
    config.game_version = data.get("game_version", "")

    player_table = data.get("player_table", {})
    config.player_table = PlayerTableDef(
        signature=player_table.get("signature", ""),
        base_pointer=player_table.get("base_pointer", 0),
        pointer_offsets=player_table.get("pointer_offsets", []),
        stride=player_table.get("stride", 1176),
        count_offset=player_table.get("count_offset", 0),
        max_players=player_table.get("max_players", 600),
        name_offset=player_table.get("name_offset", 0),
        first_name_offset=player_table.get("first_name_offset", 40),
        last_name_offset=player_table.get("last_name_offset", 0),
        team_id_offset=player_table.get("team_id_offset", -1),
        name_string_length=player_table.get("name_string_length", 20),
        direct_table=player_table.get("direct_table", True),
    )

    team_table = data.get("team_table", {})
    config.team_table = TeamTableDef(
        base_pointer=team_table.get("base_pointer", 0),
        stride=team_table.get("stride", 5672),
        team_name_offset=team_table.get("team_name_offset", 738),
        team_name_length=team_table.get("team_name_length", 24),
        max_teams=team_table.get("max_teams", 64),
    )

    for category, attr_list in data.get("attributes", {}).items():
        defs: List[AttributeDef] = []
        for item in attr_list:
            defs.append(
                AttributeDef(
                    name=item["name"],
                    offset=item["offset"],
                    type=item.get("type", "uint8"),
                    bit_start=item.get("bit_start", 0),
                    bit_length=item.get("bit_length", 0),
                    min_val=item.get("min", 0),
                    max_val=item.get("max", 99),
                    category=category,
                    string_length=item.get("string_length", 32),
                    description=item.get("description", ""),
                )
            )
        config.attributes[category] = defs

    return config


def get_default_offsets_path() -> str:
    import sys

    if getattr(sys, "_MEIPASS", None):
        return os.path.join(sys._MEIPASS, "config", "offsets_2k26.json")

    exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    candidate = os.path.join(exe_dir, "config", "offsets_2k26.json")
    if os.path.exists(candidate):
        return candidate

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_dir, "config", "offsets_2k26.json")


_current_config: Optional[OffsetConfig] = None


def initialize_offsets(filepath: Optional[str] = None) -> OffsetConfig:
    global _current_config

    if filepath is None:
        filepath = get_default_offsets_path()

    _current_config = load_offsets(filepath)
    return _current_config


def get_offsets() -> Optional[OffsetConfig]:
    return _current_config
