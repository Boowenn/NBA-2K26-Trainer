"""Roster snapshot export and diff helpers."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from . import __version__
from .core.offsets import AttributeDef, OffsetConfig
from .models.player import Player


SNAPSHOT_FORMAT_VERSION = 1
SNAPSHOT_METADATA_FIELDS: Tuple[str, ...] = (
    "team_name",
    "team_id",
    "position",
    "overall",
    "age",
    "birth_year",
)


def _attribute_label(attr: AttributeDef) -> str:
    return attr.description or attr.name


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _player_identity_key(player_entry: Dict[str, Any]) -> str:
    full_name = _normalize_text(player_entry.get("full_name")).lower()
    birth_year = int(player_entry.get("birth_year") or 0)
    position = _normalize_text(player_entry.get("position")).lower()
    return f"{full_name}|{birth_year}|{position}"


def _disambiguate_player_keys(players: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    counts: Dict[str, int] = {}

    for player in players:
        base_key = _player_identity_key(player)
        counts[base_key] = counts.get(base_key, 0) + 1
        unique_key = base_key if counts[base_key] == 1 else f"{base_key}#{counts[base_key]}"
        cloned = dict(player)
        cloned["player_key"] = unique_key
        result[unique_key] = cloned

    return result


def build_snapshot(
    config: OffsetConfig,
    player_mgr,
    players: Sequence[Player],
    *,
    roster_mode: str = "auto",
    scope_name: str = "Current Scope",
    progress_callback: Optional[Callable[[int, int, Player], None]] = None,
) -> Dict[str, Any]:
    attributes = list(config.all_attributes())
    player_entries: List[Dict[str, Any]] = []
    total_players = len(players)

    for index, player in enumerate(players, start=1):
        if progress_callback is not None:
            progress_callback(index, total_players, player)

        values = player_mgr.read_all_attributes(player)
        normalized_attributes: Dict[str, Any] = {}
        for attr in attributes:
            label = _attribute_label(attr)
            if attr.name in values:
                normalized_attributes[label] = values[attr.name]

        player_entries.append(
            {
                "index": int(player.index),
                "full_name": player.full_name,
                "first_name": player.first_name,
                "last_name": player.last_name,
                "team_id": int(player.team_id),
                "team_name": player.team_name,
                "position": player.position,
                "overall": int(player.overall),
                "age": int(player.age),
                "birth_year": int(player.birth_year),
                "attributes": normalized_attributes,
            }
        )

    keyed_players = list(_disambiguate_player_keys(player_entries).values())
    keyed_players.sort(key=lambda item: (_normalize_text(item.get("team_name")), _normalize_text(item.get("full_name"))))

    return {
        "format_version": SNAPSHOT_FORMAT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "trainer_version": __version__,
        "game_version": config.game_version,
        "offset_version": config.version,
        "roster_mode": roster_mode,
        "scope_name": scope_name,
        "player_count": len(keyed_players),
        "attribute_count": len(attributes),
        "players": keyed_players,
    }


def save_snapshot(filepath: str, snapshot: Dict[str, Any]) -> None:
    with open(filepath, "w", encoding="utf-8") as handle:
        json.dump(snapshot, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def load_snapshot(filepath: str) -> Dict[str, Any]:
    with open(filepath, "r", encoding="utf-8") as handle:
        snapshot = json.load(handle)

    players = snapshot.get("players")
    if not isinstance(players, list):
        raise ValueError("Snapshot file is missing the player list.")

    return snapshot


def diff_snapshots(left_snapshot: Dict[str, Any], right_snapshot: Dict[str, Any]) -> Dict[str, Any]:
    left_players = _disambiguate_player_keys(left_snapshot.get("players", []))
    right_players = _disambiguate_player_keys(right_snapshot.get("players", []))

    left_keys = set(left_players.keys())
    right_keys = set(right_players.keys())

    added = [right_players[key] for key in sorted(right_keys - left_keys)]
    removed = [left_players[key] for key in sorted(left_keys - right_keys)]

    changed: List[Dict[str, Any]] = []
    attribute_change_counts: Counter[str] = Counter()

    for key in sorted(left_keys & right_keys):
        left_player = left_players[key]
        right_player = right_players[key]

        metadata_changes: Dict[str, Tuple[Any, Any]] = {}
        for field in SNAPSHOT_METADATA_FIELDS:
            left_value = left_player.get(field)
            right_value = right_player.get(field)
            if left_value != right_value:
                metadata_changes[field] = (left_value, right_value)

        left_attributes = left_player.get("attributes", {}) or {}
        right_attributes = right_player.get("attributes", {}) or {}
        attribute_changes: Dict[str, Tuple[Any, Any]] = {}
        for attr_name in sorted(set(left_attributes.keys()) | set(right_attributes.keys())):
            left_value = left_attributes.get(attr_name)
            right_value = right_attributes.get(attr_name)
            if left_value != right_value:
                attribute_changes[attr_name] = (left_value, right_value)
                attribute_change_counts[attr_name] += 1

        if metadata_changes or attribute_changes:
            changed.append(
                {
                    "player_key": key,
                    "left_player": left_player,
                    "right_player": right_player,
                    "metadata_changes": metadata_changes,
                    "attribute_changes": attribute_changes,
                    "change_count": len(metadata_changes) + len(attribute_changes),
                }
            )

    changed.sort(
        key=lambda item: (
            -int(item.get("change_count", 0)),
            _normalize_text(item["right_player"].get("full_name") or item["left_player"].get("full_name")),
        )
    )

    return {
        "left_snapshot": left_snapshot,
        "right_snapshot": right_snapshot,
        "added": added,
        "removed": removed,
        "changed": changed,
        "attribute_change_counts": dict(attribute_change_counts.most_common()),
    }


def format_snapshot_summary(snapshot: Dict[str, Any]) -> str:
    scope_name = snapshot.get("scope_name") or "Snapshot"
    created_at = snapshot.get("created_at") or "unknown time"
    player_count = int(snapshot.get("player_count") or len(snapshot.get("players", [])))
    roster_mode = snapshot.get("roster_mode") or "auto"
    return f"{scope_name} | {player_count} players | roster mode {roster_mode} | {created_at}"


def _format_player_label(player_entry: Dict[str, Any]) -> str:
    full_name = player_entry.get("full_name") or "Unknown Player"
    team_name = player_entry.get("team_name") or "Unassigned"
    position = player_entry.get("position") or "?"
    return f"{full_name} ({team_name}, {position})"


def format_diff_report(diff_result: Dict[str, Any], *, max_players: int = 12, max_attributes: int = 8) -> str:
    left_snapshot = diff_result["left_snapshot"]
    right_snapshot = diff_result["right_snapshot"]
    added = diff_result["added"]
    removed = diff_result["removed"]
    changed = diff_result["changed"]
    attribute_change_counts = diff_result["attribute_change_counts"]

    lines = [
        "Roster Snapshot Diff",
        "",
        f"Left:  {format_snapshot_summary(left_snapshot)}",
        f"Right: {format_snapshot_summary(right_snapshot)}",
        "",
        f"Added players:   {len(added)}",
        f"Removed players: {len(removed)}",
        f"Changed players: {len(changed)}",
    ]

    if attribute_change_counts:
        top_attributes = list(attribute_change_counts.items())[:max_attributes]
        attr_text = ", ".join(f"{name} ({count})" for name, count in top_attributes)
        lines.extend(["", f"Top changed attributes: {attr_text}"])

    if changed:
        lines.extend(["", "Changed Players"])
        for player_change in changed[:max_players]:
            left_player = player_change["left_player"]
            right_player = player_change["right_player"]
            lines.append(f"- {_format_player_label(right_player)}")

            metadata_changes = player_change["metadata_changes"]
            if metadata_changes:
                metadata_text = ", ".join(
                    f"{field}: {old_value} -> {new_value}"
                    for field, (old_value, new_value) in metadata_changes.items()
                )
                lines.append(f"  Meta: {metadata_text}")

            attribute_items = list(player_change["attribute_changes"].items())[:max_attributes]
            if attribute_items:
                attr_text = ", ".join(
                    f"{name}: {old_value} -> {new_value}"
                    for name, (old_value, new_value) in attribute_items
                )
                suffix = ""
                if len(player_change["attribute_changes"]) > len(attribute_items):
                    suffix = ", ..."
                lines.append(f"  Attrs: {attr_text}{suffix}")

    if added:
        lines.extend(["", "Added Players"])
        for player in added[:max_players]:
            lines.append(f"- {_format_player_label(player)}")

    if removed:
        lines.extend(["", "Removed Players"])
        for player in removed[:max_players]:
            lines.append(f"- {_format_player_label(player)}")

    if not added and not removed and not changed:
        lines.extend(["", "No differences found."])

    return "\n".join(lines)
