"""Player list panel with search and team filtering."""

from __future__ import annotations

from typing import List, Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..models.player import Player


class PlayerListWidget(QWidget):
    """Display the loaded scope and emit the selected player index."""

    player_selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.players: List[Player] = []
        self._filtered_players: List[Player] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        search_layout = QHBoxLayout()
        search_layout.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索球员姓名...")
        self.search_input.textChanged.connect(self._apply_filter)
        search_layout.addWidget(self.search_input, 2)

        self.team_filter = QComboBox()
        self.team_filter.addItem("全部球队", -1)
        self.team_filter.currentIndexChanged.connect(self._apply_filter)
        search_layout.addWidget(self.team_filter, 1)

        layout.addLayout(search_layout)

        self.count_label = QLabel("共 0 名球员")
        self.count_label.setObjectName("subtleText")
        layout.addWidget(self.count_label)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["姓名", "球队", "位置", "总评", "年龄", "索引"])
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
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(5, 54)
        self.table.setColumnHidden(5, True)

        self.table.cellClicked.connect(self._on_row_clicked)
        self.table.cellDoubleClicked.connect(self._on_row_clicked)

        layout.addWidget(self.table)

    def set_players(self, players: List[Player]) -> None:
        self.players = players
        self._rebuild_team_filter()
        self._apply_filter()

    def _rebuild_team_filter(self) -> None:
        self.team_filter.blockSignals(True)
        current_data = self.team_filter.currentData()
        self.team_filter.clear()
        self.team_filter.addItem("全部球队", -1)

        teams = {}
        for player in self.players:
            if player.team_id >= 0 and player.team_name:
                teams[player.team_id] = player.team_name

        for team_id, team_name in sorted(teams.items(), key=lambda item: item[1]):
            self.team_filter.addItem(team_name, team_id)

        if current_data is not None and current_data != -1:
            index = self.team_filter.findData(current_data)
            if index >= 0:
                self.team_filter.setCurrentIndex(index)

        self.team_filter.blockSignals(False)

    def _apply_filter(self) -> None:
        search_text = self.search_input.text().strip().lower()
        team_id = self.team_filter.currentData()

        filtered: List[Player] = []
        for player in self.players:
            if search_text and search_text not in player.full_name.lower():
                continue
            if team_id is not None and team_id != -1 and player.team_id != team_id:
                continue
            filtered.append(player)

        self._filtered_players = filtered
        self._update_table()

    def _update_table(self) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self._filtered_players))

        for row, player in enumerate(self._filtered_players):
            name_item = QTableWidgetItem(player.full_name)
            team_item = QTableWidgetItem(player.team_name)
            position_item = QTableWidgetItem(player.position)
            overall_item = QTableWidgetItem(str(player.overall))
            age_item = QTableWidgetItem(str(player.age))
            index_item = QTableWidgetItem(str(player.index))

            if player.overall >= 90:
                overall_item.setForeground(QColor("#ff9f1c"))
            elif player.overall >= 80:
                overall_item.setForeground(QColor("#4dd0a8"))
            elif player.overall >= 70:
                overall_item.setForeground(QColor("#74c0fc"))

            for item in (position_item, overall_item, age_item, index_item):
                item.setTextAlignment(Qt.AlignCenter)

            overall_item.setData(Qt.UserRole, player.overall)
            age_item.setData(Qt.UserRole, player.age)

            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, team_item)
            self.table.setItem(row, 2, position_item)
            self.table.setItem(row, 3, overall_item)
            self.table.setItem(row, 4, age_item)
            self.table.setItem(row, 5, index_item)

        self.table.setSortingEnabled(True)
        self.count_label.setText(f"共 {len(self._filtered_players)} 名球员")

    def _on_row_clicked(self, row: int, _column: int) -> None:
        index_item = self.table.item(row, 5)
        if index_item is None:
            return
        try:
            self.player_selected.emit(int(index_item.text()))
        except (TypeError, ValueError):
            return

    def get_selected_player_index(self) -> Optional[int]:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        row = rows[0].row()
        if row < len(self._filtered_players):
            return self._filtered_players[row].index
        return None

    def select_player_index(self, player_index: int) -> bool:
        for row in range(self.table.rowCount()):
            index_item = self.table.item(row, 5)
            if index_item is None:
                continue
            try:
                if int(index_item.text()) != player_index:
                    continue
            except (TypeError, ValueError):
                continue

            self.table.selectRow(row)
            name_item = self.table.item(row, 0)
            if name_item is not None:
                self.table.scrollToItem(name_item, QAbstractItemView.PositionAtCenter)
            return True
        return False

    def get_filtered_players(self) -> List[Player]:
        return list(self._filtered_players)
