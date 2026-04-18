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
    save_snapshot_csv,
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
            "Export the current roster scope as JSON or CSV, compare the live roster to a saved snapshot, "
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

        self.btn_save_output = QPushButton("Save Output...")
        self.btn_save_output.clicked.connect(self._save_output)
        button_row.addWidget(self.btn_save_output)

        button_row.addStretch()
        layout.addLayout(button_row)

        summary_group = QGroupBox("Comparison Summary")
        summary_layout = QVBoxLayout(summary_group)
        counts_row = QHBoxLayout()
        self.added_label = QLabel("Added: -")
        self.removed_label = QLabel("Removed: -")
        self.changed_label = QLabel("Changed: -")
        counts_row.addWidget(self.added_label)
        counts_row.addWidget(self.removed_label)
        counts_row.addWidget(self.changed_label)
        counts_row.addStretch()
        summary_layout.addLayout(counts_row)

        self.top_attributes_label = QLabel("Top changed attributes: n/a")
        self.top_attributes_label.setWordWrap(True)
        summary_layout.addWidget(self.top_attributes_label)
        layout.addWidget(summary_group)

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
        self.btn_save_output.setEnabled(False)
        self._clear_diff_summary()
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

    def _clear_diff_summary(self) -> None:
        self.added_label.setText("Added: -")
        self.removed_label.setText("Removed: -")
        self.changed_label.setText("Changed: -")
        self.top_attributes_label.setText("Top changed attributes: n/a")

    def _set_output_text(self, text: str) -> None:
        self.report_output.setPlainText(text)
        self.btn_save_output.setEnabled(bool(text.strip()))

    def _apply_diff_result(self, diff_result, status_text: str) -> None:
        self.added_label.setText(f"Added: {len(diff_result['added'])}")
        self.removed_label.setText(f"Removed: {len(diff_result['removed'])}")
        self.changed_label.setText(f"Changed: {len(diff_result['changed'])}")

        attribute_change_counts = list(diff_result.get("attribute_change_counts", {}).items())[:5]
        if attribute_change_counts:
            top_text = ", ".join(f"{name} ({count})" for name, count in attribute_change_counts)
            self.top_attributes_label.setText(f"Top changed attributes: {top_text}")
        else:
            self.top_attributes_label.setText("Top changed attributes: none")

        self._set_output_text(format_diff_report(diff_result))
        self.status_label.setText(status_text)

    def _export_current_snapshot(self) -> None:
        if self.player_mgr is None or not self.players:
            QMessageBox.warning(self, "Snapshot Tools", "Connect the game and load players first.")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suggested = os.path.join(os.getcwd(), f"nba2k26_snapshot_{timestamp}.json")
        filepath, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save Snapshot",
            suggested,
            "Snapshot Files (*.json *.csv);;JSON Files (*.json);;CSV Files (*.csv)",
        )
        if not filepath:
            return

        snapshot = self._busy_build_current_snapshot()
        extension = os.path.splitext(filepath)[1].lower()
        if not extension:
            extension = ".csv" if "CSV" in selected_filter else ".json"
            filepath = f"{filepath}{extension}"

        if extension == ".csv":
            save_snapshot_csv(filepath, snapshot)
        else:
            save_snapshot(filepath, snapshot)

        self._clear_diff_summary()
        self.status_label.setText(f"Snapshot saved to {filepath}")
        self._set_output_text(format_snapshot_summary(snapshot))

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
        self._apply_diff_result(diff_result, f"Compared current scope against {os.path.basename(filepath)}")

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
        self._apply_diff_result(
            diff_result,
            f"Compared {os.path.basename(left_path)} vs {os.path.basename(right_path)}",
        )

    def _save_output(self) -> None:
        text = self.report_output.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Snapshot Tools", "There is no output to save yet.")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suggested = os.path.join(os.getcwd(), f"nba2k26_snapshot_report_{timestamp}.txt")
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Output",
            suggested,
            "Text Files (*.txt);;Markdown Files (*.md)",
        )
        if not filepath:
            return

        if not os.path.splitext(filepath)[1]:
            filepath = f"{filepath}.txt"

        with open(filepath, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.write("\n")

        self.status_label.setText(f"Saved output to {filepath}")
