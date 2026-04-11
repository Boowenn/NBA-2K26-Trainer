"""主窗口 - 球员列表 + 属性编辑面板"""

import os
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QPushButton, QLabel, QStatusBar, QMessageBox, QFileDialog, QComboBox,
    QToolBar, QAction
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QFont

from ..core.process import attach_to_game, is_process_running
from ..core.offsets import initialize_offsets, get_offsets, get_default_offsets_path, OffsetConfig
from ..core.memory import GameMemory
from ..models.player import Player, PlayerManager
from .player_list import PlayerListWidget
from .attribute_editor import AttributeEditorWidget
from .batch_editor import BatchEditorDialog
from .theme import DARK_STYLE

from typing import Optional


class MainWindow(QMainWindow):
    """NBA 2K26 Player Attribute Trainer"""

    def __init__(self):
        super().__init__()
        self.mem: Optional[GameMemory] = None
        self.config: Optional[OffsetConfig] = None
        self.player_mgr: Optional[PlayerManager] = None
        self.players = []
        self._player_index_map = {}
        self.roster_mode = "auto"

        self.setWindowTitle("NBA 2K26 Trainer v2.1")
        self.setMinimumSize(1200, 750)
        self.resize(1400, 850)

        self._load_config()
        self._setup_ui()
        self._setup_statusbar()
        self._setup_timer()

    def _load_config(self):
        try:
            self.config = initialize_offsets()
        except FileNotFoundError:
            QMessageBox.critical(
                self, "Error",
                "Cannot find offset config (config/offsets_2k26.json)"
            )
            self.config = OffsetConfig()

    def _setup_ui(self):
        self.setStyleSheet(DARK_STYLE)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 8, 12, 8)
        main_layout.setSpacing(8)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        title = QLabel("NBA 2K26 Trainer")
        title.setObjectName("title")
        toolbar.addWidget(title)

        toolbar.addStretch()

        self.status_label = QLabel("Not Connected")
        self.status_label.setObjectName("status_disconnected")
        toolbar.addWidget(self.status_label)

        self.btn_connect = QPushButton("Connect Game")
        self.btn_connect.setObjectName("btn_refresh")
        self.btn_connect.clicked.connect(self._connect_game)
        toolbar.addWidget(self.btn_connect)

        self.btn_guide = QPushButton("How to Launch")
        self.btn_guide.setObjectName("btn_max")
        self.btn_guide.setToolTip("Show instructions for launching without EAC")
        self.btn_guide.clicked.connect(self._show_launch_guide)
        toolbar.addWidget(self.btn_guide)

        self.btn_refresh = QPushButton("Refresh Players")
        self.btn_refresh.setObjectName("btn_refresh")
        self.btn_refresh.clicked.connect(self._refresh_players)
        self.btn_refresh.setEnabled(False)
        toolbar.addWidget(self.btn_refresh)

        self.roster_mode_label = QLabel("Roster")
        toolbar.addWidget(self.roster_mode_label)

        self.roster_mode_combo = QComboBox()
        self.roster_mode_combo.addItem("Auto", "auto")
        self.roster_mode_combo.addItem("Current", "current")
        self.roster_mode_combo.addItem("Legend/Eras", "legend")
        self.roster_mode_combo.setCurrentIndex(0)
        self.roster_mode_combo.setToolTip(
            "Auto follows the roster table currently used by your loaded save. "
            "Use Current or Legend/Eras only if you want to force a specific roster family."
        )
        self.roster_mode_combo.currentIndexChanged.connect(self._on_roster_mode_changed)
        toolbar.addWidget(self.roster_mode_combo)

        self.btn_batch = QPushButton("Batch Edit")
        self.btn_batch.clicked.connect(self._open_batch_editor)
        self.btn_batch.setEnabled(False)
        toolbar.addWidget(self.btn_batch)

        self.btn_load_offsets = QPushButton("Load Offsets")
        self.btn_load_offsets.clicked.connect(self._load_custom_offsets)
        toolbar.addWidget(self.btn_load_offsets)

        main_layout.addLayout(toolbar)

        # Main: player list + attribute editor
        splitter = QSplitter(Qt.Horizontal)

        self.player_list = PlayerListWidget()
        self.player_list.player_selected.connect(self._on_player_selected)
        splitter.addWidget(self.player_list)

        self.attr_editor = AttributeEditorWidget(self.config)
        splitter.addWidget(self.attr_editor)

        splitter.setSizes([450, 750])
        main_layout.addWidget(splitter, 1)

    def _setup_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage(
            "Ready - Launch game WITHOUT EAC from Steam, then click [Connect Game]. Click [How to Launch] for help."
        )

    def _setup_timer(self):
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self._check_connection)
        self.check_timer.start(5000)

    def _connect_game(self):
        self.statusbar.showMessage("Searching for NBA2K26.exe ...")

        result = attach_to_game()
        self.mem, status = result

        if status == "OK" and self.mem is not None:
            self.status_label.setText("Connected")
            self.status_label.setStyleSheet("color: #00e676; font-weight: bold;")
            self.btn_refresh.setEnabled(True)
            self.btn_batch.setEnabled(True)

            self.player_mgr = PlayerManager(self.mem, self.config)
            self.player_mgr.set_roster_mode(self.roster_mode)
            self.attr_editor.set_player_manager(self.player_mgr)
            self.statusbar.showMessage(
                f"Connected to NBA2K26.exe (Base: 0x{self.mem.base_address:X})"
            )
            self._refresh_players()
            return

        # Connection failed
        self.status_label.setText("Not Connected")
        self.status_label.setStyleSheet("color: #ff5252; font-weight: bold;")
        self.btn_refresh.setEnabled(False)
        self.btn_batch.setEnabled(False)

        if status == "NOT_FOUND":
            QMessageBox.warning(
                self, "Connection Failed",
                "NBA2K26.exe process not found.\n\n"
                "Please start NBA 2K26 first.\n"
                "Click [How to Launch] for instructions on launching without EAC."
            )
        elif status in ("EAC_BLOCKED", "MEMORY_ACCESS_DENIED"):
            QMessageBox.warning(
                self, "EasyAntiCheat Blocked Memory Access",
                "Game found but memory access is BLOCKED by EasyAntiCheat.\n\n"
                "You need to restart the game WITHOUT EAC:\n\n"
                "1. Close NBA 2K26 completely\n"
                "2. In Steam, click Play on NBA 2K26\n"
                "3. In the popup dialog, select the SECOND option:\n"
                '   "Play without Anti-Cheat (Offline)"\n'
                "4. Wait for game to load into MyNBA/MyGM\n"
                "5. Come back here and click [Connect Game]\n\n"
                "NOTE: You may also need to disconnect from the internet\n"
                "before selecting the offline option.\n\n"
                "Click [How to Launch] for detailed instructions."
            )
        elif status == "OPEN_FAILED":
            QMessageBox.warning(
                self, "Connection Failed",
                "Cannot open game process.\n"
                "Please run this tool as Administrator."
            )

    def _show_launch_guide(self):
        """Show instructions for launching without EAC"""
        QMessageBox.information(
            self, "How to Launch NBA 2K26 Without EAC",
            "=== Launch Guide (Required for Roster Editing) ===\n\n"
            "All roster editors require launching WITHOUT EasyAntiCheat.\n"
            "This is a Steam built-in feature, not a hack.\n\n"
            "STEPS:\n\n"
            "1. Close NBA 2K26 if it is running\n\n"
            "2. (Recommended) Disconnect your PC from the internet\n"
            "   - This prevents EAC from interfering in offline mode\n\n"
            "3. In Steam Library, click PLAY on NBA 2K26\n\n"
            "4. A popup dialog will appear with TWO options:\n"
            '   - Option 1: "Play Game" (with EAC, online)\n'
            '   - Option 2: "Play without Anti-Cheat" (offline)\n'
            "   >>> SELECT OPTION 2 <<<\n\n"
            "5. Wait for game to fully load\n"
            "   - Enter MyNBA or MyGM mode\n"
            "   - Load your save file\n\n"
            "6. Come back to this Trainer\n"
            "   - Click [Connect Game]\n"
            "   - Select a player and start editing!\n\n"
            "=== NOTES ===\n"
            "- Online modes will NOT work without EAC\n"
            "- MyNBA / MyGM / Play Now all work offline\n"
            "- All community editors use this same method\n"
            "- If no popup appears, right-click the game in Steam\n"
            "  > Properties > General > Launch Options"
        )

    def _refresh_players(self):
        if self.player_mgr is None:
            return

        self.statusbar.showMessage("Scanning player data ...")
        self.btn_refresh.setEnabled(False)
        from PyQt5.QtWidgets import QApplication
        QApplication.processEvents()

        # Reset cached table base so it re-scans
        self.player_mgr._table_base = None
        self.player_mgr.set_roster_mode(self.roster_mode)

        def progress(msg):
            self.statusbar.showMessage(msg)
            QApplication.processEvents()

        self.players = self.player_mgr.scan_players(progress_callback=progress)
        self._player_index_map = {p.index: p for p in self.players}
        self.player_list.set_players(self.players)

        self.btn_refresh.setEnabled(True)

        if len(self.players) == 0:
            debug_info = self._debug_table_scan()
            QMessageBox.warning(
                self, "No Players Found",
                f"Cannot find players in game memory.\n\n"
                f"Module base: 0x{self.mem.base_address:X}\n"
                f"Config pointer: 0x{self.config.player_table.base_pointer:X}\n\n"
                f"Debug info:\n{debug_info}\n\n"
                "Make sure you are in MyNBA/MyGM mode with a roster loaded.\n"
                "The game must be past the main menu."
            )
        else:
            base = self.player_mgr._table_base
            base_str = f"0x{base:X}" if base else "unknown"
            self.statusbar.showMessage(
                f"Loaded {len(self.players)} players (table base: {base_str})"
            )

    def _on_roster_mode_changed(self, *_args):
        if not hasattr(self, "roster_mode_combo"):
            return
        self.roster_mode = self.roster_mode_combo.currentData() or "auto"
        if self.player_mgr is not None:
            self.player_mgr.set_roster_mode(self.roster_mode)
            self._refresh_players()

    def _debug_table_scan(self) -> str:
        """Collect debug info about table scanning"""
        lines = []
        mem = self.mem
        pt = self.config.player_table

        # Try multiple pointer interpretations
        addr_rva = mem.base_address + pt.base_pointer
        addr_abs = pt.base_pointer

        val_rva = mem.read_uint64(addr_rva)
        val_abs = mem.read_uint64(addr_abs)

        lines.append(f"base+ptr (0x{addr_rva:X}): {f'0x{val_rva:X}' if val_rva else 'FAIL'}")
        lines.append(f"abs ptr  (0x{addr_abs:X}): {f'0x{val_abs:X}' if val_abs else 'FAIL'}")

        # Try reading names from each resolved address
        for label, table_val in [("base+ptr", val_rva), ("abs_ptr", val_abs)]:
            if not table_val or table_val == 0:
                continue
            # Direct read
            for i in range(3):
                rec = table_val + i * pt.stride
                last = mem.read_wstring(rec + pt.last_name_offset, pt.name_string_length)
                first = mem.read_wstring(rec + pt.first_name_offset, pt.name_string_length)
                if first or last:
                    lines.append(f"  {label}[{i}]: {first} {last}")
                    break
            else:
                # Try double deref
                val2 = mem.read_uint64(table_val)
                if val2 and 0x10000 < val2 < 0x7FFFFFFFFFFF:
                    for i in range(3):
                        rec = val2 + i * pt.stride
                        last = mem.read_wstring(rec + pt.last_name_offset, pt.name_string_length)
                        first = mem.read_wstring(rec + pt.first_name_offset, pt.name_string_length)
                        if first or last:
                            lines.append(f"  {label}->deref (0x{val2:X})[{i}]: {first} {last}")
                            break
                    else:
                        raw = mem.read_bytes(val2, 40)
                        lines.append(f"  {label}->deref (0x{val2:X}): raw={raw[:20].hex() if raw else 'FAIL'}")

        return "\n".join(lines) if lines else "No data"

    def _on_player_selected(self, player_index: int):
        player = self._player_index_map.get(player_index)
        if player and self.player_mgr:
            self.attr_editor.load_player(player)
            self.statusbar.showMessage(f"Selected: {player.full_name} ({player.team_name})")

    def _open_batch_editor(self):
        if not self.players or self.player_mgr is None:
            QMessageBox.warning(self, "Warning", "Connect game and load players first")
            return

        team_id = self.player_list.team_filter.currentData()
        if team_id is not None and team_id != -1:
            batch_players = [p for p in self.players if p.team_id == team_id]
        else:
            batch_players = self.players

        dialog = BatchEditorDialog(self.config, self.player_mgr, batch_players, self)
        dialog.exec_()
        self._refresh_players()

    def _load_custom_offsets(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select Offset Config", "", "JSON Files (*.json)"
        )
        if filepath:
            try:
                self.config = initialize_offsets(filepath)
                QMessageBox.information(self, "Success", f"Loaded offsets: {self.config.version}")
                if self.player_mgr:
                    self.player_mgr.config = self.config
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load offsets:\n{e}")

    def _check_connection(self):
        if self.mem is not None:
            if not is_process_running():
                self.mem = None
                self.player_mgr = None
                self.status_label.setText("Disconnected")
                self.status_label.setStyleSheet("color: #ff5252; font-weight: bold;")
                self.btn_refresh.setEnabled(False)
                self.btn_batch.setEnabled(False)
                self.statusbar.showMessage("Game process closed")

    def closeEvent(self, event):
        if self.mem:
            self.mem.close()
        event.accept()
