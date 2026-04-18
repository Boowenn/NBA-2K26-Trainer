"""Prospect analysis and trend dialog built on top of live roster snapshots."""

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
    compare_prospect_snapshots,
    export_prospect_board_csv,
    export_prospect_trend_csv,
    format_prospect_report,
    format_prospect_trend_report,
)
from ..snapshots import build_snapshot, load_snapshot


class ProspectLabDialog(QDialog):
    """Analyze prospect ceilings or compare prospect boards across checkpoints."""

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
        self.current_trend: Optional[Dict] = None
        self.current_result_kind: Optional[str] = None
        self.current_source_label = "No analysis loaded."
        self._analysis_uses_live_scope = False

        self.setWindowTitle("Prospect Lab")
        self.setMinimumSize(1040, 700)
        self._setup_ui()
        self._refresh_state()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        intro = QLabel(
            "Prospect Lab ranks the current filter scope or a saved snapshot by age, ceiling, boom/bust growth, "
            "and roster readiness. It can also compare two checkpoints to surface risers, fallers, and board churn."
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

        analysis_row = QHBoxLayout()
        self.btn_analyze_current = QPushButton("Analyze Current Scope")
        self.btn_analyze_current.setObjectName("btn_apply")
        self.btn_analyze_current.clicked.connect(self._analyze_current_scope)
        analysis_row.addWidget(self.btn_analyze_current)

        self.btn_analyze_snapshot = QPushButton("Analyze Snapshot File...")
        self.btn_analyze_snapshot.clicked.connect(self._analyze_snapshot_file)
        analysis_row.addWidget(self.btn_analyze_snapshot)

        self.btn_compare_current = QPushButton("Compare Current vs Snapshot...")
        self.btn_compare_current.clicked.connect(self._compare_current_vs_snapshot)
        analysis_row.addWidget(self.btn_compare_current)

        self.btn_compare_snapshots = QPushButton("Compare Two Snapshots...")
        self.btn_compare_snapshots.setObjectName("btn_max")
        self.btn_compare_snapshots.clicked.connect(self._compare_two_snapshots)
        analysis_row.addWidget(self.btn_compare_snapshots)

        analysis_row.addStretch()
        layout.addLayout(analysis_row)

        action_row = QHBoxLayout()
        self.btn_apply_growth = QPushButton("Apply Growth Plan...")
        self.btn_apply_growth.clicked.connect(self._apply_growth_plan)
        action_row.addWidget(self.btn_apply_growth)

        self.btn_export = QPushButton("Export Current CSV...")
        self.btn_export.clicked.connect(self._export_current_result)
        action_row.addWidget(self.btn_export)

        action_row.addStretch()
        layout.addLayout(action_row)

        summary_group = QGroupBox("Summary")
        summary_layout = QHBoxLayout(summary_group)
        self.summary_label_1 = QLabel("Value A: -")
        self.summary_label_2 = QLabel("Value B: -")
        self.summary_label_3 = QLabel("Value C: -")
        self.summary_label_4 = QLabel("Value D: -")
        summary_layout.addWidget(self.summary_label_1)
        summary_layout.addWidget(self.summary_label_2)
        summary_layout.addWidget(self.summary_label_3)
        summary_layout.addWidget(self.summary_label_4)
        summary_layout.addStretch()
        layout.addWidget(summary_group)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.status_label = QLabel("Ready.")
        self.status_label.setStyleSheet("color: #b8b8b8;")
        layout.addWidget(self.status_label)

        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, 2)

        self.report_output = QPlainTextEdit()
        self.report_output.setReadOnly(True)
        layout.addWidget(self.report_output, 1)

        self._configure_board_table()

    def _refresh_state(self) -> None:
        player_count = len(self.players)
        self.scope_label.setText(
            f"Scope: {self.scope_name}\nPlayers in current live scope: {player_count}\nRoster mode: {self.roster_mode}"
        )
        live_available = self.player_mgr is not None and player_count > 0
        self.btn_analyze_current.setEnabled(live_available)
        self.btn_compare_current.setEnabled(live_available)
        self.btn_apply_growth.setEnabled(False)
        self.btn_export.setEnabled(False)
        if not live_available:
            self.status_label.setText(
                "Connect the game and load players to analyze the live roster, or open a snapshot file."
            )
        self._clear_summary()

    def _clear_summary(self) -> None:
        self.summary_label_1.setText("Value A: -")
        self.summary_label_2.setText("Value B: -")
        self.summary_label_3.setText("Value C: -")
        self.summary_label_4.setText("Value D: -")

    def _configure_board_table(self) -> None:
        self.table.setSortingEnabled(False)
        self.table.clear()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels(
            ["Name", "Team", "Pos", "Age", "OVR", "POT", "Score", "Tier", "Growth", "Role"]
        )
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
        self.table.setSortingEnabled(True)

    def _configure_trend_table(self) -> None:
        self.table.setSortingEnabled(False)
        self.table.clear()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels(
            ["Name", "Team", "Pos", "Status", "Delta", "New Score", "OVR D", "POT D", "Tier Shift", "Growth Shift"]
        )
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
        self.table.setSortingEnabled(True)

    def _load_snapshot_file(self, dialog_title: str) -> Optional[Dict]:
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            dialog_title,
            "",
            "JSON Files (*.json)",
        )
        if not filepath:
            return None

        try:
            snapshot = load_snapshot(filepath)
        except Exception as exc:
            QMessageBox.warning(self, "Prospect Lab", f"Failed to load snapshot file:\n{exc}")
            return None

        snapshot["_filepath"] = filepath
        return snapshot

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

    def _set_board_rows(self, players: List[Dict]) -> None:
        self._configure_board_table()
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

    def _trend_rows(self, trend: Dict[str, Any]) -> List[Dict]:
        rows: List[Dict] = []
        for player in trend.get("risers", []) or []:
            rows.append(
                {
                    "full_name": player["full_name"],
                    "team_name": player["team_name"],
                    "position": player["position"],
                    "status": "Riser",
                    "delta": player["score_delta"],
                    "score_after": player["score_after"],
                    "overall_delta": player["overall_delta"],
                    "potential_delta": player["potential_delta"],
                    "tier_shift": f"{player['tier_before']} -> {player['tier_after']}",
                    "growth_shift": f"{player['growth_before']} -> {player['growth_after']}",
                }
            )
        for player in trend.get("fallers", []) or []:
            rows.append(
                {
                    "full_name": player["full_name"],
                    "team_name": player["team_name"],
                    "position": player["position"],
                    "status": "Faller",
                    "delta": player["score_delta"],
                    "score_after": player["score_after"],
                    "overall_delta": player["overall_delta"],
                    "potential_delta": player["potential_delta"],
                    "tier_shift": f"{player['tier_before']} -> {player['tier_after']}",
                    "growth_shift": f"{player['growth_before']} -> {player['growth_after']}",
                }
            )
        for player in trend.get("added", []) or []:
            rows.append(
                {
                    "full_name": player["full_name"],
                    "team_name": player["team_name"],
                    "position": player["position"],
                    "status": "New Entry",
                    "delta": "",
                    "score_after": player["prospect_score"],
                    "overall_delta": "",
                    "potential_delta": "",
                    "tier_shift": f"New -> {player['tier']}",
                    "growth_shift": f"New -> {player['growth_plan']}",
                }
            )
        for player in trend.get("removed", []) or []:
            rows.append(
                {
                    "full_name": player["full_name"],
                    "team_name": player["team_name"],
                    "position": player["position"],
                    "status": "Dropped",
                    "delta": "",
                    "score_after": player["prospect_score"],
                    "overall_delta": "",
                    "potential_delta": "",
                    "tier_shift": f"{player['tier']} -> Off Board",
                    "growth_shift": f"{player['growth_plan']} -> Off Board",
                }
            )
        return rows

    def _set_trend_rows(self, trend: Dict[str, Any]) -> None:
        rows = self._trend_rows(trend)
        self._configure_trend_table()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))

        status_colors = {
            "Riser": "#90be6d",
            "Faller": "#ef476f",
            "New Entry": "#8ecae6",
            "Dropped": "#adb5bd",
        }

        for row, player in enumerate(rows):
            delta_text = "" if player["delta"] == "" else f"{player['delta']:+.1f}"
            score_text = "" if player["score_after"] == "" else f"{player['score_after']:.1f}"
            overall_text = "" if player["overall_delta"] == "" else f"{player['overall_delta']:+d}"
            potential_text = "" if player["potential_delta"] == "" else f"{player['potential_delta']:+d}"
            items = [
                QTableWidgetItem(player["full_name"]),
                QTableWidgetItem(player["team_name"]),
                QTableWidgetItem(player["position"]),
                QTableWidgetItem(player["status"]),
                QTableWidgetItem(delta_text),
                QTableWidgetItem(score_text),
                QTableWidgetItem(overall_text),
                QTableWidgetItem(potential_text),
                QTableWidgetItem(player["tier_shift"]),
                QTableWidgetItem(player["growth_shift"]),
            ]

            for column in (2, 3, 4, 5, 6, 7):
                items[column].setTextAlignment(Qt.AlignCenter)
            items[4].setData(Qt.UserRole, float(player["delta"] or 0.0))
            items[5].setData(Qt.UserRole, float(player["score_after"] or 0.0))

            status_color = status_colors.get(player["status"])
            if status_color:
                items[3].setForeground(QColor(status_color))
            if player["delta"] != "":
                delta_value = float(player["delta"])
                if delta_value > 0:
                    items[4].setForeground(QColor("#90be6d"))
                elif delta_value < 0:
                    items[4].setForeground(QColor("#ef476f"))

            for column, item in enumerate(items):
                self.table.setItem(row, column, item)

        self.table.setSortingEnabled(True)

    def _set_board(self, board: Dict, *, source_label: str, uses_live_scope: bool) -> None:
        self.current_board = board
        self.current_trend = None
        self.current_result_kind = "board"
        self.current_source_label = source_label
        self._analysis_uses_live_scope = uses_live_scope
        self.source_label.setText(source_label)
        self.report_output.setPlainText(format_prospect_report(board))
        self._set_board_rows(list(board.get("players", [])))

        qualified = int(board.get("qualified_count", 0))
        average_score = float(board.get("average_score", 0.0))
        tier_counts = dict(board.get("tier_counts", {}) or {})
        role_counts = dict(board.get("role_track_counts", {}) or {})
        top_tier = next(iter(dict(sorted(tier_counts.items(), key=lambda item: item[1], reverse=True))), "n/a")
        top_role = next(iter(role_counts), "n/a")
        self.summary_label_1.setText(f"Qualified: {qualified}")
        self.summary_label_2.setText(f"Avg Score: {average_score:.1f}")
        self.summary_label_3.setText(f"Top Tier: {top_tier}")
        self.summary_label_4.setText(f"Common Track: {top_role}")

        growth_candidates = [
            player for player in board.get("players", []) if player.get("growth_plan") == "Franchise Prospect"
        ]
        self.btn_apply_growth.setEnabled(bool(uses_live_scope and growth_candidates))
        self.btn_export.setEnabled(True)
        self.status_label.setText(f"Loaded prospect board with {qualified} qualified players.")

    def _set_trend(self, trend: Dict, *, source_label: str) -> None:
        self.current_board = None
        self.current_trend = trend
        self.current_result_kind = "trend"
        self.current_source_label = source_label
        self._analysis_uses_live_scope = False
        self.source_label.setText(source_label)
        self.report_output.setPlainText(format_prospect_trend_report(trend))
        self._set_trend_rows(trend)

        compared = int(trend.get("compared_count", 0))
        average_delta = float(trend.get("average_score_delta", 0.0))
        risers = len(trend.get("risers", []) or [])
        fallers = len(trend.get("fallers", []) or [])
        added = len(trend.get("added", []) or [])
        removed = len(trend.get("removed", []) or [])
        self.summary_label_1.setText(f"Compared: {compared}")
        self.summary_label_2.setText(f"Avg Delta: {average_delta:+.1f}")
        self.summary_label_3.setText(f"Risers/Fallers: {risers} / {fallers}")
        self.summary_label_4.setText(f"Board Churn: +{added} / -{removed}")

        self.btn_apply_growth.setEnabled(False)
        self.btn_export.setEnabled(True)
        self.status_label.setText(
            f"Loaded prospect trend with {risers} risers, {fallers} fallers, and {added + removed} board-churn entries."
        )

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
        snapshot = self._load_snapshot_file("Open Snapshot File")
        if snapshot is None:
            return

        board = analyze_prospect_snapshot(
            snapshot,
            max_age=self.max_age_spin.value(),
            min_potential=self.min_potential_spin.value(),
        )
        self._set_board(
            board,
            source_label=f"Source: snapshot file | {os.path.basename(snapshot.get('_filepath', 'snapshot.json'))}",
            uses_live_scope=False,
        )

    def _compare_current_vs_snapshot(self) -> None:
        if self.player_mgr is None or not self.players:
            QMessageBox.warning(self, "Prospect Lab", "Connect the game and load players first.")
            return

        baseline_snapshot = self._load_snapshot_file("Open Baseline Snapshot")
        if baseline_snapshot is None:
            return

        current_snapshot = self._busy_build_current_snapshot()
        trend = compare_prospect_snapshots(
            baseline_snapshot,
            current_snapshot,
            max_age=self.max_age_spin.value(),
            min_potential=self.min_potential_spin.value(),
        )
        self._set_trend(
            trend,
            source_label=f"Trend: {os.path.basename(baseline_snapshot.get('_filepath', 'baseline.json'))} -> live scope",
        )

    def _compare_two_snapshots(self) -> None:
        left_snapshot = self._load_snapshot_file("Open Baseline Snapshot")
        if left_snapshot is None:
            return

        right_snapshot = self._load_snapshot_file("Open Latest Snapshot")
        if right_snapshot is None:
            return

        trend = compare_prospect_snapshots(
            left_snapshot,
            right_snapshot,
            max_age=self.max_age_spin.value(),
            min_potential=self.min_potential_spin.value(),
        )
        self._set_trend(
            trend,
            source_label=(
                f"Trend: {os.path.basename(left_snapshot.get('_filepath', 'left.json'))} -> "
                f"{os.path.basename(right_snapshot.get('_filepath', 'right.json'))}"
            ),
        )

    def _export_current_result(self) -> None:
        if self.current_result_kind is None:
            QMessageBox.information(self, "Prospect Lab", "Analyze a board or trend first.")
            return

        if self.current_result_kind == "trend":
            suggested = os.path.join(os.getcwd(), "nba2k26_prospect_trend.csv")
            filepath, _ = QFileDialog.getSaveFileName(
                self,
                "Save Prospect Trend",
                suggested,
                "CSV Files (*.csv)",
            )
            if not filepath:
                return
            if not filepath.lower().endswith(".csv"):
                filepath = f"{filepath}.csv"
            export_prospect_trend_csv(filepath, self.current_trend or {})
        else:
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
            export_prospect_board_csv(filepath, self.current_board or {})

        self.status_label.setText(f"Saved current result to {filepath}")

    def _apply_growth_plan(self) -> None:
        if self.current_result_kind != "board" or not self.current_board or not self._analysis_uses_live_scope or self.player_mgr is None:
            QMessageBox.information(
                self,
                "Prospect Lab",
                "Analyze the current live scope in board mode before applying a growth plan.",
            )
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
            QMessageBox.information(
                self,
                "Prospect Lab",
                "No qualified prospects currently need the Franchise Prospect growth plan.",
            )
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
