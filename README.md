# NBA 2K26 Trainer

A real-time player editor for NBA 2K26 MyNBA / MyGM saves. Edit ratings, badges, tendencies, contracts, growth, and durability directly in memory while the game is running offline.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![PyQt5](https://img.shields.io/badge/GUI-PyQt5-green?logo=qt)
![Windows](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D6?logo=windows)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## What Changed In v3.6.0

- Added team-level `Preset Packs` so a filtered scope can be reshaped with one reusable pass instead of one preset at a time
- Added three built-in pack templates: `Rebuild Identity Pack`, `Draft Class Template Pack`, and `Rotation Identity Pack`
- Added preset-pack import and export so role-template bundles can be shared as JSON, not rebuilt by hand every session
- Added Prospect-Lab-backed pack targeting, which means packs can match by role track, growth plan, tier, age, overall, potential, and score
- Refreshed the main UI with a cleaner dashboard layout, grouped actions, Chinese-friendly labels, and better visual hierarchy
- Replaced the default Python window icon with a custom trainer icon and embedded it into the packaged EXE
- Cleaned up the player list presentation so search, counts, and table headers read like a finished tool instead of a raw PyQt shell
- Extended CI with a dedicated preset-pack regression and broader import smoke coverage for the new UI surface

---

## Features

### Core Editing
- Full attribute control for ratings, contracts, body data, potential, personality, and durability
- Badge editing across inside scoring, shooting, and playmaking categories
- Tendency editing for shot selection, drives, passing, defense, post play, and freelancing
- Live memory updates while the game is running offline

### Presets And Team Tools
- Built-in role presets for common archetypes
- Export custom presets from the attributes you actually changed
- Reapply presets to a single player or to an entire filtered team
- Apply built-in or imported `Preset Packs` across a filtered team, draft class, or rebuild scope
- Import/export team template bundles as JSON so role passes are reusable across saves
- Batch tools for maxing core ratings, stamina, potential, badges, or running full God Mode
- Prospect ranking and development planning for filtered teams, draft classes, or snapshot files
- Prospect trend tracking across preseason, deadline, and offseason checkpoints

### Scan And Sync Quality
- Dynamic player-table scanning when roster pointers drift
- Current-roster vs. legend-roster selection mode
- Automatic live-roster resync when the save swaps to a different roster table
- In-match compact-copy syncing for edits that need to survive into active gameplay
- Snapshot export and diff for roster regression checks, patch comparisons, save-file validation, and spreadsheet review
- Prospect boards generated from either the live roster scope or saved snapshot files
- Prospect trend reports generated from two saved checkpoints or from the current scope against a baseline snapshot

### Experimental Live Tools
- `Live Shot Lab (Exp)` keeps temporary in-match shot tuning available
- It is intentionally separated from the normal roster-editing workflow
- It does not replace the main trainer or the preset system

---

## Quick Start

### Option 1: Download The EXE

1. Open [Releases](https://github.com/Boowenn/NBA-2K26-Trainer/releases)
2. Download `NBA2K26Trainer.exe`
3. Launch NBA 2K26 without EasyAntiCheat
4. Run the trainer as Administrator
5. Click `Connect Game`

### Option 2: Run From Source

```bash
git clone https://github.com/Boowenn/NBA-2K26-Trainer.git
cd NBA-2K26-Trainer
pip install -r requirements.txt
python main.py
```

### Build The EXE

```bash
pyinstaller NBA2K26Trainer.spec
```

The packaged executable is written to `dist/NBA2K26Trainer.exe`.

---

## Launching Without EasyAntiCheat

This trainer only works in offline modes where the game is started without EAC.

1. Close NBA 2K26
2. Optionally disconnect from the internet
3. Click `Play` in Steam
4. Choose `Play without Anti-Cheat`
5. Load into `MyNBA`, `MyGM`, or another offline mode
6. Connect the trainer

Do not use this in online modes.

---

## Usage

1. Connect to the game after the save is loaded
2. Pick a player from the list or filter by team
3. Edit the attributes you want on the right
4. Click `Apply Changes` for direct edits
5. Use `Save Preset` to export only the staged changes you made
6. Use `Apply Preset...` to reuse a built-in or imported preset
7. Use `Batch Edit` for team-wide actions in the current filter scope, including reusable `Preset Packs`
8. Open `Snapshots` to export the current filter scope as JSON or CSV, compare roster captures, and save a text report
9. Open `Prospect Lab` to rank a rebuild target list, compare checkpoint trends, export CSVs, or push the `Franchise Prospect` growth plan to qualified prospects

---

## Project Structure

```text
NBA-2K26-Trainer/
|-- .github/workflows/ci.yml
|-- assets/
|-- config/
|   `-- offsets_2k26.json
|-- nba2k26_trainer/
|   |-- core/
|   |-- models/
|   |-- ui/
|   |-- preset_packs.py
|   |-- presets.py
|   |-- prospects.py
|   |-- resources.py
|   `-- __init__.py
|-- tests/
|-- main.py
|-- NBA2K26Trainer.spec
|-- tools/
`-- requirements.txt
```

---

## Release Engineering

The CI pipeline now does six things:

1. Runs the roster regression, prospect trend regression, and preset-pack regression tests
2. Runs the full unit test suite plus import smoke checks
3. Builds the Windows executable with PyInstaller
4. Uploads the packaged EXE as a workflow artifact
5. Creates or updates a GitHub release automatically when a `v*` tag is pushed
6. Ships the packaged app with the embedded custom trainer icon

That keeps releases tied to tested commits instead of manual local packaging only.

---

## Near-Term Roadmap

These are the next extensions that fit the current product direction best:

- A safer transaction layer for contracts and cap-sheet editing
- Team or season rollup reports generated from snapshot comparisons
- Multi-checkpoint prospect timelines instead of only two-way trend compares
- Contract edit guardrails for cap, years, and salary-step validation

---

## Disclaimer

This tool is for offline single-player use only.

Modifying game memory may violate the game's Terms of Service. The author is not responsible for any consequences of using it, especially in online modes.

---

## License

[MIT License](LICENSE) - Copyright (c) 2026 Boowenn
