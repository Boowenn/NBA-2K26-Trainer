# NBA 2K26 Trainer

A real-time player attribute editor for NBA 2K26 MyNBA / MyGM mode. Modify any player's ratings, badges, tendencies, contracts, and more — all live in memory while the game is running.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![PyQt5](https://img.shields.io/badge/GUI-PyQt5-green?logo=qt)
![Windows](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D6?logo=windows)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## Features

### Player Editing
- **Full Attribute Control** — Edit all 50+ player ratings (shooting, defense, athleticism, IQ, etc.)
- **Badges** — Set any badge to Bronze / Silver / Gold / Hall of Fame
- **Tendencies** — Fine-tune 60+ AI behavior tendencies (shot selection, drives, post moves, defense)
- **Contracts** — Modify salary for up to 6 years, bird rights, two-way contract days
- **Body & Bio** — Height, weight, wingspan, age, draft info, jersey number
- **Potential & Growth** — Peak age range, boom/bust rates, potential ceiling/floor
- **Durability** — Per-body-part injury resistance (head, knees, ankles, etc.)
- **Personality** — Loyalty, ring chasing, financial security

### God Mode
One-click to make any player unstoppable:
- All ratings → 99
- All badges → Hall of Fame
- All tendencies → Max
- All durability → 99
- Potential → Max

### Batch Editing
Apply changes to an entire team (or all players) at once:
- All ratings to 99
- All badges to HOF
- All hot zones to max
- Set birth year (make everyone young)
- Full God Mode for the whole roster

### Quality of Life
- **Live Memory Editing** — Changes take effect immediately in-game
- **Player Search** — Filter by name or team
- **Team Filter** — Dynamic dropdown built from actual roster data
- **Dark Theme** — NBA-styled dark UI
- **Custom Offsets** — Load your own offset config if the game updates

---

## Quick Start

### Option 1: Download the EXE (Recommended)

1. Go to [Releases](https://github.com/Boowenn/NBA-2K26-Trainer/releases) and download `NBA2K26Trainer.exe`
2. Place it anywhere on your PC (game directory is fine but not required)
3. Launch NBA 2K26 **without Anti-Cheat** (see below)
4. Run `NBA2K26Trainer.exe` as Administrator
5. Click **Connect Game** and start editing

### Option 2: Run from Source

```bash
git clone https://github.com/Boowenn/NBA-2K26-Trainer.git
cd NBA-2K26-Trainer
pip install -r requirements.txt
python main.py
```

---

## How to Launch NBA 2K26 Without EAC

> **This is required.** The trainer reads/writes game memory, which EasyAntiCheat blocks. All community roster editors use the same method.

1. Close NBA 2K26 if it's running
2. **(Recommended)** Disconnect from the internet
3. In Steam Library, click **Play** on NBA 2K26
4. A popup appears with two options:
   - Option 1: "Play Game" (with EAC, online)
   - **Option 2: "Play without Anti-Cheat" (offline)** ← Select this
5. Wait for the game to fully load — enter **MyNBA** or **MyGM** mode and load a save
6. Open the Trainer and click **Connect Game**

> **Note:** Online modes (MyTEAM, Play Online) will not work without EAC. MyNBA, MyGM, and Play Now all work fine offline.

---

## Usage

1. **Connect** — Click "Connect Game" after launching NBA 2K26 without EAC
2. **Browse** — Use the player list on the left. Search by name or filter by team
3. **Edit** — Select a player to load their attributes in the right panel. Each category has its own tab
4. **Apply** — Modify values using sliders/spinboxes, then click "Apply Changes". Modified attributes are highlighted in orange
5. **God Mode** — Click the God Mode button to max everything for the selected player
6. **Batch Edit** — Click "Batch Edit" to apply changes to all players on the selected team

---

## Offset Configuration

Player attribute memory offsets are defined in `config/offsets_2k26.json`. When a game patch changes the memory layout, only this file needs to be updated.

You can also click **Load Offsets** in the toolbar to load a custom config file at runtime.

### Finding Updated Offsets

If the game updates and the current offsets break:

1. Reference [discobisco/2k26-Editor](https://github.com/discobisco/2k26-Editor) for community-maintained offsets
2. Use [Cheat Engine](https://www.cheatengine.org/) to manually locate values
3. Check the [NLSC Forums](https://forums.nba-live.com/) for updated Cheat Tables

---

## Project Structure

```
NBA-2K26-Trainer/
├── main.py                         # Entry point (admin check + PyQt5 app)
├── config/
│   └── offsets_2k26.json           # Memory offset definitions (JSON)
├── nba2k26_trainer/
│   ├── core/
│   │   ├── memory.py               # Win32 ReadProcessMemory / WriteProcessMemory
│   │   ├── process.py              # Process discovery (find NBA2K26.exe)
│   │   ├── scanner.py              # Dynamic player table scanner
│   │   └── offsets.py              # Offset config loader
│   ├── models/
│   │   ├── player.py               # Player data model + read/write logic
│   │   └── team.py                 # Team data model
│   └── ui/
│       ├── main_window.py          # Main window layout
│       ├── player_list.py          # Player list with search/filter
│       ├── attribute_editor.py     # Tabbed attribute editor panel
│       ├── batch_editor.py         # Batch editing dialog
│       └── theme.py                # Dark NBA-style theme (QSS)
├── NBA2K26Trainer.spec             # PyInstaller build config
├── requirements.txt                # Python dependencies
└── LICENSE                         # MIT License
```

---

## Building from Source

```bash
pip install pyinstaller
pyinstaller NBA2K26Trainer.spec
```

The output EXE will be in `dist/NBA2K26Trainer.exe`.

---

## Technical Details

- **Memory Access**: Direct Win32 API calls via `ctypes` (`ReadProcessMemory` / `WriteProcessMemory`)
- **Player Table Discovery**: Two-stage scanner — first scans the game module's data sections for pointers to the player table, then falls back to searching for known player name pairs in memory
- **Data Types**: Supports uint8/16/32/64, int8/16/32, float, bitfields (packed bits), UTF-16LE strings, and ASCII strings
- **Module Base**: Standard x64 PE base at `0x140000000`
- **Player Record**: 1176 bytes per player (stride `0x498`), with names stored as UTF-16LE wide strings

---

## Requirements

| Dependency | Purpose |
|------------|---------|
| Python 3.10+ | Runtime |
| PyQt5 | GUI framework |
| ctypes (built-in) | Win32 API memory access |
| PyInstaller | EXE packaging (build only) |

---

## Disclaimer

This tool is for **offline single-player use only** (MyNBA / MyGM / Play Now).

Modifying game memory may violate the game's Terms of Service. **Do not use this in online modes.** The author is not responsible for any consequences of using this tool.

---

## License

[MIT License](LICENSE) - Copyright (c) 2026 Boowenn
