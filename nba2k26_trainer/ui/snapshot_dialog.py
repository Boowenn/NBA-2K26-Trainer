"""UI for exporting roster snapshots and comparing snapshot files."""

from __future__ import annotations

import os
from datetime import datetime
from typing import List, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from ..core.offsets import OffsetConfig
from ..models.player import Player
from ..snapshots import (
    build_snapshot,
    diff_snapshots,
    format_diff_report,
    format_snapshot_summary,
    load_snapshot,
    save_snapshot,
)


class SnapshotToolsDialog(QDialog):
    """Export current roster snapshots and compare saved snapshots."""

    def __init__(
        self,
        config: OffsetConfig,
        player_mgr=None,
        players: Optional[List[Player]] = None,
        *,
        roster_mode: str = "auto",
        scope_name: str = "Current Scope",
        parent=None,
    ):
        super().__init__(parent)
        self.config = config
        self.player_mgr = player_mgr
        self.players = list(players or [])
        self.roster_mode = roster_mode
        self.scope_name = scope_name

        self.setWindowTitle("Snapshot Tools")
        self.setMinimumSize(760, 520)
        self._setup_ui()
        self._refresh_state()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        intro = QLabel(
            "Export the current roster scope as a JSON snapshot, compare the live roster to a saved snapshot, "
            "or diff any two snapshot files."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        scope_group = QGroupBox("Current Scope")
        scope_layout = QVBoxLayout(scope_group)
        self.scope_label = QLabel("")
        self.scope_label.setWordWrap(True)
        scope_layout.addWidget(self.scope_label)
        layout.addWidget(scope_group)

        button_row = QHBoxLayout()
        self.btn_export = QPushButton("Export Current Snapshot...")
        self.btn_export.setObjectName("btn_apply")
        self.btn_export.clicked.connect(self._export_current_snapshot)
        button_row.addWidget(self.btn_export)

        self.btn_compare_current = QPushButton("Compare Current vs Snapshot...")
        self.btn_compare_current.clicked.connect(self._compare_current_vs_snapshot)
        button_row.addWidget(self.btn_compare_current)

        self.btn_compare_files = QPushButton("Compare Two Snapshot Files...")
        self.btn_compare_files.setObjectName("btn_max")
        self.btn_compare_files.clicked.connect(self._compare_two_snapshot_files)
        button_row.addWidget(self.btn_compare_files)

        button_row.addStretch()
        layout.addLayout(button_row)

        self.status_label = QLabel("Ready.")
        self.status_label.setStyleSheet("color: #b8b8b8;")
        layout.addWidget(self.status_label)

        self.report_output = QPlainTextEdit()
        self.report_output.setReadOnly(True)
        layout.addWidget(self.report_output, 1)

    def _refresh_state(self) -> None:
        player_count = len(self.players)
        self.scope_label.setText(
            f"Scope: {self.scope_name}\nPlayers in scope: {player_count}\nRoster mode: {self.roster_mode}"
        )
        live_available = self.player_mgr is not None and player_count > 0
        self.btn_export.setEnabled(live_available)
        self.btn_compare_current.setEnabled(live_available)
        if not live_available:
            self.status_label.setText("Connect the game and load players to export or compare the live roster.")

    def _busy_build_current_snapshot(self):
        def progress(index: int, total: int, player: Player) -> None:
            self.status_label.setText(f"Reading player {index}/{total}: {player.full_name}")
            QApplication.processEvents()

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            snapshot = build_snapshot(
                self.config,
                self.player_mgr,
                self.players,
                roster_mode=self.roster_mode,
                scope_name=self.scope_name,
                progress_callback=progress,
            )
        finally:
            QApplication.restoreOverrideCursor()
        return snapshot

    def _export_current_snapshot(self) -> None:
        if self.player_mgr is None or not self.players:
            QMessageBox.warning(self, "Snapshot Tools", "Connect the game and load players first.")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suggested = os.path.join(os.getcwd(), f"nba2k26_snapshot_{timestamp}.json")
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Snapshot",
            suggested,
            "JSON Files (*.json)",
        )
        if not filepath:
            return

        snapshot = self._busy_build_current_snapshot()
        save_snapshot(filepath, snapshot)
        self.status_label.setText(f"Snapshot saved to {filepath}")
        self.report_output.setPlainText(format_snapshot_summary(snapshot))

    def _compare_current_vs_snapshot(self) -> None:
        if self.player_mgr is None or not self.players:
            QMessageBox.warning(self, "Snapshot Tools", "Connect the game and load players first.")
            return

        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Open Snapshot File",
            "",
            "JSON Files (*.json)",
        )
        if not filepath:
            return

        current_snapshot = self._busy_build_current_snapshot()
        loaded_snapshot = load_snapshot(filepath)
        diff_result = diff_snapshots(loaded_snapshot, current_snapshot)
        self.report_output.setPlainText(format_diff_report(diff_result))
        self.status_label.setText(f"Compared current scope against {os.path.basename(filepath)}")

    def _compare_two_snapshot_files(self) -> None:
        left_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Left Snapshot",
            "",
            "JSON Files (*.json)",
        )
        if not left_path:
            return

        right_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Right Snapshot",
            "",
            "JSON Files (*.json)",
        )
        if not right_path:
            return

        left_snapshot = load_snapshot(left_path)
        right_snapshot = load_snapshot(right_path)
        diff_result = diff_snapshots(left_snapshot, right_snapshot)
        self.report_output.setPlainText(format_diff_report(diff_result))
        self.status_label.setText(
            f"Compared {os.path.basename(left_path)} vs {os.path.basename(right_path)}"
        )
