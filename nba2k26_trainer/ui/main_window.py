"""Main application window."""

from __future__ import annotations

import os
from typing import Optional

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..core.memory import GameMemory
from ..core.offsets import OffsetConfig, initialize_offsets
from ..core.process import attach_to_game, is_process_running
from ..models.player import PlayerManager
from ..resources import app_icon_path
from .attribute_editor import AttributeEditorWidget
from .batch_editor import BatchEditorDialog
from .player_list import PlayerListWidget
from .prospect_dialog import ProspectLabDialog
from .snapshot_dialog import SnapshotToolsDialog
from .theme import DARK_STYLE


class MainWindow(QMainWindow):
    """NBA 2K26 Player Attribute Trainer."""

    def __init__(self):
        super().__init__()
        self.mem: Optional[GameMemory] = None
        self.config: Optional[OffsetConfig] = None
        self.player_mgr: Optional[PlayerManager] = None
        self.players = []
        self._player_index_map = {}
        self.roster_mode = "auto"
        self._refresh_in_progress = False
        self._live_roster_signature = None

        self.setWindowTitle(f"NBA 2K26 修改器 v{__version__}")
        self.setMinimumSize(1200, 750)
        self.resize(1400, 850)

        icon_path = app_icon_path()
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._load_config()
        self._setup_ui()
        self._setup_statusbar()
        self._setup_timer()

    def _load_config(self) -> None:
        try:
            self.config = initialize_offsets()
        except FileNotFoundError:
            QMessageBox.critical(
                self,
                "配置缺失",
                "找不到偏移配置文件 `config/offsets_2k26.json`。",
            )
            self.config = OffsetConfig()

    def _build_metric_card(self, label_text: str, value_label: QLabel) -> QFrame:
        card = QFrame()
        card.setObjectName("metricCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        label = QLabel(label_text)
        label.setObjectName("metricLabel")
        layout.addWidget(label)

        value_label.setObjectName("metricValue")
        layout.addWidget(value_label)
        layout.addStretch()
        return card

    def _build_action_card(self, title_text: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("actionCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title = QLabel(title_text)
        title.setObjectName("sectionLabel")
        layout.addWidget(title)
        return card, layout

    def _roster_mode_label_text(self) -> str:
        return {
            "auto": "自动",
            "current": "当前",
            "legend": "传奇/年代",
        }.get(self.roster_mode, "自动")

    def _set_connection_badge(self, text: str, *, accent: str, background: str) -> None:
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            "color: {accent};"
            "background-color: {background};"
            "border: 1px solid {accent};"
            "border-radius: 12px;"
            "padding: 6px 12px;"
            "font-size: 15px;"
            "font-weight: 700;".format(accent=accent, background=background)
        )

    def _update_dashboard(self) -> None:
        self.player_count_value.setText(str(len(self.players)))
        self.roster_mode_value.setText(self._roster_mode_label_text())

    def _setup_ui(self) -> None:
        self.setStyleSheet(DARK_STYLE)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 14, 16, 14)
        main_layout.setSpacing(12)

        hero_card = QFrame()
        hero_card.setObjectName("heroCard")
        hero_layout = QHBoxLayout(hero_card)
        hero_layout.setContentsMargins(22, 20, 22, 20)
        hero_layout.setSpacing(16)

        brand_layout = QVBoxLayout()
        brand_layout.setSpacing(8)

        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        title = QLabel("NBA 2K26 修改器")
        title.setObjectName("title")
        title_row.addWidget(title)

        version_badge = QLabel(f"v{__version__}")
        version_badge.setObjectName("heroBadge")
        title_row.addWidget(version_badge)
        title_row.addStretch()
        brand_layout.addLayout(title_row)

        subtitle = QLabel("离线 MyNBA / MyGM 实时阵容编辑、快照对比和潜力规划工具")
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        brand_layout.addWidget(subtitle)

        summary = QLabel(
            "支持当前名单同步、批量模板套用、快照回归检查和潜力趋势追踪。"
        )
        summary.setObjectName("subtleText")
        summary.setWordWrap(True)
        brand_layout.addWidget(summary)
        brand_layout.addStretch()
        hero_layout.addLayout(brand_layout, 3)

        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(12)

        self.status_label = QLabel("未连接")
        self._set_connection_badge("未连接", accent="#ff7b72", background="rgba(126, 32, 40, 0.22)")
        metrics_layout.addWidget(self._build_metric_card("连接状态", self.status_label))

        self.player_count_value = QLabel("0")
        metrics_layout.addWidget(self._build_metric_card("已载入球员", self.player_count_value))

        self.roster_mode_value = QLabel("自动")
        metrics_layout.addWidget(self._build_metric_card("阵容模式", self.roster_mode_value))

        hero_layout.addLayout(metrics_layout, 2)
        main_layout.addWidget(hero_card)

        self.btn_connect = QPushButton("连接游戏")
        self.btn_connect.setObjectName("btn_refresh")
        self.btn_connect.setToolTip("附加到 NBA2K26.exe 并读取当前存档阵容。")
        self.btn_connect.clicked.connect(self._connect_game)

        self.btn_guide = QPushButton("启动指南")
        self.btn_guide.setObjectName("btn_max")
        self.btn_guide.setToolTip("查看离线关闭 EAC 的启动方式。")
        self.btn_guide.clicked.connect(self._show_launch_guide)

        self.btn_refresh = QPushButton("刷新球员")
        self.btn_refresh.setObjectName("btn_refresh")
        self.btn_refresh.setEnabled(False)
        self.btn_refresh.clicked.connect(self._refresh_players)

        self.roster_mode_label = QLabel("阵容模式")
        self.roster_mode_label.setObjectName("sectionLabel")

        self.roster_mode_combo = QComboBox()
        self.roster_mode_combo.addItem("自动", "auto")
        self.roster_mode_combo.addItem("当前", "current")
        self.roster_mode_combo.addItem("传奇/年代", "legend")
        self.roster_mode_combo.setCurrentIndex(0)
        self.roster_mode_combo.setToolTip(
            "自动模式会跟随当前存档使用的名单表；"
            "只有在你明确知道自己要切换名单族时，才建议手动指定。"
        )
        self.roster_mode_combo.currentIndexChanged.connect(self._on_roster_mode_changed)

        self.btn_batch = QPushButton("批量编辑")
        self.btn_batch.setEnabled(False)
        self.btn_batch.clicked.connect(self._open_batch_editor)

        self.btn_snapshots = QPushButton("快照工具")
        self.btn_snapshots.setObjectName("btn_max")
        self.btn_snapshots.clicked.connect(self._open_snapshot_tools)

        self.btn_prospects = QPushButton("潜力实验室")
        self.btn_prospects.setObjectName("btn_apply")
        self.btn_prospects.clicked.connect(self._open_prospect_lab)

        self.btn_load_offsets = QPushButton("载入偏移")
        self.btn_load_offsets.setToolTip("载入自定义 offsets JSON 配置。")
        self.btn_load_offsets.clicked.connect(self._load_custom_offsets)

        top_actions = QHBoxLayout()
        top_actions.setSpacing(12)

        session_card, session_layout = self._build_action_card("连接与扫描")
        session_buttons = QHBoxLayout()
        session_buttons.setSpacing(8)
        session_buttons.addWidget(self.btn_connect)
        session_buttons.addWidget(self.btn_guide)
        session_buttons.addWidget(self.btn_refresh)
        session_layout.addLayout(session_buttons)
        top_actions.addWidget(session_card, 3)

        scope_card, scope_layout = self._build_action_card("阵容范围")
        scope_hint = QLabel("切换当前名单表，或装载新的偏移配置。")
        scope_hint.setObjectName("subtleText")
        scope_hint.setWordWrap(True)
        scope_layout.addWidget(scope_hint)
        scope_row = QHBoxLayout()
        scope_row.setSpacing(8)
        scope_row.addWidget(self.roster_mode_label)
        scope_row.addWidget(self.roster_mode_combo, 1)
        scope_row.addWidget(self.btn_load_offsets)
        scope_layout.addLayout(scope_row)
        top_actions.addWidget(scope_card, 3)

        tools_card, tools_layout = self._build_action_card("分析工具")
        tools_hint = QLabel("批量改动、快照回归和潜力趋势都从这里进入。")
        tools_hint.setObjectName("subtleText")
        tools_hint.setWordWrap(True)
        tools_layout.addWidget(tools_hint)
        tools_row = QHBoxLayout()
        tools_row.setSpacing(8)
        tools_row.addWidget(self.btn_batch)
        tools_row.addWidget(self.btn_snapshots)
        tools_row.addWidget(self.btn_prospects)
        tools_layout.addLayout(tools_row)
        top_actions.addWidget(tools_card, 4)

        main_layout.addLayout(top_actions)

        splitter = QSplitter(Qt.Horizontal)

        self.player_list = PlayerListWidget()
        self.player_list.player_selected.connect(self._on_player_selected)
        splitter.addWidget(self.player_list)

        self.attr_editor = AttributeEditorWidget(self.config)
        self.attr_editor.set_perfect_shot_team_resolver(self._resolve_lock_green_team_target)
        splitter.addWidget(self.attr_editor)

        splitter.setSizes([450, 750])

        workspace_card = QFrame()
        workspace_card.setObjectName("workspaceCard")
        workspace_layout = QVBoxLayout(workspace_card)
        workspace_layout.setContentsMargins(12, 12, 12, 12)
        workspace_layout.addWidget(splitter)
        main_layout.addWidget(workspace_card, 1)

        self._update_dashboard()

    def _setup_statusbar(self) -> None:
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage(
            "准备就绪：请从 Steam 以关闭 EAC 的方式启动游戏，然后点击“连接游戏”。"
        )

    def _setup_timer(self) -> None:
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self._check_connection)
        self.check_timer.start(5000)

    def _connect_game(self) -> None:
        self.statusbar.showMessage("正在查找 NBA2K26.exe ...")

        self.mem, status = attach_to_game()

        if status == "OK" and self.mem is not None:
            self._set_connection_badge("已连接", accent="#4dd0a8", background="rgba(13, 82, 66, 0.24)")
            self.btn_refresh.setEnabled(True)
            self.btn_batch.setEnabled(True)

            self.player_mgr = PlayerManager(self.mem, self.config)
            self.player_mgr.set_roster_mode(self.roster_mode)
            self.attr_editor.set_player_manager(self.player_mgr)
            self.statusbar.showMessage(f"已连接到 NBA2K26.exe（基址：0x{self.mem.base_address:X}）")
            self._refresh_players(force_rescan=True, preserve_selection=False)
            return

        self._set_connection_badge("未连接", accent="#ff7b72", background="rgba(126, 32, 40, 0.22)")
        self.btn_refresh.setEnabled(False)
        self.btn_batch.setEnabled(False)
        self._update_dashboard()

        if status == "NOT_FOUND":
            QMessageBox.warning(
                self,
                "连接失败",
                "没有找到 NBA2K26.exe 进程。\n\n"
                "请先启动 NBA 2K26。\n"
                "如果你不确定如何关闭 EAC，可以点击“启动指南”。",
            )
        elif status in ("EAC_BLOCKED", "MEMORY_ACCESS_DENIED"):
            QMessageBox.warning(
                self,
                "EasyAntiCheat 阻止了内存访问",
                "已经找到游戏进程，但当前仍被 EasyAntiCheat 保护。\n\n"
                "请重新以关闭 EAC 的方式启动游戏：\n\n"
                "1. 完全关闭 NBA 2K26\n"
                "2. 在 Steam 中点击“开始游戏”\n"
                "3. 在弹窗里选择第二项：\n"
                '   “关闭反作弊启动（离线）”\n'
                "4. 等游戏进入 MyNBA / MyGM 存档\n"
                "5. 回到修改器后重新点击“连接游戏”\n\n"
                "如需更详细步骤，请点击“启动指南”。",
            )
        elif status == "OPEN_FAILED":
            QMessageBox.warning(
                self,
                "连接失败",
                "无法打开游戏进程。\n"
                "请尝试以管理员身份运行修改器。",
            )

    def _show_launch_guide(self) -> None:
        QMessageBox.information(
            self,
            "如何关闭 EAC 启动 NBA 2K26",
            "=== 启动指南（阵容编辑必需） ===\n\n"
            "所有阵容类修改都要求关闭 EasyAntiCheat 启动。\n"
            "这是 Steam 自带的离线启动方式，不是外挂注入流程。\n\n"
            "步骤：\n\n"
            "1. 完全关闭 NBA 2K26\n\n"
            "2. 建议暂时断网\n"
            "   - 这样更容易避免 EAC 在离线模式下干扰内存访问\n\n"
            "3. 在 Steam 库里点击“开始游戏”\n\n"
            "4. 弹窗里会看到两个选项：\n"
            '   - 选项 1：“正常启动”（带 EAC，在线）\n'
            '   - 选项 2：“关闭反作弊启动”（离线）\n'
            "   >>> 请选择选项 2 <<<\n\n"
            "5. 等游戏完全进入 MyNBA / MyGM 存档\n\n"
            "6. 回到修改器：\n"
            "   - 点击“连接游戏”\n"
            "   - 选择球员后开始编辑\n\n"
            "说明：\n"
            "- 在线模式无法使用此工具\n"
            "- MyNBA / MyGM / Play Now 等离线模式可以正常工作\n"
            "- 如果 Steam 没弹出选项窗口，可到游戏属性里检查启动方式设置",
        )

    def _capture_selected_player_identity(self):
        player = self.attr_editor.current_player
        if player is None:
            return None
        return {
            "index": player.index,
            "full_name": player.full_name,
            "team_name": player.team_name,
        }

    def _restore_selected_player(self, identity) -> None:
        if not identity:
            return

        player = self._player_index_map.get(identity.get("index"))
        if player and player.full_name == identity.get("full_name"):
            self.player_list.select_player_index(player.index)
            self.attr_editor.load_player(player)
            return

        full_name = identity.get("full_name")
        team_name = identity.get("team_name")
        for candidate in self.players:
            if candidate.full_name == full_name and candidate.team_name == team_name:
                self.player_list.select_player_index(candidate.index)
                self.attr_editor.load_player(candidate)
                return

        for candidate in self.players:
            if candidate.full_name == full_name:
                self.player_list.select_player_index(candidate.index)
                self.attr_editor.load_player(candidate)
                return

    def _refresh_players(
        self,
        *_args,
        force_rescan: bool = True,
        silent: bool = False,
        preserve_selection: bool = True,
    ) -> None:
        if self.player_mgr is None or self._refresh_in_progress:
            return

        previous_players = self.players
        previous_index_map = self._player_index_map
        selected_identity = self._capture_selected_player_identity() if preserve_selection else None
        self._refresh_in_progress = True

        try:
            self.statusbar.showMessage("正在扫描球员数据 ...")
            self.btn_refresh.setEnabled(False)
            QApplication.processEvents()

            self.player_mgr.begin_refresh(force_rescan=force_rescan)
            self.player_mgr.set_roster_mode(self.roster_mode)

            def progress(message):
                self.statusbar.showMessage(message)
                QApplication.processEvents()

            new_players = self.player_mgr.scan_players(progress_callback=None if silent else progress)
            if not new_players and silent:
                self.players = previous_players
                self._player_index_map = previous_index_map
                self.statusbar.showMessage("没有发现稳定的实时名单变化，保留当前球员列表。")
                self._update_dashboard()
                return

            self.players = new_players
            self._player_index_map = {player.index: player for player in self.players}
            self.player_list.set_players(self.players)
            self._restore_selected_player(selected_identity)

            self._live_roster_signature = self.player_mgr.get_live_roster_signature(force_refresh=False)
            self._update_dashboard()

            if len(self.players) == 0:
                if silent:
                    self.statusbar.showMessage("实时名单探测没有解析到可用的球员表。")
                else:
                    debug_info = self._debug_table_scan()
                    QMessageBox.warning(
                        self,
                        "未找到球员",
                        f"当前没有在游戏内找到可用的球员数据。\n\n"
                        f"模块基址：0x{self.mem.base_address:X}\n"
                        f"配置指针：0x{self.config.player_table.base_pointer:X}\n\n"
                        f"调试信息：\n{debug_info}\n\n"
                        "请确认你已经进入 MyNBA / MyGM 且存档已载入，"
                        "不要停留在主菜单。",
                    )
            else:
                base = self.player_mgr._table_base
                base_str = f"0x{base:X}" if base else "unknown"
                self.statusbar.showMessage(f"已载入 {len(self.players)} 名球员（表基址：{base_str}）")
        finally:
            self._refresh_in_progress = False
            self.btn_refresh.setEnabled(self.player_mgr is not None)

    def _on_roster_mode_changed(self, *_args) -> None:
        if not hasattr(self, "roster_mode_combo"):
            return
        self.roster_mode = self.roster_mode_combo.currentData() or "auto"
        self._update_dashboard()
        if self.player_mgr is not None:
            self.player_mgr.set_roster_mode(self.roster_mode)
            self._refresh_players(force_rescan=True)

    def _debug_table_scan(self) -> str:
        lines = []
        mem = self.mem
        pt = self.config.player_table

        addr_rva = mem.base_address + pt.base_pointer
        addr_abs = pt.base_pointer

        val_rva = mem.read_uint64(addr_rva)
        val_abs = mem.read_uint64(addr_abs)

        lines.append(f"base+ptr (0x{addr_rva:X}): {f'0x{val_rva:X}' if val_rva else 'FAIL'}")
        lines.append(f"abs ptr  (0x{addr_abs:X}): {f'0x{val_abs:X}' if val_abs else 'FAIL'}")

        for label, table_val in [("base+ptr", val_rva), ("abs_ptr", val_abs)]:
            if not table_val:
                continue
            for i in range(3):
                rec = table_val + i * pt.stride
                last = mem.read_wstring(rec + pt.last_name_offset, pt.name_string_length)
                first = mem.read_wstring(rec + pt.first_name_offset, pt.name_string_length)
                if first or last:
                    lines.append(f"  {label}[{i}]: {first} {last}")
                    break
            else:
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

    def _on_player_selected(self, player_index: int) -> None:
        player = self._player_index_map.get(player_index)
        if player and self.player_mgr:
            self.attr_editor.load_player(player)
            self.statusbar.showMessage(f"已选中：{player.full_name}（{player.team_name}）")

    def _resolve_lock_green_team_target(self):
        current_player = self.attr_editor.current_player
        team_id = self.player_list.team_filter.currentData()
        team_name = self.player_list.team_filter.currentText()

        if team_id is not None and team_id != -1:
            if current_player and current_player.team_id == team_id:
                preferred_player = current_player
            else:
                preferred_player = next((player for player in self.players if player.team_id == team_id), None)
            return {
                "player": preferred_player,
                "team_id": int(team_id),
                "team_name": team_name,
                "source": "team filter",
            }

        if current_player is not None:
            return {
                "player": current_player,
                "team_id": current_player.team_id,
                "team_name": current_player.team_name,
                "source": "selected player",
            }

        return None

    def _open_batch_editor(self) -> None:
        if not self.players or self.player_mgr is None:
            QMessageBox.warning(self, "批量编辑", "请先连接游戏并载入球员列表。")
            return

        team_id = self.player_list.team_filter.currentData()
        batch_players = [player for player in self.players if player.team_id == team_id] if team_id not in (None, -1) else self.players

        dialog = BatchEditorDialog(self.config, self.player_mgr, batch_players, self)
        dialog.exec_()
        self._refresh_players(force_rescan=True)

    def _open_snapshot_tools(self) -> None:
        scope_players = self.player_list.get_filtered_players() if hasattr(self.player_list, "get_filtered_players") else list(self.players)
        search_text = self.player_list.search_input.text().strip() if hasattr(self.player_list, "search_input") else ""
        team_id = self.player_list.team_filter.currentData() if hasattr(self.player_list, "team_filter") else -1
        scope_parts = [f"球队：{self.player_list.team_filter.currentText()}" if team_id not in (None, -1) else "全部已载入球员"]
        if search_text:
            scope_parts.append(f"搜索：{search_text}")
        scope_name = " | ".join(scope_parts)

        dialog = SnapshotToolsDialog(
            self.config,
            self.player_mgr,
            scope_players,
            roster_mode=self.roster_mode,
            scope_name=scope_name,
            parent=self,
        )
        dialog.exec_()

    def _open_prospect_lab(self) -> None:
        scope_players = self.player_list.get_filtered_players() if hasattr(self.player_list, "get_filtered_players") else list(self.players)
        search_text = self.player_list.search_input.text().strip() if hasattr(self.player_list, "search_input") else ""
        team_id = self.player_list.team_filter.currentData() if hasattr(self.player_list, "team_filter") else -1
        scope_parts = [f"球队：{self.player_list.team_filter.currentText()}" if team_id not in (None, -1) else "全部已载入球员"]
        if search_text:
            scope_parts.append(f"搜索：{search_text}")
        scope_name = " | ".join(scope_parts)

        dialog = ProspectLabDialog(
            self.config,
            self.player_mgr,
            scope_players,
            roster_mode=self.roster_mode,
            scope_name=scope_name,
            parent=self,
        )
        dialog.exec_()
        if self.player_mgr is not None:
            self._refresh_players(force_rescan=False, silent=True, preserve_selection=True)

    def _load_custom_offsets(self) -> None:
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "选择偏移配置",
            "",
            "JSON Files (*.json)",
        )
        if not filepath:
            return

        try:
            self.config = initialize_offsets(filepath)
            QMessageBox.information(self, "载入成功", f"已载入 offsets 版本：{self.config.version}")
            if self.player_mgr:
                self.player_mgr.config = self.config
        except Exception as exc:
            QMessageBox.critical(self, "载入失败", f"载入偏移配置失败：\n{exc}")

    def _check_connection(self) -> None:
        if self.mem is None:
            return
        if not is_process_running():
            self.mem = None
            self.player_mgr = None
            self.attr_editor.set_player_manager(None)
            self._set_connection_badge("已断开", accent="#ff7b72", background="rgba(126, 32, 40, 0.22)")
            self.btn_refresh.setEnabled(False)
            self.btn_batch.setEnabled(False)
            self.players = []
            self._player_index_map = {}
            self.player_list.set_players([])
            self._live_roster_signature = None
            self._update_dashboard()
            self.statusbar.showMessage("游戏进程已关闭。")
            return
        self._sync_live_roster()

    def _sync_live_roster(self) -> None:
        if self.player_mgr is None or self._refresh_in_progress:
            return

        live_signature = self.player_mgr.get_live_roster_signature(force_refresh=False)
        if live_signature is None:
            return

        if self._live_roster_signature is None:
            self._live_roster_signature = live_signature
            return

        if live_signature != self._live_roster_signature:
            self.statusbar.showMessage("检测到实时名单变化，正在重新同步球员列表 ...")
            self._refresh_players(force_rescan=True, silent=True, preserve_selection=True)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.mem:
            self.mem.close()
        event.accept()
