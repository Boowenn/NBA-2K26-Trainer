"""球员列表组件 - 可搜索、可筛选的球员表格"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLineEdit, QComboBox, QLabel, QHeaderView, QAbstractItemView
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor

from ..models.player import Player
from typing import List, Optional


class PlayerListWidget(QWidget):
    """球员列表组件"""

    player_selected = pyqtSignal(int)  # 发射球员 index

    def __init__(self, parent=None):
        super().__init__(parent)
        self.players: List[Player] = []
        self._filtered_players: List[Player] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 搜索栏
        search_layout = QHBoxLayout()
        search_layout.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索球员姓名...")
        self.search_input.textChanged.connect(self._apply_filter)
        search_layout.addWidget(self.search_input, 2)

        self.team_filter = QComboBox()
        self.team_filter.addItem("All Teams", -1)
        self.team_filter.currentIndexChanged.connect(self._apply_filter)
        search_layout.addWidget(self.team_filter, 1)

        layout.addLayout(search_layout)

        # 球员数量
        self.count_label = QLabel("共 0 名球员")
        layout.addWidget(self.count_label)

        # 球员表格
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["姓名", "球队", "位置", "综评", "年龄", "索引"])
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
        self.table.setColumnWidth(5, 50)
        self.table.setColumnHidden(5, True)

        self.table.cellClicked.connect(self._on_row_clicked)
        self.table.cellDoubleClicked.connect(self._on_row_clicked)

        layout.addWidget(self.table)

    def set_players(self, players: List[Player]):
        """设置球员列表"""
        self.players = players
        self._rebuild_team_filter()
        self._apply_filter()

    def _rebuild_team_filter(self):
        """从球员数据动态构建球队筛选下拉"""
        self.team_filter.blockSignals(True)
        current_data = self.team_filter.currentData()
        self.team_filter.clear()
        self.team_filter.addItem("All Teams", -1)

        # Collect unique teams from player data
        teams = {}
        for p in self.players:
            if p.team_id >= 0 and p.team_name:
                teams[p.team_id] = p.team_name

        for tid, name in sorted(teams.items(), key=lambda x: x[1]):
            self.team_filter.addItem(name, tid)

        # Restore previous selection if possible
        if current_data is not None and current_data != -1:
            idx = self.team_filter.findData(current_data)
            if idx >= 0:
                self.team_filter.setCurrentIndex(idx)

        self.team_filter.blockSignals(False)

    def _apply_filter(self):
        """应用搜索和球队筛选"""
        search_text = self.search_input.text().strip().lower()
        team_id = self.team_filter.currentData()

        filtered = []
        for p in self.players:
            if search_text and search_text not in p.full_name.lower():
                continue
            if team_id is not None and team_id != -1 and p.team_id != team_id:
                continue
            filtered.append(p)

        self._filtered_players = filtered
        self._update_table()

    def _update_table(self):
        """更新表格显示"""
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self._filtered_players))

        for row, player in enumerate(self._filtered_players):
            name_item = QTableWidgetItem(player.full_name)
            team_item = QTableWidgetItem(player.team_name)
            pos_item = QTableWidgetItem(player.position)
            ovr_item = QTableWidgetItem(str(player.overall))
            age_item = QTableWidgetItem(str(player.age))
            idx_item = QTableWidgetItem(str(player.index))

            # 综评颜色
            ovr = player.overall
            if ovr >= 90:
                ovr_item.setForeground(QColor("#ff6d00"))
            elif ovr >= 80:
                ovr_item.setForeground(QColor("#00e676"))
            elif ovr >= 70:
                ovr_item.setForeground(QColor("#29b6f6"))

            # 居中对齐
            for item in [pos_item, ovr_item, age_item, idx_item]:
                item.setTextAlignment(Qt.AlignCenter)

            # 设置 sort data
            ovr_item.setData(Qt.UserRole, ovr)
            age_item.setData(Qt.UserRole, player.age)

            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, team_item)
            self.table.setItem(row, 2, pos_item)
            self.table.setItem(row, 3, ovr_item)
            self.table.setItem(row, 4, age_item)
            self.table.setItem(row, 5, idx_item)

        self.table.setSortingEnabled(True)
        self.count_label.setText(f"共 {len(self._filtered_players)} 名球员")

    def _on_row_clicked(self, row: int, col: int):
        """行点击事件 - 使用隐藏的索引列获取球员index（排序安全）"""
        idx_item = self.table.item(row, 5)
        if idx_item is None:
            return
        try:
            player_index = int(idx_item.text())
            self.player_selected.emit(player_index)
        except (ValueError, TypeError):
            pass

    def get_selected_player_index(self) -> Optional[int]:
        """获取当前选中的球员 index"""
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        row = rows[0].row()
        if row < len(self._filtered_players):
            return self._filtered_players[row].index
        return None
