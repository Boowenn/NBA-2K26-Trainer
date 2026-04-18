"""Prospect board analysis and trend helpers built on top of roster snapshots."""

from __future__ import annotations

import csv
from collections import Counter
from typing import Any, Dict, List, Sequence


DEFAULT_MAX_AGE = 24
DEFAULT_MIN_POTENTIAL = 70
TREND_DELTA_THRESHOLD = 0.5


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


def _board_identity_key(player_entry: Dict[str, Any]) -> str:
    player_key = str(player_entry.get("player_key") or "").strip().lower()
    if player_key:
        return player_key
    full_name = str(player_entry.get("full_name") or "").strip().lower()
    birth_year = _as_int(player_entry.get("birth_year"), 0)
    position = str(player_entry.get("position") or "").strip().lower()
    return f"{full_name}|{birth_year}|{position}"


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
        birth_year = _as_int(player_entry.get("birth_year"), 0)
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
            "birth_year": birth_year,
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

    average_score = round(
        sum(float(item["prospect_score"]) for item in entries) / len(entries),
        1,
    ) if entries else 0.0
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


def compare_prospect_boards(left_board: Dict[str, Any], right_board: Dict[str, Any]) -> Dict[str, Any]:
    left_players = {
        _board_identity_key(player): player
        for player in left_board.get("players", []) or []
    }
    right_players = {
        _board_identity_key(player): player
        for player in right_board.get("players", []) or []
    }

    left_keys = set(left_players.keys())
    right_keys = set(right_players.keys())

    added = [right_players[key] for key in sorted(right_keys - left_keys)]
    removed = [left_players[key] for key in sorted(left_keys - right_keys)]
    changed: List[Dict[str, Any]] = []
    risers: List[Dict[str, Any]] = []
    fallers: List[Dict[str, Any]] = []
    stable: List[Dict[str, Any]] = []

    for key in sorted(left_keys & right_keys):
        left_player = left_players[key]
        right_player = right_players[key]
        score_delta = round(float(right_player["prospect_score"]) - float(left_player["prospect_score"]), 1)
        overall_delta = int(right_player["overall"]) - int(left_player["overall"])
        potential_delta = int(right_player["potential"]) - int(left_player["potential"])
        average_potential_delta = int(right_player["average_potential"]) - int(left_player["average_potential"])
        boom_delta = int(right_player["boom"]) - int(left_player["boom"])
        bust_delta = int(right_player["bust"]) - int(left_player["bust"])
        age_delta = int(right_player["age"]) - int(left_player["age"])
        development_gap_delta = int(right_player["development_gap"]) - int(left_player["development_gap"])

        status = "Stable"
        if score_delta >= TREND_DELTA_THRESHOLD:
            status = "Riser"
        elif score_delta <= -TREND_DELTA_THRESHOLD:
            status = "Faller"

        notes: List[str] = []
        if potential_delta > 0:
            notes.append(f"potential +{potential_delta}")
        elif potential_delta < 0:
            notes.append(f"potential {potential_delta}")
        if overall_delta > 0:
            notes.append(f"overall +{overall_delta}")
        elif overall_delta < 0:
            notes.append(f"overall {overall_delta}")
        if boom_delta > 0:
            notes.append(f"boom +{boom_delta}")
        elif boom_delta < 0:
            notes.append(f"boom {boom_delta}")
        if bust_delta < 0:
            notes.append(f"bust {bust_delta}")
        elif bust_delta > 0:
            notes.append(f"bust +{bust_delta}")
        if left_player["tier"] != right_player["tier"]:
            notes.append(f"tier {left_player['tier']} -> {right_player['tier']}")
        if left_player["growth_plan"] != right_player["growth_plan"]:
            notes.append(f"growth {left_player['growth_plan']} -> {right_player['growth_plan']}")
        if left_player["role_track"] != right_player["role_track"]:
            notes.append(f"role {left_player['role_track']} -> {right_player['role_track']}")
        if age_delta > 0:
            notes.append(f"age +{age_delta}")
        if not notes:
            notes.append("no major profile changes")

        change_entry = {
            "player_key": key,
            "full_name": right_player["full_name"],
            "team_name": right_player["team_name"],
            "position": right_player["position"],
            "birth_year": right_player.get("birth_year", left_player.get("birth_year", 0)),
            "left_player": left_player,
            "right_player": right_player,
            "score_before": float(left_player["prospect_score"]),
            "score_after": float(right_player["prospect_score"]),
            "score_delta": score_delta,
            "overall_before": int(left_player["overall"]),
            "overall_after": int(right_player["overall"]),
            "overall_delta": overall_delta,
            "potential_before": int(left_player["potential"]),
            "potential_after": int(right_player["potential"]),
            "potential_delta": potential_delta,
            "average_potential_delta": average_potential_delta,
            "boom_delta": boom_delta,
            "bust_delta": bust_delta,
            "development_gap_delta": development_gap_delta,
            "tier_before": left_player["tier"],
            "tier_after": right_player["tier"],
            "growth_before": left_player["growth_plan"],
            "growth_after": right_player["growth_plan"],
            "role_before": left_player["role_track"],
            "role_after": right_player["role_track"],
            "status": status,
            "notes": ", ".join(notes),
        }
        changed.append(change_entry)
        if status == "Riser":
            risers.append(change_entry)
        elif status == "Faller":
            fallers.append(change_entry)
        else:
            stable.append(change_entry)

    added.sort(key=lambda item: (-float(item["prospect_score"]), str(item["full_name"]).lower()))
    removed.sort(key=lambda item: (-float(item["prospect_score"]), str(item["full_name"]).lower()))
    changed.sort(
        key=lambda item: (
            -abs(float(item["score_delta"])),
            -float(item["score_after"]),
            str(item["full_name"]).lower(),
        )
    )
    risers.sort(
        key=lambda item: (
            -float(item["score_delta"]),
            -float(item["score_after"]),
            str(item["full_name"]).lower(),
        )
    )
    fallers.sort(
        key=lambda item: (
            float(item["score_delta"]),
            -float(item["score_after"]),
            str(item["full_name"]).lower(),
        )
    )

    average_delta = round(
        sum(float(item["score_delta"]) for item in changed) / len(changed),
        1,
    ) if changed else 0.0
    return {
        "left_board": left_board,
        "right_board": right_board,
        "compared_count": len(changed),
        "added": added,
        "removed": removed,
        "changed": changed,
        "risers": risers,
        "fallers": fallers,
        "stable": stable,
        "average_score_delta": average_delta,
    }


