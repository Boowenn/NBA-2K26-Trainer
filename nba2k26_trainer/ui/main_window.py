"""主窗口 - 球员列表 + 属性编辑面板"""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QPushButton, QLabel, QStatusBar, QMessageBox, QFileDialog,
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
    """NBA 2K26 球员属性修改器主窗口"""

    def __init__(self):
        super().__init__()
        self.mem: Optional[GameMemory] = None
        self.config: Optional[OffsetConfig] = None
        self.player_mgr: Optional[PlayerManager] = None
        self.players = []
        self._player_index_map = {}

        self.setWindowTitle("NBA 2K26 Trainer - 球员属性修改器 v1.1")
        self.setMinimumSize(1200, 750)
        self.resize(1400, 850)

        self._load_config()
        self._setup_ui()
        self._setup_statusbar()
        self._setup_timer()

    def _load_config(self):
        """加载 offset 配置"""
        try:
            self.config = initialize_offsets()
        except FileNotFoundError:
            QMessageBox.critical(
                self, "错误",
                "找不到 offset 配置文件 (config/offsets_2k26.json)\n"
                "请确保配置文件存在。"
            )
            self.config = OffsetConfig()

    def _setup_ui(self):
        self.setStyleSheet(DARK_STYLE)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 8, 12, 8)
        main_layout.setSpacing(8)

        # 顶部工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        title = QLabel("NBA 2K26 Trainer")
        title.setObjectName("title")
        toolbar.addWidget(title)

        toolbar.addStretch()

        self.status_label = QLabel("未连接")
        self.status_label.setObjectName("status_disconnected")
        toolbar.addWidget(self.status_label)

        self.btn_connect = QPushButton("连接游戏")
        self.btn_connect.setObjectName("btn_refresh")
        self.btn_connect.clicked.connect(self._connect_game)
        toolbar.addWidget(self.btn_connect)

        self.btn_refresh = QPushButton("刷新球员")
        self.btn_refresh.setObjectName("btn_refresh")
        self.btn_refresh.clicked.connect(self._refresh_players)
        self.btn_refresh.setEnabled(False)
        toolbar.addWidget(self.btn_refresh)

        self.btn_batch = QPushButton("批量编辑")
        self.btn_batch.clicked.connect(self._open_batch_editor)
        self.btn_batch.setEnabled(False)
        toolbar.addWidget(self.btn_batch)

        self.btn_load_offsets = QPushButton("加载Offset")
        self.btn_load_offsets.clicked.connect(self._load_custom_offsets)
        toolbar.addWidget(self.btn_load_offsets)

        main_layout.addLayout(toolbar)

        # 主体：左侧球员列表 + 右侧属性编辑
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
        self.statusbar.showMessage("就绪 - 请先启动 NBA 2K26 然后点击「连接游戏」")

    def _setup_timer(self):
        """定时检查游戏进程状态"""
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self._check_connection)
        self.check_timer.start(5000)  # 每5秒检查一次

    def _connect_game(self):
        """连接到游戏进程"""
        self.statusbar.showMessage("正在查找 NBA2K26.exe 进程...")

        self.mem = attach_to_game()
        if self.mem is None:
            self.status_label.setText("未连接")
            self.status_label.setObjectName("status_disconnected")
            self.status_label.setStyleSheet("color: #ff5252; font-weight: bold;")
            self.btn_refresh.setEnabled(False)
            self.btn_batch.setEnabled(False)
            QMessageBox.warning(
                self, "连接失败",
                "找不到 NBA2K26.exe 进程。\n\n"
                "请确保:\n"
                "1. NBA 2K26 已经启动并进入游戏\n"
                "2. 本程序以管理员权限运行"
            )
            return

        self.status_label.setText("已连接")
        self.status_label.setObjectName("status_connected")
        self.status_label.setStyleSheet("color: #00e676; font-weight: bold;")
        self.btn_refresh.setEnabled(True)
        self.btn_batch.setEnabled(True)

        self.player_mgr = PlayerManager(self.mem, self.config)
        self.attr_editor.set_player_manager(self.player_mgr)

        self.statusbar.showMessage(
            f"已连接到 NBA2K26.exe (基址: 0x{self.mem.base_address:X})"
        )

        self._refresh_players()

    def _refresh_players(self):
        """刷新球员列表"""
        if self.player_mgr is None:
            return

        self.statusbar.showMessage("正在扫描球员数据...")
        self.players = self.player_mgr.scan_players()
        self._player_index_map = {p.index: p for p in self.players}

        self.player_list.set_players(self.players)
        self.statusbar.showMessage(f"已加载 {len(self.players)} 名球员")

    def _on_player_selected(self, player_index: int):
        """球员被选中"""
        player = self._player_index_map.get(player_index)
        if player and self.player_mgr:
            self.attr_editor.load_player(player)
            self.statusbar.showMessage(f"已选择: {player.full_name} ({player.team_name})")

    def _open_batch_editor(self):
        """打开批量编辑对话框"""
        if not self.players or self.player_mgr is None:
            QMessageBox.warning(self, "警告", "请先连接游戏并刷新球员列表")
            return

        # 使用当前筛选后的球员，如果没有筛选就用全部
        selected_idx = self.player_list.get_selected_player_index()
        if selected_idx is not None:
            # 如果有选中的球队筛选，使用筛选后的列表
            team_id = self.player_list.team_filter.currentData()
            if team_id is not None and team_id != -1:
                batch_players = [p for p in self.players if p.team_id == team_id]
            else:
                batch_players = self.players
        else:
            batch_players = self.players

        dialog = BatchEditorDialog(self.config, self.player_mgr, batch_players, self)
        dialog.exec_()
        self._refresh_players()

    def _load_custom_offsets(self):
        """加载自定义 offset 文件"""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "选择 Offset 配置文件", "", "JSON Files (*.json)"
        )
        if filepath:
            try:
                self.config = initialize_offsets(filepath)
                QMessageBox.information(
                    self, "成功",
                    f"已加载 offset 配置: {self.config.version}"
                )
                # 需要重建 UI 以反映新的属性列表
                if self.player_mgr:
                    self.player_mgr.config = self.config
            except Exception as e:
                QMessageBox.critical(self, "错误", f"加载 offset 配置失败:\n{e}")

    def _check_connection(self):
        """定时检查连接状态"""
        if self.mem is not None:
            if not is_process_running():
                self.mem = None
                self.player_mgr = None
                self.status_label.setText("已断开")
                self.status_label.setStyleSheet("color: #ff5252; font-weight: bold;")
                self.btn_refresh.setEnabled(False)
                self.btn_batch.setEnabled(False)
                self.statusbar.showMessage("游戏进程已关闭，连接已断开")

    def closeEvent(self, event):
        """关闭时清理"""
        if self.mem:
            self.mem.close()
        event.accept()
