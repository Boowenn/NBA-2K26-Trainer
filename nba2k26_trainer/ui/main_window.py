"""主窗口 - 球员列表 + 属性编辑面板"""

import os
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QPushButton, QLabel, QStatusBar, QMessageBox, QFileDialog,
    QToolBar, QAction
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QFont

from ..core.process import attach_to_game, is_process_running, launch_game_without_eac
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

        self.setWindowTitle("NBA 2K26 Trainer v1.2")
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

        self.btn_launch = QPushButton("Launch (No EAC)")
        self.btn_launch.setObjectName("btn_max")
        self.btn_launch.setToolTip("Launch NBA2K26.exe directly without EasyAntiCheat (offline mode)")
        self.btn_launch.clicked.connect(self._launch_no_eac)
        toolbar.addWidget(self.btn_launch)

        self.btn_refresh = QPushButton("Refresh Players")
        self.btn_refresh.setObjectName("btn_refresh")
        self.btn_refresh.clicked.connect(self._refresh_players)
        self.btn_refresh.setEnabled(False)
        toolbar.addWidget(self.btn_refresh)

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
            "Ready - Launch game with [Launch (No EAC)] or start NBA2K26.exe directly, then [Connect Game]"
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
                "Please:\n"
                "1. Start NBA 2K26 first\n"
                "2. Use [Launch (No EAC)] button to start without anti-cheat\n"
                "3. Run this tool as Administrator"
            )
        elif status in ("EAC_BLOCKED", "MEMORY_ACCESS_DENIED"):
            reply = QMessageBox.warning(
                self, "EasyAntiCheat Blocked Memory Access",
                "Game found but memory access is BLOCKED by EasyAntiCheat.\n\n"
                "EAC prevents external tools from reading/writing game memory.\n"
                "All community editors (discobisco, Young1996, etc.) have the same limitation.\n\n"
                "Solution: Launch NBA2K26.exe directly without EAC.\n"
                "This enables offline mode only (MyNBA/MyGM still works offline).\n\n"
                "Click [Yes] to close current game and relaunch without EAC.\n"
                "Click [No] to cancel.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                self._launch_no_eac()
        elif status == "OPEN_FAILED":
            QMessageBox.warning(
                self, "Connection Failed",
                "Cannot open game process.\n"
                "Please run this tool as Administrator."
            )

    def _launch_no_eac(self):
        """Launch game directly without EAC"""
        # Try to find NBA2K26.exe
        import sys
        search_paths = []

        # Same directory as trainer
        if getattr(sys, 'frozen', False):
            trainer_dir = os.path.dirname(sys.executable)
        else:
            trainer_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        search_paths.append(os.path.join(trainer_dir, "NBA2K26.exe"))

        # Parent directory (if trainer is in subfolder)
        parent = os.path.dirname(trainer_dir)
        search_paths.append(os.path.join(parent, "NBA2K26.exe"))

        # Common Steam paths
        search_paths.extend([
            r"C:\SteamLibrary\steamapps\common\NBA 2K26\NBA2K26.exe",
            r"D:\SteamLibrary\steamapps\common\NBA 2K26\NBA2K26.exe",
            r"C:\Program Files (x86)\Steam\steamapps\common\NBA 2K26\NBA2K26.exe",
        ])

        exe_path = None
        for p in search_paths:
            if os.path.exists(p):
                exe_path = p
                break

        if not exe_path:
            QMessageBox.warning(
                self, "Not Found",
                "Cannot find NBA2K26.exe.\n\n"
                "Please place this trainer in the NBA 2K26 game directory,\n"
                "or launch NBA2K26.exe manually (not start_protected_game.exe)."
            )
            return

        import subprocess
        try:
            subprocess.Popen([exe_path], cwd=os.path.dirname(exe_path))
            self.statusbar.showMessage(
                f"Launched: {exe_path} (No EAC) - Wait for game to load, then click [Connect Game]"
            )
            QMessageBox.information(
                self, "Game Launched",
                f"NBA2K26.exe launched without EAC.\n\n"
                f"Path: {exe_path}\n\n"
                "Wait for the game to fully load into MyNBA/MyGM mode,\n"
                "then click [Connect Game]."
            )
        except Exception as e:
            QMessageBox.critical(self, "Launch Failed", f"Failed to launch:\n{e}")

    def _refresh_players(self):
        if self.player_mgr is None:
            return
        self.statusbar.showMessage("Scanning player data ...")
        self.players = self.player_mgr.scan_players()
        self._player_index_map = {p.index: p for p in self.players}
        self.player_list.set_players(self.players)
        self.statusbar.showMessage(f"Loaded {len(self.players)} players")

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
