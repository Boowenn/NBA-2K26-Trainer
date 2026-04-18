"""Prospect board analysis helpers built on top of roster snapshots."""

from __future__ import annotations

import csv
from collections import Counter
from typing import Any, Dict, List, Sequence


DEFAULT_MAX_AGE = 24
DEFAULT_MIN_POTENTIAL = 70


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _as_int(value: Any, default: int = 0) -> int:
    return int(round(_as_float(value, default)))


def _player_attr(player_entry: Dict[str, Any], description: str, default: float = 0.0) -> float:
    attributes = player_entry.get("attributes", {}) or {}
    return _as_float(attributes.get(description, default), default)


def _age_score(age: int) -> float:
    if age <= 19:
        return 100.0
    if age >= 30:
        return 0.0
    return _clamp(100.0 - ((age - 19) * 9.0), 0.0, 100.0)


def _readiness_score(player_entry: Dict[str, Any]) -> float:
    samples = [
        _player_attr(player_entry, "Shot IQ", player_entry.get("overall", 0)),
        _player_attr(player_entry, "Offensive Consistency", player_entry.get("overall", 0)),
        _player_attr(player_entry, "Stamina", 70),
    ]
    valid = [sample for sample in samples if sample > 0]
    if not valid:
        return 0.0
    return sum(valid) / len(valid)


def _role_track(player_entry: Dict[str, Any]) -> str:
    shooting_score = (
        _player_attr(player_entry, "Three-Point Shot")
        + _player_attr(player_entry, "Mid-Range Shot")
        + _player_attr(player_entry, "Shot IQ")
    ) / 3.0
    finishing_score = (
        _player_attr(player_entry, "Driving Layup")
        + _player_attr(player_entry, "Driving Dunk")
        + _player_attr(player_entry, "Speed with Ball", _player_attr(player_entry, "Speed"))
    ) / 3.0
    defense_score = (
        _player_attr(player_entry, "Perimeter Defense")
        + _player_attr(player_entry, "Steal")
        + _player_attr(player_entry, "Pass Perception")
    ) / 3.0

    position = str(player_entry.get("position") or "").upper()
    if defense_score >= 84 and defense_score >= shooting_score and defense_score >= finishing_score:
        return "Two-Way Stopper"
    if finishing_score >= 86 and finishing_score >= shooting_score and position in {"PG", "SG", "SF", "PF"}:
        return "Rim Pressure Slasher"
    if shooting_score >= 84:
        return "Sniper Wing"
    return "Franchise Prospect"


def _growth_plan(player_entry: Dict[str, Any]) -> str:
    potential = _player_attr(player_entry, "Potential", player_entry.get("overall", 0))
    average_potential = _player_attr(player_entry, "Avg Potential %", potential)
    boom = _player_attr(player_entry, "Boom % (positive growth)", 50)
    bust = _player_attr(player_entry, "Bust % (negative growth)", 50)
    age = _as_int(player_entry.get("age"), 0)

    if potential >= 95 and average_potential >= 92 and bust <= 10 and age <= 22:
        return "Hold Ceiling"
    if boom >= 82 or potential >= 88:
        return "Franchise Prospect"
    return "Monitor"


def _tier_for_score(score: float) -> str:
    if score >= 88:
        return "Blue Chip"
    if score >= 80:
        return "Starter Bet"
    if score >= 72:
        return "Rotation Swing"
    return "Project"


