"""Batch editing dialog for applying repeatable roster changes."""

from __future__ import annotations

from typing import Dict, Iterable, List

from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from ..core.offsets import OffsetConfig
from ..models.player import Player, PlayerManager
from ..presets import resolve_preset_values
from .preset_dialog import PresetChooserDialog


class BatchEditorDialog(QDialog):
    """Apply bulk edits to the currently loaded team or roster scope."""

    def __init__(self, config: OffsetConfig, player_mgr: PlayerManager, players: List[Player], parent=None):
        super().__init__(parent)
        self.config = config
        self.player_mgr = player_mgr
        self.players = players
        self.setWindowTitle("Batch Edit")
        self.setMinimumWidth(440)
        self.setMinimumHeight(420)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        info = QLabel(f"Ready to edit {len(self.players)} players in the current scope.")
        info.setStyleSheet("font-size: 14px; font-weight: bold; color: #f77f00;")
        layout.addWidget(info)

        group_quick = QGroupBox("Quick Actions")
        quick_layout = QVBoxLayout(group_quick)

        btn_all_99 = QPushButton("Max Core Ratings")
        btn_all_99.setObjectName("btn_max")
        btn_all_99.clicked.connect(self._batch_all_99)
        quick_layout.addWidget(btn_all_99)

        btn_potential = QPushButton("Max Potential")
        btn_potential.clicked.connect(lambda: self._batch_set_attr("Potential", 99))
        quick_layout.addWidget(btn_potential)

        btn_stamina = QPushButton("Max Stamina")
        btn_stamina.clicked.connect(lambda: self._batch_set_attr("Stamina", 99))
        quick_layout.addWidget(btn_stamina)

        btn_badges = QPushButton("All Badges to Hall of Fame")
        btn_badges.setObjectName("btn_max")
        btn_badges.clicked.connect(self._batch_all_badges_hof)
        quick_layout.addWidget(btn_badges)

        btn_god = QPushButton("Full God Mode")
        btn_god.setObjectName("btn_god")
        btn_god.clicked.connect(self._batch_god_mode)
        quick_layout.addWidget(btn_god)

        helper = QLabel(
            "The old one-off shortcuts for forcing one birth year or maxing hot zones were removed. "
            "Presets cover those use cases in a safer, more reusable way."
        )
        helper.setWordWrap(True)
        helper.setStyleSheet("color: #b8b8b8;")
        quick_layout.addWidget(helper)

        layout.addWidget(group_quick)

        group_presets = QGroupBox("Roles & Presets")
        preset_layout = QVBoxLayout(group_presets)

        preset_info = QLabel(
            "Use a built-in role preset or import a JSON preset exported from the player editor. "
            "This is the recommended replacement for niche batch shortcuts."
        )
        preset_info.setWordWrap(True)
        preset_layout.addWidget(preset_info)

        btn_apply_preset = QPushButton("Apply Preset...")
        btn_apply_preset.setObjectName("btn_apply")
        btn_apply_preset.clicked.connect(self._batch_apply_preset)
        preset_layout.addWidget(btn_apply_preset)

        layout.addWidget(group_presets)

        group_custom = QGroupBox("Custom Attribute")
        custom_layout = QHBoxLayout(group_custom)

        self.attr_combo = QComboBox()
        for attr in self.config.all_attributes():
            if attr.type in ("wstring", "ascii"):
                continue
            label = attr.description or attr.name
            self.attr_combo.addItem(f"{attr.category} - {label}", attr.name)
        custom_layout.addWidget(self.attr_combo, 2)

        self.value_spin = QSpinBox()
        self.value_spin.setMinimum(0)
        self.value_spin.setMaximum(99999)
        self.value_spin.setValue(99)
        custom_layout.addWidget(self.value_spin, 1)

        btn_custom = QPushButton("Apply")
        btn_custom.setObjectName("btn_apply")
        btn_custom.clicked.connect(self._batch_custom)
        custom_layout.addWidget(btn_custom)

        layout.addWidget(group_custom)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def _find_attribute(self, key: str):
        return self.config.find_attribute_by_description(key) or self.config.get_attribute(key)

    def _categories_with_descriptions(self, samples: Iterable[str]) -> List[str]:
        wanted = {sample.strip().lower() for sample in samples}
        categories: List[str] = []
        for category, attrs in self.config.attributes.items():
            descriptions = {(attr.description or attr.name).strip().lower() for attr in attrs}
            if wanted & descriptions:
                categories.append(category)
        return categories

    def _apply_values_to_players(self, values: Dict[str, int], action_label: str) -> None:
        if not values:
            QMessageBox.information(self, "Batch Edit", "Nothing to apply for this action.")
            return

        self.progress.setVisible(True)
        self.progress.setMaximum(len(self.players))
        successful_players = 0
        total_writes = 0
        failed_writes = 0

        for index, player in enumerate(self.players, start=1):
            results = self.player_mgr.write_all_attributes(player, values)
            write_count = sum(1 for ok in results.values() if ok)
            fail_count = sum(1 for ok in results.values() if not ok)
            if write_count > 0:
                successful_players += 1
            total_writes += write_count
            failed_writes += fail_count
            self.progress.setValue(index)

        self.progress.setVisible(False)
        QMessageBox.information(
            self,
            "Batch Edit Complete",
            "\n".join(
                [
                    action_label,
                    f"Players updated: {successful_players}/{len(self.players)}",
                    f"Successful writes: {total_writes}",
                    f"Failed writes: {failed_writes}",
                ]
            ),
        )

    def _batch_set_attr(self, attr_key: str, value: int) -> None:
        attr = self._find_attribute(attr_key)
        if attr is None:
            QMessageBox.warning(self, "Batch Edit", f"Cannot find attribute: {attr_key}")
            return
        self._apply_values_to_players({attr.name: value}, f"Applied {attr.description or attr.name} = {value}")

    def _batch_all_99(self) -> None:
        categories = self._categories_with_descriptions(
            [
                "Close Shot",
                "Interior Defense",
                "Speed",
                "Shot IQ",
            ]
        )
        if not categories:
            QMessageBox.warning(self, "Batch Edit", "Could not resolve the core ratings categories.")
            return

        self.progress.setVisible(True)
        self.progress.setMaximum(len(self.players))
        for index, player in enumerate(self.players, start=1):
            self.player_mgr.set_all_to_max(player, categories)
            self.progress.setValue(index)
        self.progress.setVisible(False)

        QMessageBox.information(
            self,
            "Batch Edit Complete",
            f"Maxed the core ratings categories for {len(self.players)} players.",
        )

    def _batch_all_badges_hof(self) -> None:
        badge_categories = self._categories_with_descriptions(
            [
                "Aerial Wizard",
                "Deadeye",
                "Bailout",
            ]
        )
        if not badge_categories:
            QMessageBox.warning(self, "Batch Edit", "Could not resolve the badge categories.")
            return

        self.progress.setVisible(True)
        self.progress.setMaximum(len(self.players))
        for index, player in enumerate(self.players, start=1):
            self.player_mgr.set_all_to_max(player, badge_categories)
            self.progress.setValue(index)
        self.progress.setVisible(False)

        QMessageBox.information(
            self,
            "Batch Edit Complete",
            f"Set every badge category to its maximum tier for {len(self.players)} players.",
        )

    def _batch_god_mode(self) -> None:
        reply = QMessageBox.question(
            self,
            "Full God Mode",
            "\n".join(
                [
                    f"Apply full God Mode to {len(self.players)} players?",
                    "",
                    "This maxes ratings, badges, tendencies, durability, and growth values.",
                ]
            ),
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self.progress.setVisible(True)
        self.progress.setMaximum(len(self.players))
        for index, player in enumerate(self.players, start=1):
            self.player_mgr.apply_god_mode(player)
            self.progress.setValue(index)
        self.progress.setVisible(False)

        QMessageBox.information(
            self,
            "Batch Edit Complete",
            f"Applied God Mode to {len(self.players)} players.",
        )

    def _batch_apply_preset(self) -> None:
        dialog = PresetChooserDialog(self.config, self)
        if dialog.exec_() != QDialog.Accepted:
            return

        preset = dialog.selected_preset()
        if preset is None:
            return

        values, unresolved = resolve_preset_values(self.config, preset.values_by_description)
        if not values:
            QMessageBox.warning(self, "Batch Edit", "The selected preset did not map to any writable attributes.")
            return

        label = f"Applied preset '{preset.name}'."
        if unresolved:
            label += f"\nSkipped {len(unresolved)} entries that do not exist in the current offsets."
        self._apply_values_to_players(values, label)

    def _batch_custom(self) -> None:
        attr_name = self.attr_combo.currentData()
        value = self.value_spin.value()
        if attr_name:
            self._batch_set_attr(attr_name, value)