def compare_prospect_snapshots(
    left_snapshot: Dict[str, Any],
    right_snapshot: Dict[str, Any],
    *,
    max_age: int = DEFAULT_MAX_AGE,
    min_potential: int = DEFAULT_MIN_POTENTIAL,
) -> Dict[str, Any]:
    left_board = analyze_prospect_snapshot(
        left_snapshot,
        max_age=max_age,
        min_potential=min_potential,
    )
    right_board = analyze_prospect_snapshot(
        right_snapshot,
        max_age=max_age,
        min_potential=min_potential,
    )
    return compare_prospect_boards(left_board, right_board)


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


def format_prospect_trend_report(trend: Dict[str, Any], *, max_players: int = 10) -> str:
    left_board = trend["left_board"]
    right_board = trend["right_board"]
    risers = trend["risers"]
    fallers = trend["fallers"]
    added = trend["added"]
    removed = trend["removed"]

    lines = [
        "Prospect Trend",
        "",
        f"Left:  {left_board.get('scope_name', 'Baseline')} | qualified {left_board.get('qualified_count', 0)} | avg {left_board.get('average_score', 0.0)}",
        f"Right: {right_board.get('scope_name', 'Latest')} | qualified {right_board.get('qualified_count', 0)} | avg {right_board.get('average_score', 0.0)}",
        "",
        f"Shared prospects: {trend.get('compared_count', 0)}",
        f"Average score delta: {trend.get('average_score_delta', 0.0):+.1f}",
        f"Risers: {len(risers)}",
        f"Fallers: {len(fallers)}",
        f"New entries: {len(added)}",
        f"Dropped prospects: {len(removed)}",
    ]

    if risers:
        lines.extend(["", "Top Risers"])
        for player in risers[:max_players]:
            lines.append(
                f"- {player['full_name']} ({player['team_name']}, {player['position']}) | "
                f"{player['score_delta']:+.1f} score | OVR {player['overall_delta']:+d} | POT {player['potential_delta']:+d}"
            )
            lines.append(
                f"  Tier {player['tier_before']} -> {player['tier_after']} | "
                f"Growth {player['growth_before']} -> {player['growth_after']} | {player['notes']}"
            )

    if fallers:
        lines.extend(["", "Top Fallers"])
        for player in fallers[:max_players]:
            lines.append(
                f"- {player['full_name']} ({player['team_name']}, {player['position']}) | "
                f"{player['score_delta']:+.1f} score | OVR {player['overall_delta']:+d} | POT {player['potential_delta']:+d}"
            )
            lines.append(
                f"  Tier {player['tier_before']} -> {player['tier_after']} | "
                f"Growth {player['growth_before']} -> {player['growth_after']} | {player['notes']}"
            )

    if added:
        lines.extend(["", "New Board Entries"])
        for player in added[:max_players]:
            lines.append(
                f"- {player['full_name']} ({player['team_name']}, {player['position']}) | "
                f"Score {player['prospect_score']} | {player['tier']} | {player['growth_plan']}"
            )

    if removed:
        lines.extend(["", "Dropped From Board"])
        for player in removed[:max_players]:
            lines.append(
                f"- {player['full_name']} ({player['team_name']}, {player['position']}) | "
                f"Score {player['prospect_score']} | {player['tier']} | {player['growth_plan']}"
            )

    if not risers and not fallers and not added and not removed:
        lines.extend(["", "No meaningful trend shifts found across the current filters."])

    return "\n".join(lines)