def analyze_prospect_snapshot(
    snapshot: Dict[str, Any],
    *,
    max_age: int = DEFAULT_MAX_AGE,
    min_potential: int = DEFAULT_MIN_POTENTIAL,
) -> Dict[str, Any]:
    players = list(snapshot.get("players", []))
    entries: List[Dict[str, Any]] = []
    tier_counts: Counter[str] = Counter()
    role_track_counts: Counter[str] = Counter()

    for player_entry in players:
        age = _as_int(player_entry.get("age"), 0)
        overall = _as_int(player_entry.get("overall"), 0)
        potential = _as_int(_player_attr(player_entry, "Potential", overall), overall)
        average_potential = _as_int(_player_attr(player_entry, "Avg Potential %", potential), potential)
        boom = _as_int(_player_attr(player_entry, "Boom % (positive growth)", 50), 50)
        bust = _as_int(_player_attr(player_entry, "Bust % (negative growth)", 50), 50)
        readiness = _readiness_score(player_entry)
        age_factor = _age_score(age)
        bust_control = 100.0 - _clamp(float(bust), 0.0, 100.0)
        prospect_score = round(
            (potential * 0.34)
            + (overall * 0.18)
            + (age_factor * 0.16)
            + (average_potential * 0.12)
            + (boom * 0.10)
            + (bust_control * 0.06)
            + (readiness * 0.04),
            1,
        )
        development_gap = max(0, potential - overall)
        qualifies = age <= int(max_age) and potential >= int(min_potential)
        if not qualifies:
            continue

        tier = _tier_for_score(prospect_score)
        role_track = _role_track(player_entry)
        growth_plan = _growth_plan(player_entry)
        notes: List[str] = []
        if development_gap >= 12:
            notes.append("large ceiling gap")
        if boom >= 85:
            notes.append("high-growth profile")
        if bust <= 10:
            notes.append("low bust risk")
        if overall >= 78:
            notes.append("rotation ready")
        if not notes:
            notes.append("needs patient development")

        entry = {
            "player_key": player_entry.get("player_key") or "",
            "index": _as_int(player_entry.get("index"), -1),
            "full_name": str(player_entry.get("full_name") or "Unknown Player"),
            "team_name": str(player_entry.get("team_name") or "Unassigned"),
            "position": str(player_entry.get("position") or "?"),
            "age": age,
            "overall": overall,
            "potential": potential,
            "average_potential": average_potential,
            "boom": boom,
            "bust": bust,
            "development_gap": development_gap,
            "prospect_score": prospect_score,
            "tier": tier,
            "growth_plan": growth_plan,
            "role_track": role_track,
            "notes": ", ".join(notes),
        }
        entries.append(entry)
        tier_counts[tier] += 1
        role_track_counts[role_track] += 1

    entries.sort(
        key=lambda item: (
            -float(item["prospect_score"]),
            int(item["age"]),
            -int(item["potential"]),
            str(item["full_name"]).lower(),
        )
    )

    average_score = round(sum(float(item["prospect_score"]) for item in entries) / len(entries), 1) if entries else 0.0
    return {
        "scope_name": snapshot.get("scope_name") or "Current Scope",
        "source_created_at": snapshot.get("created_at") or "unknown time",
        "roster_mode": snapshot.get("roster_mode") or "auto",
        "player_count": len(players),
        "qualified_count": len(entries),
        "max_age": int(max_age),
        "min_potential": int(min_potential),
        "average_score": average_score,
        "tier_counts": dict(tier_counts),
        "role_track_counts": dict(role_track_counts.most_common()),
        "players": entries,
    }


def format_prospect_report(board: Dict[str, Any], *, max_players: int = 12) -> str:
    lines = [
        "Prospect Lab",
        "",
        f"Scope: {board.get('scope_name', 'Current Scope')}",
        f"Criteria: age <= {board.get('max_age', DEFAULT_MAX_AGE)}, potential >= {board.get('min_potential', DEFAULT_MIN_POTENTIAL)}",
        f"Qualified prospects: {board.get('qualified_count', 0)} / {board.get('player_count', 0)}",
        f"Average prospect score: {board.get('average_score', 0.0)}",
    ]

    tier_counts = board.get("tier_counts", {}) or {}
    if tier_counts:
        tier_text = ", ".join(f"{tier} ({count})" for tier, count in tier_counts.items())
        lines.append(f"Tiers: {tier_text}")

    role_track_counts = board.get("role_track_counts", {}) or {}
    if role_track_counts:
        role_text = ", ".join(f"{role} ({count})" for role, count in list(role_track_counts.items())[:4])
        lines.append(f"Role tracks: {role_text}")

    players = board.get("players", []) or []
    if not players:
        lines.extend(
            [
                "",
                "No prospects matched the current filters.",
                "Raise the age limit or lower the potential floor to widen the board.",
            ]
        )
        return "\n".join(lines)

    lines.extend(["", "Top Prospects"])
    for player in players[:max_players]:
        lines.append(
            f"- {player['full_name']} ({player['team_name']}, {player['position']}) | "
            f"Score {player['prospect_score']} | {player['tier']} | "
            f"Growth: {player['growth_plan']} | Role: {player['role_track']}"
        )
        lines.append(
            f"  Age {player['age']} | OVR {player['overall']} | POT {player['potential']} | "
            f"Boom {player['boom']} | Bust {player['bust']} | {player['notes']}"
        )

    return "\n".join(lines)


def export_prospect_board_csv(filepath: str, board: Dict[str, Any]) -> None:
    fieldnames: Sequence[str] = (
        "full_name",
        "team_name",
        "position",
        "age",
        "overall",
        "potential",
        "average_potential",
        "boom",
        "bust",
        "development_gap",
        "prospect_score",
        "tier",
        "growth_plan",
        "role_track",
        "notes",
        "index",
        "player_key",
    )

    with open(filepath, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for player in board.get("players", []) or []:
            writer.writerow({field: player.get(field, "") for field in fieldnames})
