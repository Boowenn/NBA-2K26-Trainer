"""Reusable preset picker dialog."""

from __future__ import annotations

import os
from typing import Optional

from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.offsets import OffsetConfig
from ..presets import (
    PresetDefinition,
    builtin_presets,
    load_custom_preset,
    resolve_preset_values,
    summarize_preset_values,
)


class PresetChooserDialog(QDialog):
    """Pick a built-in preset or import one from a JSON file."""

    def __init__(self, config: OffsetConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._builtin_presets = builtin_presets()
        self._custom_preset: Optional[PresetDefinition] = None
        self._custom_path: Optional[str] = None
        self.setWindowTitle("Choose Preset")
        self.setMinimumWidth(520)
        self._setup_ui()
        self._refresh_builtin_preview()
        self._refresh_custom_preview()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        intro = QLabel(
            "Built-in presets cover the most common role edits. "
            "You can also import a JSON preset exported from the trainer."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_builtin_tab(), "Built-in")
        self.tabs.addTab(self._create_custom_tab(), "Preset File")
        layout.addWidget(self.tabs)

        buttons = QHBoxLayout()
        buttons.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_cancel)

        btn_ok = QPushButton("Use Preset")
        btn_ok.setObjectName("btn_apply")
        btn_ok.clicked.connect(self._accept_if_valid)
        buttons.addWidget(btn_ok)

        layout.addLayout(buttons)

    def _create_builtin_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)

        self.builtin_combo = QComboBox()
        for preset in self._builtin_presets:
            self.builtin_combo.addItem(preset.name, preset.preset_id)
        self.builtin_combo.currentIndexChanged.connect(self._refresh_builtin_preview)
        layout.addWidget(self.builtin_combo)

        self.builtin_preview = QLabel("")
        self.builtin_preview.setWordWrap(True)
        self.builtin_preview.setStyleSheet("color: #d8d8d8;")
        layout.addWidget(self.builtin_preview)

        return widget

    def _create_custom_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)

        button_row = QHBoxLayout()

        btn_browse = QPushButton("Load Preset File...")
        btn_browse.clicked.connect(self._browse_custom_preset)
        button_row.addWidget(btn_browse)

        btn_clear = QPushButton("Clear File")
        btn_clear.clicked.connect(self._clear_custom_preset)
        button_row.addWidget(btn_clear)

        button_row.addStretch()
        layout.addLayout(button_row)

        self.custom_path_label = QLabel("No preset file selected.")
        self.custom_path_label.setWordWrap(True)
        layout.addWidget(self.custom_path_label)

        self.custom_preview = QLabel("")
        self.custom_preview.setWordWrap(True)
        self.custom_preview.setStyleSheet("color: #d8d8d8;")
        layout.addWidget(self.custom_preview)

        return widget

    def _refresh_builtin_preview(self) -> None:
        preset = self._builtin_presets[self.builtin_combo.currentIndex()]
        resolved, unresolved = resolve_preset_values(self.config, preset.values_by_description)
        lines = [
            preset.description,
            f"Mapped attributes: {len(resolved)}",
            f"Preview: {summarize_preset_values(resolved.keys())}",
        ]
        if unresolved:
            lines.append(f"Unresolved entries: {len(unresolved)}")
        self.builtin_preview.setText("\n".join(lines))

    def _refresh_custom_preview(self) -> None:
        if self._custom_preset is None:
            self.custom_preview.setText("Export a preset from the editor or load an existing JSON file here.")
            self.custom_path_label.setText("No preset file selected.")
            return

        resolved, unresolved = resolve_preset_values(self.config, self._custom_preset.values_by_description)
        path_label = self._custom_path or "Custom preset"
        self.custom_path_label.setText(os.path.basename(path_label))
        lines = [
            self._custom_preset.name,
            self._custom_preset.description,
            f"Mapped attributes: {len(resolved)}",
            f"Preview: {summarize_preset_values(resolved.keys())}",
        ]
        if unresolved:
            lines.append(f"Unresolved entries: {len(unresolved)}")
        self.custom_preview.setText("\n".join(line for line in lines if line))

    def _browse_custom_preset(self) -> None:
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Open Preset File",
            "",
            "JSON Files (*.json)",
        )
        if not filepath:
            return

        try:
            self._custom_preset = load_custom_preset(filepath)
            self._custom_path = filepath
        except Exception as exc:
            QMessageBox.warning(self, "Preset File", f"Failed to load preset file:\n{exc}")
            return

        self._refresh_custom_preview()

    def _clear_custom_preset(self) -> None:
        self._custom_preset = None
        self._custom_path = None
        self._refresh_custom_preview()

    def _accept_if_valid(self) -> None:
        if self.selected_preset() is None:
            QMessageBox.warning(self, "Choose Preset", "Load a preset file or switch back to a built-in preset.")
            return
        self.accept()

    def selected_preset(self) -> Optional[PresetDefinition]:
        if self.tabs.currentIndex() == 1:
            return self._custom_preset
        return self._builtin_presets[self.builtin_combo.currentIndex()]
