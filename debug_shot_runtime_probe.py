from __future__ import annotations

import time
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from nba2k26_trainer.core.offsets import load_offsets
from nba2k26_trainer.core.process import attach_to_game
from nba2k26_trainer.models.player import (
    PERFECT_SHOT_LEGACY_STATE_PATCHES,
    Player,
    PlayerManager,
    SHOT_RUNTIME_TEAM_BLOCK_OFFSET,
    SHOT_RUNTIME_TEAM_BLOCK_SIZE,
)


REPO_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = REPO_ROOT / "config" / "offsets_2k26.json"
WATCH_SECONDS = 12.0
WATCH_INTERVAL = 0.05
TOP_OFFSETS = 18


def _format_hex_bytes(data: bytes | None, *, limit: int = 16) -> str:
    if not data:
        return "n/a"
    preview = data[:limit].hex()
    if len(data) > limit:
        preview += "..."
    return preview


def _find_player(players: Iterable[Player], *, team_hint: str, name_hint: str) -> Player | None:
    normalized_team = team_hint.lower()
    normalized_name = name_hint.lower()
    for player in players:
        team_name = (player.team_name or "").lower()
        full_name = player.full_name.lower()
        if normalized_team in team_name and normalized_name in full_name:
            return player
    return None


def _find_first_opponent(players: Iterable[Player], excluded_team_id: int) -> Player | None:
    for player in players:
        if player.team_id != excluded_team_id and (player.team_name or "").strip():
            return player
    return None


def _diff_counter(previous: bytes, current: bytes, counter: Counter[int]) -> None:
    for offset, (old_byte, new_byte) in enumerate(zip(previous, current)):
        if old_byte != new_byte:
            counter[offset] += 1


def _summarize_counter(counter: Counter[int], *, limit: int = TOP_OFFSETS) -> List[str]:
    lines: List[str] = []
    for offset, hits in counter.most_common(limit):
        lines.append(f"0x{offset:04X} -> {hits}")
    return lines


