"""球队数据模型"""

from dataclasses import dataclass
from typing import List
from .player import TEAM_NAMES


@dataclass
class Team:
    team_id: int
    name: str


def get_all_teams() -> List[Team]:
    """获取所有 NBA 球队"""
    teams = [Team(team_id=tid, name=name) for tid, name in sorted(TEAM_NAMES.items())]
    return teams
