"""属性编辑面板 - 分类 Tab 展示所有可编辑属性"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QScrollArea,
    QLabel, QSpinBox, QDoubleSpinBox, QSlider, QGridLayout, QPushButton,
    QMessageBox, QGroupBox, QFrame
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont

from ..core.offsets import OffsetConfig, AttributeDef
from ..models.player import Player, PlayerManager
from typing import Callable, Dict, Optional, Any, List


class AttributeRow(QWidget):
    """单个属性编辑行"""

    value_changed = pyqtSignal(str, int)  # (attr_name, new_value)

    def __init__(self, attr: AttributeDef, parent=None):
        super().__init__(parent)
        self.attr = attr
        self._original_value: Optional[int] = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)

        self._is_float = self.attr.type == "float"
        numeric_range = self.attr.max_val - self.attr.min_val
        self._show_slider = (
            self.attr.type not in ("wstring", "ascii", "float")
            and numeric_range <= 1000
        )

        # 属性名
        self.name_label = QLabel(self.attr.name)
        self.name_label.setFixedWidth(120)
        self.name_label.setToolTip(self.attr.description)
        layout.addWidget(self.name_label)

        # 滑块 (仅数值型, 非 float)
        if self._show_slider:
            self.slider = QSlider(Qt.Horizontal)
            self.slider.setMinimum(self.attr.min_val)
            self.slider.setMaximum(self.attr.max_val)
            self.slider.valueChanged.connect(self._on_slider_changed)
            layout.addWidget(self.slider, 1)
        else:
            self.slider = None
            layout.addStretch(1)

        # 数值输入
        if self._is_float:
            self.spin = QDoubleSpinBox()
            self.spin.setDecimals(2)
            self.spin.setMinimum(float(self.attr.min_val))
            self.spin.setMaximum(float(self.attr.max_val))
            self.spin.setSingleStep(0.5)
        else:
            self.spin = QSpinBox()
            self.spin.setMinimum(self.attr.min_val)
            self.spin.setMaximum(self.attr.max_val)
            self.spin.setAccelerated(True)
            if self.attr.max_val >= 10000000:
                self.spin.setSingleStep(1000000)
            elif self.attr.max_val >= 1000000:
                self.spin.setSingleStep(100000)
            elif self.attr.max_val >= 10000:
                self.spin.setSingleStep(1000)
        self.spin.setFixedWidth(100)
        self.spin.valueChanged.connect(self._on_spin_changed)
        layout.addWidget(self.spin)

        # 原始值标签
        self.original_label = QLabel("")
        self.original_label.setFixedWidth(50)
        self.original_label.setStyleSheet("color: #888;")
        self.original_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.original_label)

    def _on_slider_changed(self, value: int):
        if self.spin.value() != value:
            self.spin.blockSignals(True)
            self.spin.setValue(value)
            self.spin.blockSignals(False)
        self._check_modified()
        self.value_changed.emit(self.attr.name, value)

    def _on_spin_changed(self, value: int):
        if self.slider and self.slider.value() != value:
            self.slider.blockSignals(True)
            self.slider.setValue(value)
            self.slider.blockSignals(False)
        self._check_modified()
        self.value_changed.emit(self.attr.name, value)

    def _check_modified(self):
        if self._original_value is not None and self.spin.value() != self._original_value:
            self.setStyleSheet("background-color: rgba(247, 127, 0, 0.15); border-radius: 4px;")
        else:
            self.setStyleSheet("")

    def set_value(self, value: int, is_original: bool = False):
        """设置属性值"""
        if value is None:
            value = 0
        value = max(self.attr.min_val, min(self.attr.max_val, int(value)))

        self.spin.blockSignals(True)
        self.spin.setValue(value)
        self.spin.blockSignals(False)

        if self.slider:
            self.slider.blockSignals(True)
            self.slider.setValue(value)
            self.slider.blockSignals(False)

        if is_original:
            self._original_value = value
            self.original_label.setText(str(value))
            self.setStyleSheet("")

    def get_value(self) -> int:
        return self.spin.value()

    def is_modified(self) -> bool:
        return self._original_value is not None and self.spin.value() != self._original_value

    def reset(self):
        if self._original_value is not None:
            self.set_value(self._original_value)
            self.setStyleSheet("")


class AttributeEditorWidget(QWidget):
    """属性编辑面板"""

    def __init__(self, config: OffsetConfig, player_mgr: Optional[PlayerManager] = None, parent=None):
        super().__init__(parent)
        self.config = config
        self.player_mgr = player_mgr
        self.current_player: Optional[Player] = None
        self._attr_rows: Dict[str, AttributeRow] = {}
        self._perfect_shot_team_resolver: Optional[Callable[[], Optional[Dict[str, Any]]]] = None
        self._perfect_shot_sustain_timer = QTimer(self)
        self._perfect_shot_sustain_timer.setTimerType(Qt.PreciseTimer)
        self._perfect_shot_sustain_timer.setInterval(1)
        self._perfect_shot_sustain_timer.timeout.connect(self._on_perfect_shot_sustain_tick)
        self._perfect_shot_refresh_timer = QTimer(self)
        self._perfect_shot_refresh_timer.setTimerType(Qt.PreciseTimer)
        self._perfect_shot_refresh_timer.setInterval(100)
        self._perfect_shot_refresh_timer.timeout.connect(self._on_perfect_shot_refresh_tick)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 球员信息头
        self.player_info = QLabel("请选择一名球员")
        self.player_info.setObjectName("title")
        layout.addWidget(self.player_info)

        # Tab 面板
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget, 1)

        for category in self.config.categories():
            attrs = self.config.attributes[category]
            tab = self._create_category_tab(category, attrs)
            self.tab_widget.addTab(tab, category)

        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.btn_apply = QPushButton("应用修改")
        self.btn_apply.setObjectName("btn_apply")
        self.btn_apply.clicked.connect(self._on_apply)
        btn_layout.addWidget(self.btn_apply)

        self.btn_reset = QPushButton("还原")
        self.btn_reset.clicked.connect(self._on_reset)
        btn_layout.addWidget(self.btn_reset)

        self.btn_max_offense = QPushButton("进攻全满")
        self.btn_max_offense.setObjectName("btn_max")
        self.btn_max_offense.clicked.connect(lambda: self._set_category_max("进攻能力"))
        btn_layout.addWidget(self.btn_max_offense)

        self.btn_max_defense = QPushButton("防守全满")
        self.btn_max_defense.setObjectName("btn_max")
        self.btn_max_defense.clicked.connect(lambda: self._set_category_max("防守能力"))
        btn_layout.addWidget(self.btn_max_defense)

        self.btn_max_all = QPushButton("全部满属性")
        self.btn_max_all.setObjectName("btn_max")
        self.btn_max_all.clicked.connect(self._set_all_max)
        btn_layout.addWidget(self.btn_max_all)

        self.btn_god = QPushButton("⚡ 超级模式")
        self.btn_god.setObjectName("btn_god")
        self.btn_god.setToolTip(
            "一键开启超级模式：全能力99 + 全徽章满级\n"
            "+ 全投篮/突破/防守倾向拉满 + 全耐久满\n"
            "+ 潜力拉满 → 投篮必进、突破无解"
        )
        self.btn_god.clicked.connect(self._apply_god_mode)
        btn_layout.addWidget(self.btn_god)

        self.btn_perfect_shot = QPushButton("Lock Green Beta")
        self.btn_perfect_shot.setObjectName("btn_max")
        self.btn_perfect_shot.setCheckable(True)
        self.btn_perfect_shot.setToolTip(
            "Targets the current MyGM team during an active game.\n"
            "It prefers the current team filter, then falls back to the selected player.\n"
            "It zeroes the live AI timing error buffer and boosts only the in-match copies for your team.\n"
            "It does not modify the roster table or permanent player attributes.\n"
            "Beta: this is safer than the old global lock, but it is still experimental."
        )
        self.btn_perfect_shot.clicked.connect(self._toggle_perfect_shot_beta)
        btn_layout.addWidget(self.btn_perfect_shot)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def _create_category_tab(self, category: str, attrs: List[AttributeDef]) -> QWidget:
        """创建一个属性分类 Tab"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(2)

        for attr in attrs:
            row = AttributeRow(attr)
            self._attr_rows[attr.name] = row
            layout.addWidget(row)

        layout.addStretch()
        scroll.setWidget(container)
        return scroll

    def load_player(self, player: Player):
        """加载球员数据到编辑面板"""
        self.current_player = player
        info_parts = [player.full_name]
        if player.team_name:
            info_parts.append(player.team_name)
        info_parts.append(f"OVR {player.overall}")
        if player.age > 0:
            info_parts.append(f"{player.age}岁 (生于{player.birth_year})")
        self.player_info.setText("  |  ".join(info_parts))

        if self.player_mgr is None:
            return

        values = self.player_mgr.read_all_attributes(player)
        for attr_name, row in self._attr_rows.items():
            val = values.get(attr_name)
            if val is not None:
                row.set_value(val, is_original=True)

    def _on_apply(self):
        """应用所有修改"""
        if self.current_player is None or self.player_mgr is None:
            QMessageBox.warning(self, "警告", "请先选择一名球员")
            return

        modified = {}
        for attr_name, row in self._attr_rows.items():
            if row.is_modified():
                modified[attr_name] = row.get_value()

        if not modified:
            QMessageBox.information(self, "提示", "没有修改任何属性")
            return

        results = self.player_mgr.write_all_attributes(self.current_player, modified)
        success = sum(1 for v in results.values() if v)
        failed = sum(1 for v in results.values() if not v)

        if failed > 0:
            QMessageBox.warning(
                self, "部分失败",
                f"成功修改 {success} 项，失败 {failed} 项"
            )
        else:
            QMessageBox.information(self, "成功", f"已成功修改 {success} 项属性")

        # 重新加载以更新原始值
        self.load_player(self.current_player)

    def _on_reset(self):
        """还原所有修改"""
        for row in self._attr_rows.values():
            row.reset()

    def _set_category_max(self, category: str):
        """将某分类所有属性设为最大值"""
        if category not in self.config.attributes:
            return
        for attr in self.config.attributes[category]:
            if attr.name in self._attr_rows and attr.type not in ("wstring", "ascii"):
                self._attr_rows[attr.name].set_value(attr.max_val)

    def _set_all_max(self):
        """全部属性设为最大值（能力值相关分类）"""
        for category in ["进攻能力", "防守能力", "体能属性", "篮球智商"]:
            self._set_category_max(category)
        # 徽章全满
        for category in self.config.categories():
            if "徽章" in category:
                self._set_category_max(category)

    def _apply_god_mode(self):
        """超级模式 - 直接写入内存，全属性拉满"""
        if self.current_player is None or self.player_mgr is None:
            QMessageBox.warning(self, "警告", "请先选择一名球员")
            return

        reply = QMessageBox.question(
            self, "超级模式",
            f"确定要对 {self.current_player.full_name} 开启超级模式？\n\n"
            "将会设置：\n"
            "• 全部能力值 → 99\n"
            "• 全部徽章 → 最高等级\n"
            "• 全部投篮/突破/防守倾向 → 最大值\n"
            "• 全部耐久性 → 99\n"
            "• 潜力/成长 → 最大值\n\n"
            "效果：投篮几乎必进，包括半场三分",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        count = self.player_mgr.apply_god_mode(self.current_player)
        summary = self.player_mgr.summarize_live_gameplay_state(self.current_player)
        compact_count = int(summary.get("match_compact_entries", 0) or 0)
        compact_bases = summary.get("match_compact_bases", [])
        attr_summary = summary.get("attributes", {})

        lines = [
            f"Updated {count} attributes for {self.current_player.full_name}.",
        ]
        if compact_count:
            compact_text = ", ".join(compact_bases[:3])
            if len(compact_bases) > 3:
                compact_text += ", ..."
            lines.append(f"In-match compact copies synced: {compact_count}")
            if compact_text:
                lines.append(f"Match copy bases: {compact_text}")
        else:
            lines.append("No in-match compact copies were found for this player right now.")

        for label in (
            "Three-Point Shot",
            "Mid-Range Shot",
            "Driving Layup",
            "Deadeye",
            "Spot Up Drive",
            "Contest Shot",
        ):
            values = attr_summary.get(label)
            if not values:
                continue
            match_values = values.get("match_copies") or []
            mirror_text = ", ".join(str(value) for value in match_values) if match_values else "n/a"
            lines.append(f"{label}: {values.get('current')} | Match copies: {mirror_text}")

        QMessageBox.information(self, "God Mode Applied", "\n".join(lines))
        # 重新加载显示
        self.load_player(self.current_player)

    def _set_perfect_shot_button_state(self, active: bool) -> None:
        self.btn_perfect_shot.blockSignals(True)
        self.btn_perfect_shot.setChecked(active)
        self.btn_perfect_shot.setText("Stop Lock Green Beta" if active else "Lock Green Beta")
        self.btn_perfect_shot.blockSignals(False)

    def _stop_perfect_shot_timers(self) -> None:
        self._perfect_shot_sustain_timer.stop()
        self._perfect_shot_refresh_timer.stop()

    def set_perfect_shot_team_resolver(self, resolver: Optional[Callable[[], Optional[Dict[str, Any]]]]) -> None:
        self._perfect_shot_team_resolver = resolver

    def _resolve_perfect_shot_target(self) -> Optional[Dict[str, Any]]:
        if self._perfect_shot_team_resolver is not None:
            resolved = self._perfect_shot_team_resolver()
            if resolved:
                return resolved

        if self.current_player is None:
            return None

        return {
            "player": self.current_player,
            "team_id": self.current_player.team_id,
            "team_name": self.current_player.team_name,
            "source": "selected player",
        }

    def _toggle_perfect_shot_beta(self, checked: bool) -> None:
        if self.player_mgr is None:
            self._set_perfect_shot_button_state(False)
            QMessageBox.warning(self, "Warning", "Connect the game first.")
            return

        if not checked:
            self._stop_perfect_shot_timers()
            self.player_mgr.stop_perfect_shot_beta()
            self._set_perfect_shot_button_state(False)
            return

        target = self._resolve_perfect_shot_target()
        if target is None:
            self._set_perfect_shot_button_state(False)
            QMessageBox.warning(self, "Lock Green Beta", "Select a player or filter your MyGM team first.")
            return

        summary = self.player_mgr.start_perfect_shot_beta_for_team(
            team_id=target.get("team_id"),
            team_name=target.get("team_name"),
            preferred_player=target.get("player"),
        )
        if not summary.get("active"):
            self._set_perfect_shot_button_state(False)
            QMessageBox.warning(
                self,
                "Lock Green Beta",
                str(summary.get("error") or "No live in-match shot entry was found."),
            )
            return

        self._perfect_shot_sustain_timer.start()
        self._perfect_shot_refresh_timer.start()
        self._set_perfect_shot_button_state(True)
        target_source = str(target.get("source") or "auto")

        lines = [
            "Lock Green Beta is now running for your MyGM team.",
            f"Team: {summary.get('target_team_name') or 'n/a'}",
            f"Target source: {target_source}",
            f"Representative player: {summary.get('representative_player') or 'n/a'}",
            f"Runtime entry: {summary.get('entry_base') or 'n/a'}",
            f"Runtime team block: {summary.get('team_block_index') if summary.get('team_block_index') is not None else 'unresolved'}",
            f"AI timing delta zeroed: {'yes' if summary.get('ai_delta_written') else 'no'}",
            "Runtime patches:"
            f" AI-team={'yes' if summary.get('ai_team_delta_written') else 'no'}"
            f" Human-team={'yes' if summary.get('human_team_delta_written') else 'no'}"
            f" Coverage={'yes' if summary.get('coverage_delta_written') else 'no'}"
            f" Impact={'yes' if summary.get('impact_delta_written') else 'no'}",
            f"Shot tuning patches applied: {summary.get('runtime_patch_writes', 0)}",
            "Shared runtime shot-result patches are active for this live game.",
            f"Legacy live shot-state patches: {summary.get('legacy_state_writes', 0)} writes",
            f"Temporary roster shooting boosts: {summary.get('roster_boost_players', 0)} players / {summary.get('roster_boost_writes', 0)} writes",
            f"Live match players boosted: {summary.get('match_boost_players', 0)}",
            f"Live match entries boosted: {summary.get('match_boost_entries', 0)}",
            f"Live match writes applied: {summary.get('match_boost_writes', 0)}",
            f"Opponent dampening team: {summary.get('opponent_team_name') or 'not resolved'}",
            f"Opponent roster dampening: {summary.get('opponent_roster_boost_players', 0)} players / {summary.get('opponent_roster_boost_writes', 0)} writes",
            f"Opponent live match dampening: {summary.get('opponent_match_boost_players', 0)} players / {summary.get('opponent_match_boost_entries', 0)} entries / {summary.get('opponent_match_boost_writes', 0)} writes",
            "All temporary Lock Green boosts are restored when you stop the toggle.",
        ]
        QMessageBox.information(self, "Lock Green Beta Enabled", "\n".join(lines))

    def _on_perfect_shot_sustain_tick(self) -> None:
        if self.player_mgr is None:
            self._stop_perfect_shot_timers()
            self._set_perfect_shot_button_state(False)
            return

        summary = self.player_mgr.enforce_perfect_shot_beta()
        if not summary.get("active"):
            self._stop_perfect_shot_timers()
            self._set_perfect_shot_button_state(False)

    def _on_perfect_shot_refresh_tick(self) -> None:
        if self.player_mgr is None:
            self._stop_perfect_shot_timers()
            self._set_perfect_shot_button_state(False)
            return

        summary = self.player_mgr.refresh_perfect_shot_beta()
        if not summary.get("active"):
            self._stop_perfect_shot_timers()
            self._set_perfect_shot_button_state(False)
            reason = summary.get("reason")
            if reason:
                QMessageBox.information(self, "Lock Green Beta Stopped", str(reason))

    def set_player_manager(self, mgr: Optional[PlayerManager]):
        if mgr is None:
            self._stop_perfect_shot_timers()
            self._set_perfect_shot_button_state(False)
            if self.player_mgr is not None:
                self.player_mgr.stop_perfect_shot_beta(restore_live_memory=False)
        self.player_mgr = mgr