def export_prospect_board_csv(filepath: str, board: Dict[str, Any]) -> None:
    fieldnames: Sequence[str] = (
        "full_name",
        "team_name",
        "position",
        "age",
        "birth_year",
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


def export_prospect_trend_csv(filepath: str, trend: Dict[str, Any]) -> None:
    fieldnames: Sequence[str] = (
        "full_name",
        "team_name",
        "position",
        "status",
        "score_before",
        "score_after",
        "score_delta",
        "overall_before",
        "overall_after",
        "overall_delta",
        "potential_before",
        "potential_after",
        "potential_delta",
        "tier_before",
        "tier_after",
        "growth_before",
        "growth_after",
        "role_before",
        "role_after",
        "notes",
        "player_key",
    )

    rows: List[Dict[str, Any]] = []
    for change in trend.get("changed", []) or []:
        rows.append(
            {
                "full_name": change["full_name"],
                "team_name": change["team_name"],
                "position": change["position"],
                "status": change["status"],
                "score_before": change["score_before"],
                "score_after": change["score_after"],
                "score_delta": change["score_delta"],
                "overall_before": change["overall_before"],
                "overall_after": change["overall_after"],
                "overall_delta": change["overall_delta"],
                "potential_before": change["potential_before"],
                "potential_after": change["potential_after"],
                "potential_delta": change["potential_delta"],
                "tier_before": change["tier_before"],
                "tier_after": change["tier_after"],
                "growth_before": change["growth_before"],
                "growth_after": change["growth_after"],
                "role_before": change["role_before"],
                "role_after": change["role_after"],
                "notes": change["notes"],
                "player_key": change["player_key"],
            }
        )

    for player in trend.get("added", []) or []:
        rows.append(
            {
                "full_name": player["full_name"],
                "team_name": player["team_name"],
                "position": player["position"],
                "status": "New Entry",
                "score_before": "",
                "score_after": player["prospect_score"],
                "score_delta": "",
                "overall_before": "",
                "overall_after": player["overall"],
                "overall_delta": "",
                "potential_before": "",
                "potential_after": player["potential"],
                "potential_delta": "",
                "tier_before": "",
                "tier_after": player["tier"],
                "growth_before": "",
                "growth_after": player["growth_plan"],
                "role_before": "",
                "role_after": player["role_track"],
                "notes": "entered the filtered board",
                "player_key": _board_identity_key(player),
            }
        )

    for player in trend.get("removed", []) or []:
        rows.append(
            {
                "full_name": player["full_name"],
                "team_name": player["team_name"],
                "position": player["position"],
                "status": "Dropped",
                "score_before": player["prospect_score"],
                "score_after": "",
                "score_delta": "",
                "overall_before": player["overall"],
                "overall_after": "",
                "overall_delta": "",
                "potential_before": player["potential"],
                "potential_after": "",
                "potential_delta": "",
                "tier_before": player["tier"],
                "tier_after": "",
                "growth_before": player["growth_plan"],
                "growth_after": "",
                "role_before": player["role_track"],
                "role_after": "",
                "notes": "left the filtered board",
                "player_key": _board_identity_key(player),
            }
        )

    with open(filepath, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
