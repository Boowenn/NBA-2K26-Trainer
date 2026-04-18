# NBA 2K26 Trainer

A real-time player editor for NBA 2K26 MyNBA / MyGM saves. Edit ratings, badges, tendencies, contracts, growth, and durability directly in memory while the game is running offline.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![PyQt5](https://img.shields.io/badge/GUI-PyQt5-green?logo=qt)
![Windows](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D6?logo=windows)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## What Changed In v3.2.0

- Added reusable presets for common roster roles like `Sniper Wing`, `Rim Pressure Slasher`, `Two-Way Stopper`, and `Franchise Prospect`
- Added preset export from modified attributes only, so you can build your own reusable edits without copying full player records
- Added preset application to both the single-player editor and the batch editor
- Added `Snapshot Tools` for exporting the current roster scope and diffing snapshots against each other
- Removed low-value batch shortcuts such as forcing one birth year for everyone or maxing hot zones with no reuse story
- Demoted the in-match shot patcher into `Live Shot Lab (Exp)` so the main UI stays focused on stable roster editing
- Upgraded CI so pushes validate the repo, build the EXE, publish artifacts, and create releases from version tags

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
- Batch tools for maxing core ratings, stamina, potential, badges, or running full God Mode

### Scan And Sync Quality
- Dynamic player-table scanning when roster pointers drift
- Current-roster vs. legend-roster selection mode
- Automatic live-roster resync when the save swaps to a different roster table
- In-match compact-copy syncing for edits that need to survive into active gameplay
- Snapshot export and diff for roster regression checks, patch comparisons, and save-file validation

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
7. Use `Batch Edit` for team-wide actions in the current filter scope
8. Open `Snapshots` to export the current filter scope or compare two roster captures

---

## Project Structure

```text
NBA-2K26-Trainer/
|-- .github/workflows/ci.yml
|-- config/
|   `-- offsets_2k26.json
|-- nba2k26_trainer/
|   |-- core/
|   |-- models/
|   |-- ui/
|   |-- presets.py
|   `-- __init__.py
|-- tests/
|-- main.py
|-- NBA2K26Trainer.spec
`-- requirements.txt
```

---

## Release Engineering

The CI pipeline now does four things:

1. Runs the roster regression test plus the full test suite
2. Builds the Windows executable with PyInstaller
3. Uploads the packaged EXE as a workflow artifact
4. Creates or updates a GitHub release automatically when a `v*` tag is pushed

That keeps releases tied to tested commits instead of manual local packaging only.

---

## Near-Term Roadmap

These are the next extensions that fit the current product direction best:

- Draft-class and prospect tools built on top of the new preset system
- A safer transaction layer for contracts and cap-sheet editing
- Optional import/export for team-level preset packs and role templates
- CSV export and richer visual diff summaries on top of the new snapshot workflow

---

## Disclaimer

This tool is for offline single-player use only.

Modifying game memory may violate the game's Terms of Service. The author is not responsible for any consequences of using it, especially in online modes.

---

## License

[MIT License](LICENSE) - Copyright (c) 2026 Boowenn
