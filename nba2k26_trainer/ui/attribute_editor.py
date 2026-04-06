"""属性编辑面板 - 分类 Tab 展示所有可编辑属性"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QScrollArea,
    QLabel, QSpinBox, QSlider, QGridLayout, QPushButton, QMessageBox,
    QGroupBox, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from ..core.offsets import OffsetConfig, AttributeDef
from ..models.player import Player, PlayerManager
from typing import Dict, Optional, Any, List


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

        # 属性名
        self.name_label = QLabel(self.attr.name)
        self.name_label.setFixedWidth(120)
        self.name_label.setToolTip(self.attr.description)
        layout.addWidget(self.name_label)

        # 滑块 (仅数值型)
        if self.attr.type not in ("wstring", "ascii"):
            self.slider = QSlider(Qt.Horizontal)
            self.slider.setMinimum(self.attr.min_val)
            self.slider.setMaximum(self.attr.max_val)
            self.slider.valueChanged.connect(self._on_slider_changed)
            layout.addWidget(self.slider, 1)
        else:
            self.slider = None
            layout.addStretch(1)

        # 数值输入
        self.spin = QSpinBox()
        self.spin.setMinimum(self.attr.min_val)
        self.spin.setMaximum(self.attr.max_val)
        self.spin.setFixedWidth(80)
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
        self.player_info.setText(
            f"{player.full_name}  |  {player.team_name}  |  {player.position}  |  "
            f"OVR {player.overall}  |  {player.age}岁"
        )

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
        """全部属性设为最大值"""
        for category in ["进攻能力", "防守能力", "体能属性", "篮球智商"]:
            self._set_category_max(category)

    def set_player_manager(self, mgr: PlayerManager):
        self.player_mgr = mgr