def main() -> int:
    mem, status = attach_to_game()
    print(f"attach_status: {status}")
    if mem is None:
        return 1

    try:
        config = load_offsets(str(CONFIG_PATH))
        pm = PlayerManager(mem, config)
        pm.set_roster_mode("current")
        players = pm.scan_players()
        print(f"players: {len(players)}")

        luka = _find_player(players, team_hint="lakers", name_hint="luka")
        if luka is None:
            print("luka: not found")
            return 1
        opponent = _find_first_opponent(players, luka.team_id)

        print(f"luka: {luka.full_name} | team={luka.team_name} | record={hex(luka.record_address)}")
        if opponent is not None:
            print(
                f"opponent sample: {opponent.full_name} | team={opponent.team_name} | "
                f"record={hex(opponent.record_address)}"
            )

        runtime_entries = pm._resolve_shot_runtime_entry_bases()
        legacy_entries = pm._get_perfect_shot_beta_entry_bases()
        print(f"runtime_entries: {len(runtime_entries)}")
        print(f"legacy_entries: {len(legacy_entries)}")

        for index, entry_base in enumerate(runtime_entries):
            luka_block = pm._resolve_shot_runtime_team_block_index(entry_base, luka)
            opp_block = (
                pm._resolve_shot_runtime_team_block_index(entry_base, opponent)
                if opponent is not None
                else None
            )
            print(
                f"runtime[{index}] base={hex(entry_base)} luka_block={luka_block} "
                f"opp_block={opp_block}"
            )
            for rel in (0x15D4, 0x15DC, 0x15E4, 0x15F4, 0x15FC, 0x16FC, 0x1704, 0x170C, 0x1714, 0x171C):
                print(f"  +0x{rel:04X}: {_format_hex_bytes(mem.read_bytes(entry_base + rel, 8), limit=8)}")

        for index, entry_base in enumerate(legacy_entries):
            print(
                f"legacy[{index}] base={hex(entry_base)} "
                f"+0x0010={_format_hex_bytes(mem.read_bytes(entry_base + 0x10, 1), limit=1)} "
                f"+0x0452={_format_hex_bytes(mem.read_bytes(entry_base + 0x452, 2), limit=2)} "
                f"+0x0BF2={_format_hex_bytes(mem.read_bytes(entry_base + 0xBF2, 2), limit=2)}"
            )

        runtime_shared_counters: Dict[int, Counter[int]] = {
            entry_base: Counter() for entry_base in runtime_entries
        }
        runtime_team_counters: Dict[Tuple[int, int], Counter[int]] = {}
        runtime_previous_shared: Dict[int, bytes] = {}
        runtime_previous_team: Dict[Tuple[int, int], bytes] = {}
        legacy_counters: Dict[int, Counter[int]] = {
            entry_base: Counter() for entry_base in legacy_entries
        }
        legacy_previous: Dict[int, bytes] = {}

        for entry_base in runtime_entries:
            runtime_previous_shared[entry_base] = mem.read_bytes(entry_base + 0x1500, 0x260) or b""
            for block_index in (0, 1):
                block_base = entry_base + SHOT_RUNTIME_TEAM_BLOCK_OFFSET + block_index * SHOT_RUNTIME_TEAM_BLOCK_SIZE
                key = (entry_base, block_index)
                runtime_team_counters[key] = Counter()
                runtime_previous_team[key] = mem.read_bytes(block_base, SHOT_RUNTIME_TEAM_BLOCK_SIZE) or b""

        for entry_base in legacy_entries:
            legacy_previous[entry_base] = mem.read_bytes(entry_base, 0x1050) or b""

        sample_count = 0
        deadline = time.time() + WATCH_SECONDS
        while time.time() < deadline:
            sample_count += 1
            for entry_base in runtime_entries:
                shared_blob = mem.read_bytes(entry_base + 0x1500, 0x260) or b""
                previous_shared = runtime_previous_shared.get(entry_base, b"")
                if len(previous_shared) == len(shared_blob) and shared_blob:
                    _diff_counter(previous_shared, shared_blob, runtime_shared_counters[entry_base])
                runtime_previous_shared[entry_base] = shared_blob

                for block_index in (0, 1):
                    block_base = entry_base + SHOT_RUNTIME_TEAM_BLOCK_OFFSET + block_index * SHOT_RUNTIME_TEAM_BLOCK_SIZE
                    key = (entry_base, block_index)
                    block_blob = mem.read_bytes(block_base, SHOT_RUNTIME_TEAM_BLOCK_SIZE) or b""
                    previous_block = runtime_previous_team.get(key, b"")
                    if len(previous_block) == len(block_blob) and block_blob:
                        _diff_counter(previous_block, block_blob, runtime_team_counters[key])
                    runtime_previous_team[key] = block_blob

            for entry_base in legacy_entries:
                blob = mem.read_bytes(entry_base, 0x1050) or b""
                previous_blob = legacy_previous.get(entry_base, b"")
                if len(previous_blob) == len(blob) and blob:
                    _diff_counter(previous_blob, blob, legacy_counters[entry_base])
                legacy_previous[entry_base] = blob

            time.sleep(WATCH_INTERVAL)

        print(f"samples: {sample_count}")
        print("runtime_shared_changes:")
        for index, entry_base in enumerate(runtime_entries):
            print(f"  runtime[{index}] {hex(entry_base)}")
            for line in _summarize_counter(runtime_shared_counters[entry_base]):
                print(f"    {line}")

        print("runtime_team_block_changes:")
        for index, entry_base in enumerate(runtime_entries):
            for block_index in (0, 1):
                key = (entry_base, block_index)
                print(f"  runtime[{index}] block[{block_index}] {hex(entry_base)}")
                for line in _summarize_counter(runtime_team_counters[key]):
                    print(f"    {line}")

        print("legacy_changes:")
        for index, entry_base in enumerate(legacy_entries):
            print(f"  legacy[{index}] {hex(entry_base)}")
            for line in _summarize_counter(legacy_counters[entry_base]):
                print(f"    {line}")

        print("legacy_patch_offsets:")
        for offset, patch_bytes in PERFECT_SHOT_LEGACY_STATE_PATCHES:
            print(f"  +0x{offset:04X}: {patch_bytes.hex()}")

        return 0
    finally:
        mem.close()


if __name__ == "__main__":
    raise SystemExit(main())
