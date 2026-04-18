"""Preset definitions and import/export helpers for reusable roster edits."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple

from .core.offsets import OffsetConfig


PRESET_FILE_VERSION = 1


@dataclass(frozen=True)
class PresetDefinition:
    preset_id: str
    name: str
    description: str
    values_by_description: Dict[str, Any]


BUILTIN_PRESETS: Tuple[PresetDefinition, ...] = (
    PresetDefinition(
        preset_id="sniper_wing",
        name="Sniper Wing",
        description=(
            "A shooting-first wing preset for spacing lineups. It boosts perimeter scoring, "
            "off-ball badges, and the shot tendencies that make a player behave like a true spacer."
        ),
        values_by_description={
            "Close Shot": 85,
            "Mid-Range Shot": 92,
            "Three-Point Shot": 99,
            "Free Throw": 90,
            "Ball Control": 82,
            "Pass Accuracy": 80,
            "Speed": 85,
            "Speed with Ball": 84,
            "Shot IQ": 97,
            "Offensive Consistency": 95,
            "Deadeye": 4,
            "Limitless Range": 4,
            "Mini Marksman": 4,
            "Shifty Shooter": 4,
            "Slippery Off-Ball": 4,
            "Shot 3pt": 99,
            "Contested 3pt": 85,
            "Off Screen 3pt": 95,
            "Stepback 3pt": 90,
            "Transition Pull Up 3pt": 90,
        },
    ),
    PresetDefinition(
        preset_id="rim_pressure_slasher",
        name="Rim Pressure Slasher",
        description=(
            "Built for downhill scorers. It prioritizes burst, finishing badges, and aggressive drive "
            "tendencies instead of turning every player into a full god-mode clone."
        ),
        values_by_description={
            "Close Shot": 90,
            "Driving Layup": 98,
            "Driving Dunk": 96,
            "Standing Dunk": 75,
            "Ball Control": 88,
            "Pass Accuracy": 82,
            "Speed": 92,
            "Speed with Ball": 94,
            "Vertical": 92,
            "Strength": 80,
            "Shot IQ": 88,
            "Aerial Wizard": 4,
            "Layup Mix Master": 4,
            "Physical Finisher": 4,
            "Posterizer": 4,
            "Rise Up": 3,
            "Driving Layup Tendency": 99,
            "Driving Dunk Tendency": 99,
            "Flashy Dunk": 85,
            "Drive": 99,
            "Spot Up Drive": 90,
            "Attack Strong": 99,
        },
    ),
    PresetDefinition(
        preset_id="two_way_stopper",
        name="Two-Way Stopper",
        description=(
            "A balanced wing stopper preset. It hardens point-of-attack defense, creates turnovers, "
            "and keeps enough shooting to stay playable in MyGM rotations."
        ),
        values_by_description={
            "Close Shot": 78,
            "Mid-Range Shot": 82,
            "Three-Point Shot": 86,
            "Interior Defense": 88,
            "Perimeter Defense": 97,
            "Pass Perception": 95,
            "Steal": 96,
            "Block": 82,
            "Defensive Rebound": 82,
            "Strength": 84,
            "Speed": 88,
            "Stamina": 96,
            "Shot IQ": 88,
            "Offensive Consistency": 85,
            "On Ball Steal": 99,
            "Pass Interception": 99,
            "Contest Shot": 99,
            "Foul": 15,
            "Hard Foul": 20,
        },
    ),
    PresetDefinition(
        preset_id="franchise_prospect",
        name="Franchise Prospect",
        description=(
            "Growth-oriented tuning for rebuild saves. It upgrades long-term ceiling and peak years "
            "without mutating contracts or cosmetic roster data."
        ),
        values_by_description={
            "Potential": 95,
            "Avg Potential %": 94,
            "Boom % (positive growth)": 92,
            "Bust % (negative growth)": 8,
            "Min Potential": 90,
            "Max Potential": 99,
            "Peak Start Age": 27,
            "Peak End Age": 34,
            "Offensive Consistency": 88,
            "Stamina": 92,
        },
    ),
)


def builtin_presets() -> List[PresetDefinition]:
    return list(BUILTIN_PRESETS)


def get_builtin_preset(preset_id: str) -> PresetDefinition | None:
    for preset in BUILTIN_PRESETS:
        if preset.preset_id == preset_id:
            return preset
    return None


def _find_attr_for_key(config: OffsetConfig, key: str):
    return config.find_attribute_by_description(key) or config.get_attribute(key)


def resolve_preset_values(
    config: OffsetConfig,
    values_by_description: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    resolved: Dict[str, Any] = {}
    unresolved: List[str] = []

    for key, raw_value in values_by_description.items():
        attr = _find_attr_for_key(config, key)
        if attr is None or attr.type in ("wstring", "ascii"):
            unresolved.append(str(key))
            continue

        try:
            if attr.type == "float":
                numeric_value = float(raw_value)
            else:
                numeric_value = int(raw_value)
        except (TypeError, ValueError):
            unresolved.append(str(key))
            continue

        numeric_value = max(attr.min_val, min(attr.max_val, numeric_value))
        resolved[attr.name] = numeric_value

    return resolved, unresolved


def export_custom_preset(
    filepath: str,
    name: str,
    config: OffsetConfig,
    values_by_attr_name: Dict[str, Any],
    *,
    description: str = "",
) -> None:
    entries: List[Dict[str, Any]] = []
    for attr_name, raw_value in sorted(values_by_attr_name.items()):
        attr = _find_attr_for_key(config, attr_name)
        if attr is None or attr.type in ("wstring", "ascii"):
            continue

        value = float(raw_value) if attr.type == "float" else int(raw_value)
        entries.append(
            {
                "name": attr.name,
                "description": attr.description or attr.name,
                "category": attr.category,
                "value": value,
            }
        )

    payload = {
        "format_version": PRESET_FILE_VERSION,
        "name": name.strip() or "Custom Preset",
        "description": description.strip(),
        "values": entries,
    }

    with open(filepath, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def load_custom_preset(filepath: str) -> PresetDefinition:
    with open(filepath, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    entries = data.get("values")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Preset file does not contain any attribute values.")

    values_by_description: Dict[str, Any] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        key = entry.get("description") or entry.get("name")
        if not key:
            continue
        values_by_description[str(key)] = entry.get("value", 0)

    if not values_by_description:
        raise ValueError("Preset file does not contain any usable attribute mappings.")

    name = str(data.get("name") or "Custom Preset").strip() or "Custom Preset"
    description = str(data.get("description") or "").strip()

    return PresetDefinition(
        preset_id="custom_file",
        name=name,
        description=description or "Imported from a preset JSON file.",
        values_by_description=values_by_description,
    )


def summarize_preset_values(values_by_description: Iterable[str], max_items: int = 6) -> str:
    items = [str(item) for item in values_by_description]
    preview = ", ".join(items[:max_items])
    if len(items) > max_items:
        preview += ", ..."
    return preview
