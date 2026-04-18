"""Tabbed attribute editor and live tools for the trainer UI."""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, List, Optional

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.offsets import AttributeDef, OffsetConfig
from ..models.player import Player, PlayerManager
from ..presets import export_custom_preset, resolve_preset_values
from .preset_dialog import PresetChooserDialog


class AttributeRow(QWidget):
    """One editable attribute row with a spinbox and optional slider."""

    value_changed = pyqtSignal(str, object)

    def __init__(self, attr: AttributeDef, parent=None):
        super().__init__(parent)
        self.attr = attr
        self._is_float = self.attr.type == "float"
        self._original_value: Optional[float] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)

        numeric_range = self.attr.max_val - self.attr.min_val
        self._show_slider = (
            self.attr.type not in ("wstring", "ascii", "float")
            and numeric_range <= 1000
        )

        self.name_label = QLabel(self.attr.name)
        self.name_label.setFixedWidth(120)
        self.name_label.setToolTip(self.attr.description)
        layout.addWidget(self.name_label)

        if self._show_slider:
            self.slider = QSlider(Qt.Horizontal)
            self.slider.setMinimum(self.attr.min_val)
            self.slider.setMaximum(self.attr.max_val)
            self.slider.valueChanged.connect(self._on_slider_changed)
            layout.addWidget(self.slider, 1)
        else:
            self.slider = None
            layout.addStretch(1)

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

        self.original_label = QLabel("")
        self.original_label.setFixedWidth(64)
        self.original_label.setStyleSheet("color: #888;")
        self.original_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.original_label)

    def _on_slider_changed(self, value: int) -> None:
        if self.spin.value() != value:
            self.spin.blockSignals(True)
            self.spin.setValue(value)
            self.spin.blockSignals(False)
        self._check_modified()
        self.value_changed.emit(self.attr.name, value)

    def _on_spin_changed(self, value: Any) -> None:
        if self.slider and self.slider.value() != int(value):
            self.slider.blockSignals(True)
            self.slider.setValue(int(value))
            self.slider.blockSignals(False)
        self._check_modified()
        self.value_changed.emit(self.attr.name, value)

    def _check_modified(self) -> None:
        if self._original_value is None:
            self.setStyleSheet("")
            return

        current = float(self.spin.value())
        if abs(current - float(self._original_value)) > 1e-6:
            self.setStyleSheet("background-color: rgba(247, 127, 0, 0.15); border-radius: 4px;")
        else:
            self.setStyleSheet("")

    def set_value(self, value: Any, is_original: bool = False) -> None:
        if value is None:
            value = 0.0 if self._is_float else 0

        if self._is_float:
            clamped = max(float(self.attr.min_val), min(float(self.attr.max_val), float(value)))
        else:
            clamped = max(self.attr.min_val, min(self.attr.max_val, int(value)))

        self.spin.blockSignals(True)
        self.spin.setValue(clamped)
        self.spin.blockSignals(False)

        if self.slider is not None:
            self.slider.blockSignals(True)
            self.slider.setValue(int(clamped))
            self.slider.blockSignals(False)

        if is_original:
            self._original_value = float(clamped)
            if self._is_float:
                self.original_label.setText(f"{clamped:.2f}")
            else:
                self.original_label.setText(str(int(clamped)))
            self.setStyleSheet("")

    def get_value(self) -> Any:
        return self.spin.value()

    def is_modified(self) -> bool:
        if self._original_value is None:
            return False
        return abs(float(self.spin.value()) - float(self._original_value)) > 1e-6

    def reset(self) -> None:
        if self._original_value is not None:
            self.set_value(self._original_value)
            self.setStyleSheet("")


