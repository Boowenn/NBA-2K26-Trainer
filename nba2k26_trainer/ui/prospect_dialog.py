"""Prospect analysis dialog built on top of live roster snapshots."""

from __future__ import annotations

import os
from typing import Dict, List, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..core.offsets import OffsetConfig
from ..models.player import Player, PlayerManager
from ..presets import get_builtin_preset, resolve_preset_values
from ..prospects import (
    DEFAULT_MAX_AGE,
    DEFAULT_MIN_POTENTIAL,
    analyze_prospect_snapshot,
    export_prospect_board_csv,
    format_prospect_report,
)
from ..snapshots import build_snapshot, load_snapshot


class ProspectLabDialog(QDialog):
    """Analyze prospect ceilings in the current roster scope or from saved snapshots."""

    def __init__(
        self,
        config: OffsetConfig,
        player_mgr: Optional[PlayerManager] = None,
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
        self.current_board: Optional[Dict] = None
        self.current_source_label = "No analysis loaded."
        self._analysis_uses_live_scope = False

        self.setWindowTitle("Prospect Lab")
        self.setMinimumSize(980, 640)
        self._setup_ui()
        self._refresh_state()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        intro = QLabel(
            "Prospect Lab ranks the current filter scope or a saved snapshot by age, ceiling, boom/bust growth, "
            "and roster readiness. Use it to build draft boards, rebuild shortlists, and development plans."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        scope_group = QGroupBox("Source Scope")
        scope_layout = QVBoxLayout(scope_group)
        self.scope_label = QLabel("")
        self.scope_label.setWordWrap(True)
        scope_layout.addWidget(self.scope_label)
        self.source_label = QLabel("No analysis loaded.")
        self.source_label.setWordWrap(True)
        self.source_label.setStyleSheet("color: #b8b8b8;")
        scope_layout.addWidget(self.source_label)
        layout.addWidget(scope_group)

        filter_group = QGroupBox("Board Filters")
        filter_layout = QHBoxLayout(filter_group)
        filter_layout.addWidget(QLabel("Max Age"))
        self.max_age_spin = QSpinBox()
        self.max_age_spin.setRange(18, 35)
        self.max_age_spin.setValue(DEFAULT_MAX_AGE)
        filter_layout.addWidget(self.max_age_spin)
        filter_layout.addSpacing(12)
        filter_layout.addWidget(QLabel("Min Potential"))
        self.min_potential_spin = QSpinBox()
        self.min_potential_spin.setRange(50, 99)
        self.min_potential_spin.setValue(DEFAULT_MIN_POTENTIAL)
        filter_layout.addWidget(self.min_potential_spin)
        filter_layout.addStretch()
        layout.addWidget(filter_group)

        button_row = QHBoxLayout()
        self.btn_analyze_current = QPushButton("Analyze Current Scope")
        self.btn_analyze_current.setObjectName("btn_apply")
        self.btn_analyze_current.clicked.connect(self._analyze_current_scope)
        button_row.addWidget(self.btn_analyze_current)

        self.btn_analyze_snapshot = QPushButton("Analyze Snapshot File...")
        self.btn_analyze_snapshot.clicked.connect(self._analyze_snapshot_file)
        button_row.addWidget(self.btn_analyze_snapshot)

        self.btn_apply_growth = QPushButton("Apply Growth Plan...")
        self.btn_apply_growth.clicked.connect(self._apply_growth_plan)
        button_row.addWidget(self.btn_apply_growth)

        self.btn_export = QPushButton("Export Board CSV...")
        self.btn_export.setObjectName("btn_max")
        self.btn_export.clicked.connect(self._export_board)
        button_row.addWidget(self.btn_export)

        button_row.addStretch()
        layout.addLayout(button_row)

        summary_group = QGroupBox("Board Summary")
        summary_layout = QHBoxLayout(summary_group)
        self.qualified_label = QLabel("Qualified: -")
        self.average_label = QLabel("Avg Score: -")
        self.tier_label = QLabel("Top Tier: -")
        self.role_label = QLabel("Common Track: -")
        summary_layout.addWidget(self.qualified_label)
        summary_layout.addWidget(self.average_label)
        summary_layout.addWidget(self.tier_label)
        summary_layout.addWidget(self.role_label)
        summary_layout.addStretch()
        layout.addWidget(summary_group)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.status_label = QLabel("Ready.")
        self.status_label.setStyleSheet("color: #b8b8b8;")
        layout.addWidget(self.status_label)

        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels(
            [
                "Name",
                "Team",
                "Pos",
                "Age",
                "OVR",
                "POT",
                "Score",
                "Tier",
                "Growth",
                "Role",
            ]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.ResizeToContents)
        layout.addWidget(self.table, 2)

        self.report_output = QPlainTextEdit()
        self.report_output.setReadOnly(True)
        layout.addWidget(self.report_output, 1)

    def _refresh_state(self) -> None:
        player_count = len(self.players)
        self.scope_label.setText(
            f"Scope: {self.scope_name}\nPlayers in current live scope: {player_count}\nRoster mode: {self.roster_mode}"
        )
        live_available = self.player_mgr is not None and player_count > 0
        self.btn_analyze_current.setEnabled(live_available)
        self.btn_apply_growth.setEnabled(False)
        self.btn_export.setEnabled(False)
        if not live_available:
            self.status_label.setText("Connect the game and load players to analyze the live roster, or open a snapshot file.")
        self._clear_summary()

    def _clear_summary(self) -> None:
        self.qualified_label.setText("Qualified: -")
        self.average_label.setText("Avg Score: -")
        self.tier_label.setText("Top Tier: -")
        self.role_label.setText("Common Track: -")

    def _busy_build_current_snapshot(self) -> Dict:
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

    def _top_label(self, counts: Dict[str, int], fallback: str) -> str:
        if not counts:
            return fallback
        key, count = next(iter(counts.items()))
        return f"{key} ({count})"

    def _set_table_rows(self, players: List[Dict]) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(players))

        tier_colors = {
            "Blue Chip": "#ffb703",
            "Starter Bet": "#8ecae6",
            "Rotation Swing": "#90be6d",
            "Project": "#adb5bd",
        }

        for row, player in enumerate(players):
            items = [
                QTableWidgetItem(player["full_name"]),
                QTableWidgetItem(player["team_name"]),
                QTableWidgetItem(player["position"]),
                QTableWidgetItem(str(player["age"])),
                QTableWidgetItem(str(player["overall"])),
                QTableWidgetItem(str(player["potential"])),
                QTableWidgetItem(f"{player['prospect_score']:.1f}"),
                QTableWidgetItem(player["tier"]),
                QTableWidgetItem(player["growth_plan"]),
                QTableWidgetItem(player["role_track"]),
            ]

            for column in (2, 3, 4, 5, 6):
                items[column].setTextAlignment(Qt.AlignCenter)
            items[3].setData(Qt.UserRole, int(player["age"]))
            items[4].setData(Qt.UserRole, int(player["overall"]))
            items[5].setData(Qt.UserRole, int(player["potential"]))
            items[6].setData(Qt.UserRole, float(player["prospect_score"]))

            score_value = float(player["prospect_score"])
            if score_value >= 88:
                items[6].setForeground(QColor("#ffb703"))
            elif score_value >= 80:
                items[6].setForeground(QColor("#8ecae6"))
            elif score_value >= 72:
                items[6].setForeground(QColor("#90be6d"))

            tier_color = tier_colors.get(player["tier"])
            if tier_color:
                items[7].setForeground(QColor(tier_color))

            for column, item in enumerate(items):
                self.table.setItem(row, column, item)

        self.table.setSortingEnabled(True)

    def _set_board(self, board: Dict, *, source_label: str, uses_live_scope: bool) -> None:
        self.current_board = board
        self.current_source_label = source_label
        self._analysis_uses_live_scope = uses_live_scope
        self.source_label.setText(source_label)
        self.report_output.setPlainText(format_prospect_report(board))
        self._set_table_rows(list(board.get("players", [])))

        qualified = int(board.get("qualified_count", 0))
        average_score = float(board.get("average_score", 0.0))
        tier_counts = dict(board.get("tier_counts", {}) or {})
        role_counts = dict(board.get("role_track_counts", {}) or {})
        sorted_tiers = dict(sorted(tier_counts.items(), key=lambda item: item[1], reverse=True))
        self.qualified_label.setText(f"Qualified: {qualified}")
        self.average_label.setText(f"Avg Score: {average_score:.1f}")
        self.tier_label.setText(f"Top Tier: {self._top_label(sorted_tiers, 'n/a')}")
        self.role_label.setText(f"Common Track: {self._top_label(role_counts, 'n/a')}")

        self.btn_export.setEnabled(True)
        growth_candidates = [player for player in board.get("players", []) if player.get("growth_plan") == "Franchise Prospect"]
        self.btn_apply_growth.setEnabled(bool(uses_live_scope and growth_candidates))
        self.status_label.setText(f"Loaded prospect board with {qualified} qualified players.")

    def _analyze_current_scope(self) -> None:
        if self.player_mgr is None or not self.players:
            QMessageBox.warning(self, "Prospect Lab", "Connect the game and load players first.")
            return

        snapshot = self._busy_build_current_snapshot()
        board = analyze_prospect_snapshot(
            snapshot,
            max_age=self.max_age_spin.value(),
            min_potential=self.min_potential_spin.value(),
        )
        self._set_board(
            board,
            source_label=f"Source: live scope | {self.scope_name}",
            uses_live_scope=True,
        )

    def _analyze_snapshot_file(self) -> None:
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Open Snapshot File",
            "",
            "JSON Files (*.json)",
        )
        if not filepath:
            return

        try:
            snapshot = load_snapshot(filepath)
        except Exception as exc:
            QMessageBox.warning(self, "Prospect Lab", f"Failed to load snapshot file:\n{exc}")
            return

        board = analyze_prospect_snapshot(
            snapshot,
            max_age=self.max_age_spin.value(),
            min_potential=self.min_potential_spin.value(),
        )
        self._set_board(
            board,
            source_label=f"Source: snapshot file | {os.path.basename(filepath)}",
            uses_live_scope=False,
        )

    def _export_board(self) -> None:
        if not self.current_board:
            QMessageBox.information(self, "Prospect Lab", "Analyze a live scope or snapshot first.")
            return

        suggested = os.path.join(os.getcwd(), "nba2k26_prospect_board.csv")
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Prospect Board",
            suggested,
            "CSV Files (*.csv)",
        )
        if not filepath:
            return

        if not filepath.lower().endswith(".csv"):
            filepath = f"{filepath}.csv"

        export_prospect_board_csv(filepath, self.current_board)
        self.status_label.setText(f"Saved prospect board to {filepath}")

    def _apply_growth_plan(self) -> None:
        if not self.current_board or not self._analysis_uses_live_scope or self.player_mgr is None:
            QMessageBox.information(self, "Prospect Lab", "Analyze the current live scope before applying a growth plan.")
            return

        preset = get_builtin_preset("franchise_prospect")
        if preset is None:
            QMessageBox.warning(self, "Prospect Lab", "Cannot find the built-in Franchise Prospect preset.")
            return

        values, unresolved = resolve_preset_values(self.config, preset.values_by_description)
        if not values:
            QMessageBox.warning(self, "Prospect Lab", "The growth preset did not map to any writable attributes.")
            return

        target_entries = [
            player
            for player in self.current_board.get("players", [])
            if player.get("growth_plan") == "Franchise Prospect"
        ]
        if not target_entries:
            QMessageBox.information(self, "Prospect Lab", "No qualified prospects currently need the Franchise Prospect growth plan.")
            return

        reply = QMessageBox.question(
            self,
            "Apply Growth Plan",
            "\n".join(
                [
                    f"Apply 'Franchise Prospect' to {len(target_entries)} qualified players?",
                    "",
                    "This updates only the growth-oriented attributes mapped by the built-in preset.",
                ]
            ),
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        player_map = {player.index: player for player in self.players}
        updated_players = 0
        successful_writes = 0
        failed_writes = 0
        missing_players = 0

        self.progress.setVisible(True)
        self.progress.setMaximum(len(target_entries))
        for index, entry in enumerate(target_entries, start=1):
            live_player = player_map.get(int(entry.get("index", -1)))
            if live_player is None:
                missing_players += 1
                self.progress.setValue(index)
                continue

            results = self.player_mgr.write_all_attributes(live_player, values)
            write_count = sum(1 for ok in results.values() if ok)
            fail_count = sum(1 for ok in results.values() if not ok)
            if write_count > 0:
                updated_players += 1
            successful_writes += write_count
            failed_writes += fail_count
            self.progress.setValue(index)

        self.progress.setVisible(False)

        message_lines = [
            f"Players updated: {updated_players}/{len(target_entries)}",
            f"Successful writes: {successful_writes}",
            f"Failed writes: {failed_writes}",
        ]
        if missing_players:
            message_lines.append(f"Skipped players no longer in scope: {missing_players}")
        if unresolved:
            message_lines.append(f"Skipped preset entries not in current offsets: {len(unresolved)}")

        QMessageBox.information(self, "Prospect Lab", "\n".join(message_lines))
        self._analyze_current_scope()
