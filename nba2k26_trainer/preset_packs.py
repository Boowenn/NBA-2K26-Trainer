"""Team preset pack helpers for scope-wide roster identities."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .core.offsets import OffsetConfig
from .presets import get_builtin_preset, resolve_preset_values


PRESET_PACK_FILE_VERSION = 1
TEAM_PACK_ANALYSIS_MAX_AGE = 40
TEAM_PACK_ANALYSIS_MIN_POTENTIAL = 0


@dataclass(frozen=True)
class PresetPackRule:
    rule_id: str
    name: str
    description: str
    preset_id: str = ""
    preset_name: str = ""
    values_by_description: Dict[str, Any] = field(default_factory=dict)
    positions: Tuple[str, ...] = ()
    role_tracks: Tuple[str, ...] = ()
    growth_plans: Tuple[str, ...] = ()
    tiers: Tuple[str, ...] = ()
    min_age: Optional[int] = None
    max_age: Optional[int] = None
    min_overall: Optional[int] = None
    max_overall: Optional[int] = None
    min_potential: Optional[int] = None
    max_potential: Optional[int] = None
    min_score: Optional[float] = None
    max_score: Optional[float] = None
    max_players: Optional[int] = None


@dataclass(frozen=True)
class PresetPackDefinition:
    pack_id: str
    name: str
    description: str
    rules: Tuple[PresetPackRule, ...]


BUILTIN_PRESET_PACKS: Tuple[PresetPackDefinition, ...] = (
    PresetPackDefinition(
        pack_id="rebuild_identity_pack",
        name="Rebuild Identity Pack",
        description=(
            "A young-core pack for rebuild saves. It boosts cornerstone prospects first, then gives "
            "qualified wings and guards a clearer role identity without touching every veteran in scope."
        ),
        rules=(
            PresetPackRule(
                rule_id="core_ceiling",
                name="Core Ceiling",
                description="Push the best young franchise bets toward a real rebuild timeline.",
                preset_id="franchise_prospect",
                growth_plans=("Hold Ceiling", "Franchise Prospect"),
                tiers=("Blue Chip", "Starter Bet"),
                max_age=25,
                max_players=6,
            ),
            PresetPackRule(
                rule_id="spacing_wings",
                name="Spacing Wings",
                description="Turn qualified perimeter wings into floor spacers.",
                preset_id="sniper_wing",
                positions=("SG", "SF", "PF"),
                role_tracks=("Sniper Wing",),
                min_overall=70,
                max_age=30,
                max_players=5,
            ),
            PresetPackRule(
                rule_id="downhill_creation",
                name="Downhill Creation",
                description="Add burst and rim pressure to young creators who already profile that way.",
                preset_id="rim_pressure_slasher",
                positions=("PG", "SG", "SF"),
                role_tracks=("Rim Pressure Slasher",),
                min_overall=72,
                max_age=27,
                max_players=4,
            ),
            PresetPackRule(
                rule_id="perimeter_stoppers",
                name="Perimeter Stoppers",
                description="Lock in point-of-attack defenders for the rebuild shell.",
                preset_id="two_way_stopper",
                positions=("SG", "SF", "PF"),
                role_tracks=("Two-Way Stopper",),
                min_overall=72,
                max_age=30,
                max_players=4,
            ),
        ),
    ),
    PresetPackDefinition(
        pack_id="draft_class_template_pack",
        name="Draft Class Template Pack",
        description=(
            "A pack for draft classes or youth-heavy scopes. It pushes upside tiers first, then applies "
            "role templates to the prospects who already show a clean style."
        ),
        rules=(
            PresetPackRule(
                rule_id="lottery_ceiling",
                name="Lottery Ceiling",
                description="Reserve growth tuning for the most promising young prospects.",
                preset_id="franchise_prospect",
                growth_plans=("Hold Ceiling", "Franchise Prospect"),
                tiers=("Blue Chip", "Starter Bet", "Rotation Swing"),
                max_age=23,
                max_players=10,
            ),
            PresetPackRule(
                rule_id="draft_shooters",
                name="Draft Shooters",
                description="Sharpen the cleanest young spacing bets.",
                preset_id="sniper_wing",
                positions=("SG", "SF", "PF"),
                role_tracks=("Sniper Wing",),
                max_age=24,
                max_players=8,
            ),
            PresetPackRule(
                rule_id="draft_slashers",
                name="Draft Slashers",
                description="Give attacking guards and wings a reusable rim-pressure template.",
                preset_id="rim_pressure_slasher",
                positions=("PG", "SG", "SF"),
                role_tracks=("Rim Pressure Slasher",),
                max_age=24,
                max_players=6,
            ),
            PresetPackRule(
                rule_id="draft_defenders",
                name="Draft Defenders",
                description="Solidify 3-and-D or point-of-attack defender archetypes.",
                preset_id="two_way_stopper",
                positions=("SG", "SF", "PF"),
                role_tracks=("Two-Way Stopper",),
                max_age=24,
                max_players=6,
            ),
        ),
    ),
    PresetPackDefinition(
        pack_id="rotation_identity_pack",
        name="Rotation Identity Pack",
        description=(
            "A safer role-template pack for established teams. It skips growth-only moves and just applies "
            "role presets to qualified rotation pieces inside the current scope."
        ),
        rules=(
            PresetPackRule(
                rule_id="rotation_shooters",
                name="Rotation Shooters",
                description="Add repeatable spacing to live rotation wings.",
                preset_id="sniper_wing",
                positions=("SG", "SF", "PF"),
                role_tracks=("Sniper Wing",),
                tiers=("Blue Chip", "Starter Bet", "Rotation Swing"),
                min_overall=72,
                max_age=33,
                max_players=6,
            ),
            PresetPackRule(
                rule_id="rotation_slashers",
                name="Rotation Slashers",
                description="Boost downhill pressure for guards and wings that already play that style.",
                preset_id="rim_pressure_slasher",
                positions=("PG", "SG", "SF"),
                role_tracks=("Rim Pressure Slasher",),
                tiers=("Blue Chip", "Starter Bet", "Rotation Swing"),
                min_overall=72,
                max_age=32,
                max_players=4,
            ),
            PresetPackRule(
                rule_id="rotation_stoppers",
                name="Rotation Stoppers",
                description="Harden defensive wings and combo forwards.",
                preset_id="two_way_stopper",
                positions=("SG", "SF", "PF"),
                role_tracks=("Two-Way Stopper",),
                tiers=("Blue Chip", "Starter Bet", "Rotation Swing"),
                min_overall=72,
                max_age=33,
                max_players=5,
            ),
        ),
    ),
)


def builtin_preset_packs() -> List[PresetPackDefinition]:
    return list(BUILTIN_PRESET_PACKS)


def get_builtin_preset_pack(pack_id: str) -> Optional[PresetPackDefinition]:
    for pack in BUILTIN_PRESET_PACKS:
        if pack.pack_id == pack_id:
            return pack
    return None


def _normalize_tuple(values: Any, *, upper: bool = False) -> Tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        raw_values: Iterable[Any] = [values]
    elif isinstance(values, (list, tuple, set)):
        raw_values = values
    else:
        return ()

    normalized: List[str] = []
    for raw_value in raw_values:
        text = str(raw_value or "").strip()
        if not text:
            continue
        normalized.append(text.upper() if upper else text)
    return tuple(normalized)


def _optional_int(value: Any) -> Optional[int]:
    if value in (None, "", False):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> Optional[float]:
    if value in (None, "", False):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _player_identity(player_entry: Dict[str, Any]) -> str:
    player_key = str(player_entry.get("player_key") or "").strip()
    if player_key:
        return player_key
    return "|".join(
        [
            str(player_entry.get("index", "")),
            str(player_entry.get("full_name") or "").strip().lower(),
            str(player_entry.get("birth_year") or 0),
            str(player_entry.get("position") or "").strip().upper(),
        ]
    )


def _rule_filter_text(rule: PresetPackRule) -> str:
    filters: List[str] = []
    if rule.positions:
        filters.append("pos " + "/".join(rule.positions))
    if rule.role_tracks:
        filters.append("roles " + ", ".join(rule.role_tracks))
    if rule.growth_plans:
        filters.append("growth " + ", ".join(rule.growth_plans))
    if rule.tiers:
        filters.append("tiers " + ", ".join(rule.tiers))
    if rule.min_age is not None or rule.max_age is not None:
        lower = rule.min_age if rule.min_age is not None else "*"
        upper = rule.max_age if rule.max_age is not None else "*"
        filters.append(f"age {lower}-{upper}")
    if rule.min_overall is not None or rule.max_overall is not None:
        lower = rule.min_overall if rule.min_overall is not None else "*"
        upper = rule.max_overall if rule.max_overall is not None else "*"
        filters.append(f"ovr {lower}-{upper}")
    if rule.min_potential is not None or rule.max_potential is not None:
        lower = rule.min_potential if rule.min_potential is not None else "*"
        upper = rule.max_potential if rule.max_potential is not None else "*"
        filters.append(f"pot {lower}-{upper}")
    if rule.min_score is not None or rule.max_score is not None:
        lower = f"{rule.min_score:.1f}" if rule.min_score is not None else "*"
        upper = f"{rule.max_score:.1f}" if rule.max_score is not None else "*"
        filters.append(f"score {lower}-{upper}")
    if rule.max_players is not None:
        filters.append(f"limit {rule.max_players}")
    return "; ".join(filters) if filters else "scope-wide"


def _resolve_rule_values(
    config: OffsetConfig,
    rule: PresetPackRule,
) -> Tuple[str, Dict[str, Any], List[str], str]:
    if rule.values_by_description:
        preset_name = rule.preset_name.strip() or rule.name
        resolved, unresolved = resolve_preset_values(config, rule.values_by_description)
        return preset_name, resolved, unresolved, "inline"

    builtin = get_builtin_preset(rule.preset_id)
    if builtin is None:
        return rule.preset_name.strip() or rule.preset_id or rule.name, {}, [rule.preset_id or "<missing preset>"], "missing"

    resolved, unresolved = resolve_preset_values(config, builtin.values_by_description)
    return builtin.name, resolved, unresolved, "builtin"


def inspect_preset_pack(config: OffsetConfig, pack: PresetPackDefinition) -> Dict[str, Any]:
    rules: List[Dict[str, Any]] = []
    total_mapped = 0
    total_unresolved = 0

    for rule in pack.rules:
        preset_name, values, unresolved, source = _resolve_rule_values(config, rule)
        total_mapped += len(values)
        total_unresolved += len(unresolved)
        rules.append(
            {
                "rule_id": rule.rule_id,
                "rule_name": rule.name,
                "preset_name": preset_name,
                "mapped_count": len(values),
                "unresolved": list(unresolved),
                "source": source,
                "filter_text": _rule_filter_text(rule),
            }
        )

    return {
        "pack_id": pack.pack_id,
        "pack_name": pack.name,
        "description": pack.description,
        "rule_count": len(pack.rules),
        "total_mapped": total_mapped,
        "total_unresolved": total_unresolved,
        "rules": rules,
    }


def format_preset_pack_preview(
    config: OffsetConfig,
    pack: PresetPackDefinition,
    *,
    max_rules: int = 6,
) -> str:
    inspection = inspect_preset_pack(config, pack)
    lines = [
        pack.description,
        f"Rules: {inspection['rule_count']}",
        f"Mapped attributes across rules: {inspection['total_mapped']}",
    ]
    if inspection["total_unresolved"]:
        lines.append(f"Unresolved attributes: {inspection['total_unresolved']}")
    lines.extend(["", "Rule Preview"])

    for rule in inspection["rules"][:max_rules]:
        lines.append(
            f"- {rule['rule_name']} -> {rule['preset_name']} ({rule['mapped_count']} attrs, {rule['filter_text']})"
        )
    if len(inspection["rules"]) > max_rules:
        lines.append(f"- ... and {len(inspection['rules']) - max_rules} more rules")

    lines.extend(
        [
            "",
            "First-match wins when a player qualifies for multiple rules.",
        ]
    )
    return "\n".join(lines)


def _matches_optional_range(value: float, lower: Optional[float], upper: Optional[float]) -> bool:
    if lower is not None and value < lower:
        return False
    if upper is not None and value > upper:
        return False
    return True


def _rule_matches_player(rule: PresetPackRule, player_entry: Dict[str, Any]) -> bool:
    position = str(player_entry.get("position") or "").strip().upper()
    role_track = str(player_entry.get("role_track") or "").strip()
    growth_plan = str(player_entry.get("growth_plan") or "").strip()
    tier = str(player_entry.get("tier") or "").strip()
    age = int(player_entry.get("age") or 0)
    overall = int(player_entry.get("overall") or 0)
    potential = int(player_entry.get("potential") or 0)
    score = float(player_entry.get("prospect_score") or 0.0)

    if rule.positions and position not in rule.positions:
        return False
    if rule.role_tracks and role_track not in rule.role_tracks:
        return False
    if rule.growth_plans and growth_plan not in rule.growth_plans:
        return False
    if rule.tiers and tier not in rule.tiers:
        return False
    if not _matches_optional_range(age, rule.min_age, rule.max_age):
        return False
    if not _matches_optional_range(overall, rule.min_overall, rule.max_overall):
        return False
    if not _matches_optional_range(potential, rule.min_potential, rule.max_potential):
        return False
    if not _matches_optional_range(score, rule.min_score, rule.max_score):
        return False
    return True


def plan_preset_pack_application(
    config: OffsetConfig,
    board: Dict[str, Any],
    pack: PresetPackDefinition,
) -> Dict[str, Any]:
    players = list(board.get("players", []) or [])
    assigned_identities = set()
    assignments: List[Dict[str, Any]] = []
    rules: List[Dict[str, Any]] = []
    invalid_rules: List[Dict[str, Any]] = []

    for rule in pack.rules:
        preset_name, values, unresolved, source = _resolve_rule_values(config, rule)
        if not values:
            invalid_rules.append(
                {
                    "rule_name": rule.name,
                    "preset_name": preset_name,
                    "source": source,
                    "unresolved": list(unresolved),
                }
            )
            continue

        matched_players = [
            player_entry
            for player_entry in players
            if _player_identity(player_entry) not in assigned_identities and _rule_matches_player(rule, player_entry)
        ]
        if rule.max_players is not None:
            matched_players = matched_players[: rule.max_players]

        for player_entry in matched_players:
            identity = _player_identity(player_entry)
            assigned_identities.add(identity)
            assignments.append(
                {
                    "player_key": identity,
                    "index": int(player_entry.get("index", -1)),
                    "full_name": str(player_entry.get("full_name") or "Unknown Player"),
                    "team_name": str(player_entry.get("team_name") or "Unassigned"),
                    "position": str(player_entry.get("position") or "?"),
                    "age": int(player_entry.get("age") or 0),
                    "overall": int(player_entry.get("overall") or 0),
                    "potential": int(player_entry.get("potential") or 0),
                    "prospect_score": float(player_entry.get("prospect_score") or 0.0),
                    "tier": str(player_entry.get("tier") or ""),
                    "growth_plan": str(player_entry.get("growth_plan") or ""),
                    "role_track": str(player_entry.get("role_track") or ""),
                    "rule_name": rule.name,
                    "preset_name": preset_name,
                    "filter_text": _rule_filter_text(rule),
                    "resolved_values": dict(values),
                    "unresolved": list(unresolved),
                }
            )

        rules.append(
            {
                "rule_name": rule.name,
                "preset_name": preset_name,
                "filter_text": _rule_filter_text(rule),
                "matched_count": len(matched_players),
                "mapped_count": len(values),
                "unresolved_count": len(unresolved),
            }
        )

    unmatched_players = [
        player_entry
        for player_entry in players
        if _player_identity(player_entry) not in assigned_identities
    ]

    return {
        "pack_id": pack.pack_id,
        "pack_name": pack.name,
        "pack_description": pack.description,
        "scope_name": board.get("scope_name") or "Current Scope",
        "player_count": len(players),
        "assigned_player_count": len(assignments),
        "unmatched_player_count": len(unmatched_players),
        "total_attribute_targets": sum(len(item["resolved_values"]) for item in assignments),
        "rules": rules,
        "invalid_rules": invalid_rules,
        "assignments": assignments,
        "unmatched_players": unmatched_players,
    }


def format_preset_pack_plan(plan: Dict[str, Any], *, max_players: int = 8) -> str:
    lines = [
        f"Preset Pack: {plan.get('pack_name', 'Preset Pack')}",
        str(plan.get("pack_description") or "").strip(),
        "",
        f"Scope: {plan.get('scope_name', 'Current Scope')}",
        f"Analyzed players: {int(plan.get('player_count') or 0)}",
        f"Assigned players: {int(plan.get('assigned_player_count') or 0)}",
        f"Unmatched players: {int(plan.get('unmatched_player_count') or 0)}",
        f"Planned attribute writes: {int(plan.get('total_attribute_targets') or 0)}",
    ]

    rules = list(plan.get("rules", []) or [])
    if rules:
        lines.extend(["", "Rule Hits"])
        for rule in rules:
            lines.append(
                f"- {rule['rule_name']} -> {rule['preset_name']}: {rule['matched_count']} players ({rule['filter_text']})"
            )

    assignments = list(plan.get("assignments", []) or [])
    if assignments:
        lines.extend(["", "Preview"])
        for assignment in assignments[:max_players]:
            lines.append(
                f"- {assignment['full_name']} ({assignment['team_name']}, {assignment['position']}) -> "
                f"{assignment['preset_name']} via {assignment['rule_name']}"
            )
        if len(assignments) > max_players:
            lines.append(f"- ... and {len(assignments) - max_players} more players")

    invalid_rules = list(plan.get("invalid_rules", []) or [])
    if invalid_rules:
        lines.extend(["", "Skipped Rules"])
        for rule in invalid_rules:
            lines.append(f"- {rule['rule_name']} -> {rule['preset_name']}: no writable attributes resolved")

    return "\n".join(line for line in lines if line is not None)


def save_preset_pack(filepath: str, pack: PresetPackDefinition) -> None:
    payload = {
        "format_version": PRESET_PACK_FILE_VERSION,
        "pack_id": pack.pack_id,
        "name": pack.name,
        "description": pack.description,
        "rules": [
            {
                "rule_id": rule.rule_id,
                "name": rule.name,
                "description": rule.description,
                "preset_id": rule.preset_id,
                "preset_name": rule.preset_name,
                "values_by_description": dict(rule.values_by_description),
                "positions": list(rule.positions),
                "role_tracks": list(rule.role_tracks),
                "growth_plans": list(rule.growth_plans),
                "tiers": list(rule.tiers),
                "min_age": rule.min_age,
                "max_age": rule.max_age,
                "min_overall": rule.min_overall,
                "max_overall": rule.max_overall,
                "min_potential": rule.min_potential,
                "max_potential": rule.max_potential,
                "min_score": rule.min_score,
                "max_score": rule.max_score,
                "max_players": rule.max_players,
            }
            for rule in pack.rules
        ],
    }

    with open(filepath, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _load_rule_values_map(entry: Dict[str, Any]) -> Dict[str, Any]:
    values_map = entry.get("values_by_description")
    if isinstance(values_map, dict):
        return {str(key): value for key, value in values_map.items()}

    values = entry.get("values")
    if isinstance(values, dict):
        return {str(key): value for key, value in values.items()}
    if not isinstance(values, list):
        return {}

    mapped: Dict[str, Any] = {}
    for value_entry in values:
        if not isinstance(value_entry, dict):
            continue
        key = value_entry.get("description") or value_entry.get("name")
        if not key:
            continue
        mapped[str(key)] = value_entry.get("value")
    return mapped


def load_preset_pack(filepath: str) -> PresetPackDefinition:
    with open(filepath, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    raw_rules = data.get("rules")
    if not isinstance(raw_rules, list) or not raw_rules:
        raise ValueError("Preset pack file does not contain any rules.")

    rules: List[PresetPackRule] = []
    for index, raw_rule in enumerate(raw_rules, start=1):
        if not isinstance(raw_rule, dict):
            continue

        name = str(raw_rule.get("name") or "").strip()
        if not name:
            raise ValueError(f"Preset pack rule #{index} is missing a name.")

        values_by_description = _load_rule_values_map(raw_rule)
        preset_id = str(raw_rule.get("preset_id") or "").strip()
        if not preset_id and not values_by_description:
            raise ValueError(
                f"Preset pack rule '{name}' must define either a preset_id or inline values_by_description."
            )

        rules.append(
            PresetPackRule(
                rule_id=str(raw_rule.get("rule_id") or f"custom_rule_{index}").strip() or f"custom_rule_{index}",
                name=name,
                description=str(raw_rule.get("description") or "").strip(),
                preset_id=preset_id,
                preset_name=str(raw_rule.get("preset_name") or "").strip(),
                values_by_description=values_by_description,
                positions=_normalize_tuple(raw_rule.get("positions"), upper=True),
                role_tracks=_normalize_tuple(raw_rule.get("role_tracks")),
                growth_plans=_normalize_tuple(raw_rule.get("growth_plans")),
                tiers=_normalize_tuple(raw_rule.get("tiers")),
                min_age=_optional_int(raw_rule.get("min_age")),
                max_age=_optional_int(raw_rule.get("max_age")),
                min_overall=_optional_int(raw_rule.get("min_overall")),
                max_overall=_optional_int(raw_rule.get("max_overall")),
                min_potential=_optional_int(raw_rule.get("min_potential")),
                max_potential=_optional_int(raw_rule.get("max_potential")),
                min_score=_optional_float(raw_rule.get("min_score")),
                max_score=_optional_float(raw_rule.get("max_score")),
                max_players=_optional_int(raw_rule.get("max_players")),
            )
        )

    if not rules:
        raise ValueError("Preset pack file does not contain any usable rules.")

    return PresetPackDefinition(
        pack_id=str(data.get("pack_id") or "custom_pack").strip() or "custom_pack",
        name=str(data.get("name") or "Custom Preset Pack").strip() or "Custom Preset Pack",
        description=str(data.get("description") or "").strip(),
        rules=tuple(rules),
    )