class AttributeEditorWidget(QWidget):
    """Tabbed player editor plus preset and experimental live-tool controls."""

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

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.player_info = QLabel("Select a player to inspect attributes.")
        self.player_info.setObjectName("title")
        layout.addWidget(self.player_info)

        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget, 1)

        for category in self.config.categories():
            attrs = self.config.attributes[category]
            tab = self._create_category_tab(category, attrs)
            self.tab_widget.addTab(tab, category)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)

        self.btn_apply = QPushButton("Apply Changes")
        self.btn_apply.setObjectName("btn_apply")
        self.btn_apply.clicked.connect(self._on_apply)
        button_row.addWidget(self.btn_apply)

        self.btn_reset = QPushButton("Reset")
        self.btn_reset.clicked.connect(self._on_reset)
        button_row.addWidget(self.btn_reset)

        self.btn_max_offense = QPushButton("Max Offense")
        self.btn_max_offense.setObjectName("btn_max")
        self.btn_max_offense.clicked.connect(
            lambda: self._set_max_for_descriptions({"Close Shot", "Mid-Range Shot"})
        )
        button_row.addWidget(self.btn_max_offense)

        self.btn_max_defense = QPushButton("Max Defense")
        self.btn_max_defense.setObjectName("btn_max")
        self.btn_max_defense.clicked.connect(
            lambda: self._set_max_for_descriptions({"Interior Defense", "Perimeter Defense"})
        )
        button_row.addWidget(self.btn_max_defense)

        self.btn_max_all = QPushButton("Max Core")
        self.btn_max_all.setObjectName("btn_max")
        self.btn_max_all.clicked.connect(self._set_all_max)
        button_row.addWidget(self.btn_max_all)

        self.btn_god = QPushButton("God Mode")
        self.btn_god.setObjectName("btn_god")
        self.btn_god.setToolTip(
            "Max ratings, badges, tendencies, durability, and growth for the selected player."
        )
        self.btn_god.clicked.connect(self._apply_god_mode)
        button_row.addWidget(self.btn_god)

        self.btn_save_preset = QPushButton("Save Preset")
        self.btn_save_preset.clicked.connect(self._save_preset)
        button_row.addWidget(self.btn_save_preset)

        self.btn_apply_preset = QPushButton("Apply Preset...")
        self.btn_apply_preset.setObjectName("btn_apply")
        self.btn_apply_preset.clicked.connect(self._apply_preset)
        button_row.addWidget(self.btn_apply_preset)

        button_row.addStretch()
        layout.addLayout(button_row)

        experimental_group = QGroupBox("Experimental Live Tools")
        experimental_layout = QHBoxLayout(experimental_group)
        experimental_layout.setSpacing(10)

        self.btn_perfect_shot = QPushButton("Live Shot Lab (Exp)")
        self.btn_perfect_shot.setObjectName("btn_max")
        self.btn_perfect_shot.setCheckable(True)
        self.btn_perfect_shot.setToolTip(
            "Targets the current MyGM team during an active game.\n"
            "It prefers the current team filter, then falls back to the selected player.\n"
            "It zeroes the live AI timing error buffer and boosts only the in-match copies for your team.\n"
            "It does not modify the roster table or permanent player attributes.\n"
            "Experimental: use it like a live match lab, not a core roster-editing feature."
        )
        self.btn_perfect_shot.clicked.connect(self._toggle_perfect_shot_beta)
        experimental_layout.addWidget(self.btn_perfect_shot)

        experimental_note = QLabel(
            "Live Shot Lab keeps temporary in-match tuning separate from permanent roster edits. "
            "The main editor flow now focuses on stable player, team, and preset workflows."
        )
        experimental_note.setWordWrap(True)
        experimental_note.setStyleSheet("color: #b8b8b8;")
        experimental_layout.addWidget(experimental_note, 1)
        layout.addWidget(experimental_group)

    def _create_category_tab(self, category: str, attrs: List[AttributeDef]) -> QWidget:
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

    def load_player(self, player: Player) -> None:
        self.current_player = player
        info_parts = [player.full_name]
        if player.team_name:
            info_parts.append(player.team_name)
        info_parts.append(f"OVR {player.overall}")
        if player.age > 0:
            info_parts.append(f"Age {player.age} (Birth Year {player.birth_year})")
        self.player_info.setText("  |  ".join(info_parts))

        if self.player_mgr is None:
            return

        values = self.player_mgr.read_all_attributes(player)
        for attr_name, row in self._attr_rows.items():
            value = values.get(attr_name)
            if value is not None:
                row.set_value(value, is_original=True)

    def _collect_modified_values(self) -> Dict[str, Any]:
        modified: Dict[str, Any] = {}
        for attr_name, row in self._attr_rows.items():
            if row.is_modified():
                modified[attr_name] = row.get_value()
        return modified

    def _on_apply(self) -> None:
        if self.current_player is None or self.player_mgr is None:
            QMessageBox.warning(self, "Apply Changes", "Select a player after connecting to the game first.")
            return

        modified = self._collect_modified_values()
        if not modified:
            QMessageBox.information(self, "Apply Changes", "No staged edits were found.")
            return

        results = self.player_mgr.write_all_attributes(self.current_player, modified)
        success = sum(1 for ok in results.values() if ok)
        failed = sum(1 for ok in results.values() if not ok)

        if failed > 0:
            QMessageBox.warning(
                self,
                "Apply Changes",
                f"Updated {success} attributes, but {failed} writes failed.",
            )
        else:
            QMessageBox.information(self, "Apply Changes", f"Updated {success} attributes.")

        self.load_player(self.current_player)

    def _on_reset(self) -> None:
        for row in self._attr_rows.values():
            row.reset()

    def _categories_with_descriptions(self, samples: set[str]) -> List[str]:
        lowered = {sample.strip().lower() for sample in samples}
        categories: List[str] = []
        for category, attrs in self.config.attributes.items():
            descriptions = {(attr.description or attr.name).strip().lower() for attr in attrs}
            if lowered & descriptions:
                categories.append(category)
        return categories

    def _set_max_for_descriptions(self, samples: set[str]) -> None:
        for category in self._categories_with_descriptions(samples):
            for attr in self.config.attributes[category]:
                if attr.type in ("wstring", "ascii"):
                    continue
                self._attr_rows[attr.name].set_value(attr.max_val)

    def _set_all_max(self) -> None:
        self._set_max_for_descriptions({"Close Shot", "Interior Defense", "Speed", "Shot IQ"})
        self._set_max_for_descriptions({"Aerial Wizard", "Deadeye", "Bailout"})

    def _apply_god_mode(self) -> None:
        if self.current_player is None or self.player_mgr is None:
            QMessageBox.warning(self, "God Mode", "Select a player after connecting to the game first.")
            return

        reply = QMessageBox.question(
            self,
            "God Mode",
            "\n".join(
                [
                    f"Apply full God Mode to {self.current_player.full_name}?",
                    "",
                    "This will max ratings, badges, tendencies, durability, and growth values.",
                ]
            ),
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        count = self.player_mgr.apply_god_mode(self.current_player)
        summary = self.player_mgr.summarize_live_gameplay_state(self.current_player)
        compact_count = int(summary.get("match_compact_entries", 0) or 0)
        compact_bases = summary.get("match_compact_bases", [])
        attr_summary = summary.get("attributes", {})

        lines = [f"Updated {count} attributes for {self.current_player.full_name}."]
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
        self.load_player(self.current_player)

    def _save_preset(self) -> None:
        modified = self._collect_modified_values()
        if not modified:
            QMessageBox.information(
                self,
                "Save Preset",
                "Make some edits first. Presets are exported from the modified attributes only.",
            )
            return

        default_name = "Custom Preset"
        if self.current_player is not None and self.current_player.full_name:
            default_name = f"{self.current_player.full_name} Build"

        preset_name, accepted = QInputDialog.getText(
            self,
            "Save Preset",
            "Preset name:",
            text=default_name,
        )
        if not accepted:
            return

        preset_name = preset_name.strip()
        if not preset_name:
            QMessageBox.warning(self, "Save Preset", "Preset name cannot be empty.")
            return

        suggested_filename = "".join(char if char.isalnum() else "_" for char in preset_name).strip("_")
        if not suggested_filename:
            suggested_filename = "custom_preset"

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Preset",
            os.path.join(os.getcwd(), f"{suggested_filename}.json"),
            "JSON Files (*.json)",
        )
        if not filepath:
            return

        description = "Preset exported from modified attributes only."
        if self.current_player is not None:
            description = f"Preset exported from modified attributes for {self.current_player.full_name}."

        try:
            export_custom_preset(
                filepath,
                preset_name,
                self.config,
                modified,
                description=description,
            )
        except Exception as exc:
            QMessageBox.warning(self, "Save Preset", f"Failed to save preset:\n{exc}")
            return

        QMessageBox.information(
            self,
            "Save Preset",
            f"Saved preset '{preset_name}' with {len(modified)} attributes.",
        )

    def _apply_preset(self) -> None:
        if self.current_player is None or self.player_mgr is None:
            QMessageBox.warning(self, "Apply Preset", "Select a player and connect the game first.")
            return

        modified = self._collect_modified_values()
        if modified:
            reply = QMessageBox.question(
                self,
                "Apply Preset",
                "You have unsaved edits in the current player panel.\n\n"
                "Applying a preset will overwrite those staged values. Continue?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        dialog = PresetChooserDialog(self.config, self)
        if dialog.exec_() != dialog.Accepted:
            return

        preset = dialog.selected_preset()
        if preset is None:
            return

        values, unresolved = resolve_preset_values(self.config, preset.values_by_description)
        if not values:
            QMessageBox.warning(
                self,
                "Apply Preset",
                "The selected preset did not map to any writable attributes for the current offsets.",
            )
            return

        results = self.player_mgr.write_all_attributes(self.current_player, values)
        success = sum(1 for ok in results.values() if ok)
        failed = sum(1 for ok in results.values() if not ok)

        lines = [
            f"Applied preset: {preset.name}",
            f"Successful writes: {success}",
            f"Failed writes: {failed}",
        ]
        if unresolved:
            lines.append(f"Skipped missing mappings: {len(unresolved)}")

        QMessageBox.information(self, "Apply Preset", "\n".join(lines))
        self.load_player(self.current_player)

    def _set_perfect_shot_button_state(self, active: bool) -> None:
        self.btn_perfect_shot.blockSignals(True)
        self.btn_perfect_shot.setChecked(active)
        self.btn_perfect_shot.setText("Stop Live Shot Lab" if active else "Live Shot Lab (Exp)")
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
            QMessageBox.warning(self, "Live Shot Lab", "Connect the game first.")
            return

        if not checked:
            self._stop_perfect_shot_timers()
            self.player_mgr.stop_perfect_shot_beta()
            self._set_perfect_shot_button_state(False)
            return

        target = self._resolve_perfect_shot_target()
        if target is None:
            self._set_perfect_shot_button_state(False)
            QMessageBox.warning(self, "Live Shot Lab", "Select a player or filter your MyGM team first.")
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
                "Live Shot Lab",
                str(summary.get("error") or "No live in-match shot entry was found."),
            )
            return

        self._perfect_shot_sustain_timer.start()
        self._perfect_shot_refresh_timer.start()
        self._set_perfect_shot_button_state(True)
        target_source = str(target.get("source") or "auto")

        lines = [
            "Live Shot Lab is now running for your MyGM team.",
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
            "All temporary live-shot boosts are restored when you stop the toggle.",
        ]
        QMessageBox.information(self, "Live Shot Lab Enabled", "\n".join(lines))

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
                QMessageBox.information(self, "Live Shot Lab Stopped", str(reason))

    def set_player_manager(self, mgr: Optional[PlayerManager]) -> None:
        if mgr is None:
            self._stop_perfect_shot_timers()
            self._set_perfect_shot_button_state(False)
            if self.player_mgr is not None:
                self.player_mgr.stop_perfect_shot_beta(restore_live_memory=False)
        self.player_mgr = mgr
