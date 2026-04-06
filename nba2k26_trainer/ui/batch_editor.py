"""批量编辑对话框"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QCheckBox, QGroupBox, QMessageBox,
    QProgressBar
)
from PyQt5.QtCore import Qt

from ..models.player import Player, PlayerManager
from ..core.offsets import OffsetConfig
from typing import List


class BatchEditorDialog(QDialog):
    """批量编辑对话框"""

    def __init__(self, config: OffsetConfig, player_mgr: PlayerManager,
                 players: List[Player], parent=None):
        super().__init__(parent)
        self.config = config
        self.player_mgr = player_mgr
        self.players = players
        self.setWindowTitle("批量编辑")
        self.setMinimumWidth(400)
        self.setMinimumHeight(350)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 目标信息
        info = QLabel(f"将对 {len(self.players)} 名球员进行批量修改")
        info.setStyleSheet("font-size: 14px; font-weight: bold; color: #f77f00;")
        layout.addWidget(info)

        # 快捷操作
        group_quick = QGroupBox("快捷操作")
        quick_layout = QVBoxLayout(group_quick)

        btn_all_99 = QPushButton("全部能力值设为 99")
        btn_all_99.setObjectName("btn_max")
        btn_all_99.clicked.connect(self._batch_all_99)
        quick_layout.addWidget(btn_all_99)

        btn_young = QPushButton("全部年龄设为 20 岁")
        btn_young.clicked.connect(lambda: self._batch_set_attr("年龄", 20))
        quick_layout.addWidget(btn_young)

        btn_potential = QPushButton("全部潜力设为 99")
        btn_potential.clicked.connect(lambda: self._batch_set_attr("潜力", 99))
        quick_layout.addWidget(btn_potential)

        btn_stamina = QPushButton("全部耐力设为 99")
        btn_stamina.clicked.connect(lambda: self._batch_set_attr("耐力", 99))
        quick_layout.addWidget(btn_stamina)

        btn_badges = QPushButton("全部徽章设为名人堂")
        btn_badges.setObjectName("btn_max")
        btn_badges.clicked.connect(self._batch_all_badges_hof)
        quick_layout.addWidget(btn_badges)

        btn_hotzones = QPushButton("全部热区设为极热")
        btn_hotzones.clicked.connect(self._batch_all_hotzones)
        quick_layout.addWidget(btn_hotzones)

        layout.addWidget(group_quick)

        # 自定义修改
        group_custom = QGroupBox("自定义修改")
        custom_layout = QHBoxLayout(group_custom)

        self.attr_combo = QComboBox()
        for attr in self.config.all_attributes():
            if attr.type not in ("wstring", "ascii"):
                self.attr_combo.addItem(f"{attr.category} - {attr.name}", attr.name)
        custom_layout.addWidget(self.attr_combo, 2)

        self.value_spin = QSpinBox()
        self.value_spin.setMinimum(0)
        self.value_spin.setMaximum(99999)
        self.value_spin.setValue(99)
        custom_layout.addWidget(self.value_spin, 1)

        btn_custom = QPushButton("应用")
        btn_custom.setObjectName("btn_apply")
        btn_custom.clicked.connect(self._batch_custom)
        custom_layout.addWidget(btn_custom)

        layout.addWidget(group_custom)

        # 进度条
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # 关闭
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def _batch_set_attr(self, attr_name: str, value: int):
        """批量设置单个属性"""
        attr = self.config.get_attribute(attr_name)
        if not attr:
            QMessageBox.warning(self, "错误", f"找不到属性: {attr_name}")
            return

        self.progress.setVisible(True)
        self.progress.setMaximum(len(self.players))
        success = 0

        for i, player in enumerate(self.players):
            if self.player_mgr.write_attribute(player, attr, value):
                success += 1
            self.progress.setValue(i + 1)

        self.progress.setVisible(False)
        QMessageBox.information(
            self, "完成",
            f"已将 {success}/{len(self.players)} 名球员的{attr_name}设为 {value}"
        )

    def _batch_all_99(self):
        """全部能力值设为 99"""
        categories = ["进攻能力", "防守能力", "体能属性", "篮球智商"]
        self.progress.setVisible(True)
        self.progress.setMaximum(len(self.players))

        for i, player in enumerate(self.players):
            self.player_mgr.set_all_to_max(player, categories)
            self.progress.setValue(i + 1)

        self.progress.setVisible(False)
        QMessageBox.information(self, "完成", f"已将 {len(self.players)} 名球员的能力值全部设为最大")

    def _batch_all_badges_hof(self):
        """全部徽章设为名人堂"""
        self.progress.setVisible(True)
        self.progress.setMaximum(len(self.players))

        for i, player in enumerate(self.players):
            self.player_mgr.set_all_to_max(player, ["徽章"])
            self.progress.setValue(i + 1)

        self.progress.setVisible(False)
        QMessageBox.information(self, "完成", f"已将 {len(self.players)} 名球员的徽章全部设为名人堂")

    def _batch_all_hotzones(self):
        """全部热区设为极热"""
        self.progress.setVisible(True)
        self.progress.setMaximum(len(self.players))

        for i, player in enumerate(self.players):
            self.player_mgr.set_all_to_max(player, ["热区"])
            self.progress.setValue(i + 1)

        self.progress.setVisible(False)
        QMessageBox.information(self, "完成", f"已将 {len(self.players)} 名球员的热区全部设为极热")

    def _batch_custom(self):
        """自定义批量修改"""
        attr_name = self.attr_combo.currentData()
        value = self.value_spin.value()
        if attr_name:
            self._batch_set_attr(attr_name, value)
