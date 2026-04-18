"""Reusable preset pack picker dialog."""

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
    QPlainTextEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.offsets import OffsetConfig
from ..preset_packs import (
    PresetPackDefinition,
    builtin_preset_packs,
    format_preset_pack_preview,
    load_preset_pack,
    save_preset_pack,
)


class PresetPackChooserDialog(QDialog):
    """Pick a built-in preset pack or import one from a JSON file."""

    def __init__(self, config: OffsetConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._builtin_packs = builtin_preset_packs()
        self._custom_pack: Optional[PresetPackDefinition] = None
        self._custom_path: Optional[str] = None
        self.setWindowTitle("Choose Preset Pack")
        self.setMinimumSize(620, 420)
        self._setup_ui()
        self._refresh_builtin_preview()
        self._refresh_custom_preview()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        intro = QLabel(
            "Preset packs apply multiple role templates across the current scope using Prospect Lab heuristics. "
            "They are the recommended way to batch-shape a rebuild, draft class, or rotation identity."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_builtin_tab(), "Built-in")
        self.tabs.addTab(self._create_custom_tab(), "Pack File")
        layout.addWidget(self.tabs, 1)

        button_row = QHBoxLayout()

        btn_export = QPushButton("Save Selected Pack...")
        btn_export.clicked.connect(self._export_selected_pack)
        button_row.addWidget(btn_export)

        button_row.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        button_row.addWidget(btn_cancel)

        btn_ok = QPushButton("Use Pack")
        btn_ok.setObjectName("btn_apply")
        btn_ok.clicked.connect(self._accept_if_valid)
        button_row.addWidget(btn_ok)

        layout.addLayout(button_row)

    def _create_builtin_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)

        self.builtin_combo = QComboBox()
        for pack in self._builtin_packs:
            self.builtin_combo.addItem(pack.name, pack.pack_id)
        self.builtin_combo.currentIndexChanged.connect(self._refresh_builtin_preview)
        layout.addWidget(self.builtin_combo)

        self.builtin_preview = QPlainTextEdit()
        self.builtin_preview.setReadOnly(True)
        layout.addWidget(self.builtin_preview, 1)
        return widget

    def _create_custom_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)

        button_row = QHBoxLayout()

        btn_browse = QPushButton("Load Pack File...")
        btn_browse.clicked.connect(self._browse_custom_pack)
        button_row.addWidget(btn_browse)

        btn_clear = QPushButton("Clear File")
        btn_clear.clicked.connect(self._clear_custom_pack)
        button_row.addWidget(btn_clear)

        button_row.addStretch()
        layout.addLayout(button_row)

        self.custom_path_label = QLabel("No preset pack file selected.")
        self.custom_path_label.setWordWrap(True)
        layout.addWidget(self.custom_path_label)

        self.custom_preview = QPlainTextEdit()
        self.custom_preview.setReadOnly(True)
        layout.addWidget(self.custom_preview, 1)
        return widget

    def _refresh_builtin_preview(self) -> None:
        if not self._builtin_packs:
            self.builtin_preview.setPlainText("No built-in preset packs are available.")
            return
        pack = self._builtin_packs[self.builtin_combo.currentIndex()]
        self.builtin_preview.setPlainText(format_preset_pack_preview(self.config, pack))

    def _refresh_custom_preview(self) -> None:
        if self._custom_pack is None:
            self.custom_path_label.setText("No preset pack file selected.")
            self.custom_preview.setPlainText(
                "Load a JSON preset pack here to preview its rules and use it in Batch Edit."
            )
            return

        path_label = self._custom_path or "Custom pack"
        self.custom_path_label.setText(os.path.basename(path_label))
        self.custom_preview.setPlainText(format_preset_pack_preview(self.config, self._custom_pack))

    def _browse_custom_pack(self) -> None:
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Open Preset Pack",
            "",
            "JSON Files (*.json)",
        )
        if not filepath:
            return

        try:
            self._custom_pack = load_preset_pack(filepath)
            self._custom_path = filepath
        except Exception as exc:
            QMessageBox.warning(self, "Preset Pack", f"Failed to load preset pack:\n{exc}")
            return

        self._refresh_custom_preview()

    def _clear_custom_pack(self) -> None:
        self._custom_pack = None
        self._custom_path = None
        self._refresh_custom_preview()

    def _export_selected_pack(self) -> None:
        pack = self.selected_pack()
        if pack is None:
            QMessageBox.warning(
                self,
                "Preset Pack",
                "Load a preset pack file or switch to a built-in pack before exporting.",
            )
            return

        suggested = f"{pack.pack_id or 'preset_pack'}.json"
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Preset Pack",
            suggested,
            "JSON Files (*.json)",
        )
        if not filepath:
            return

        if not os.path.splitext(filepath)[1]:
            filepath = f"{filepath}.json"

        try:
            save_preset_pack(filepath, pack)
        except Exception as exc:
            QMessageBox.warning(self, "Preset Pack", f"Failed to save preset pack:\n{exc}")
            return

        QMessageBox.information(self, "Preset Pack", f"Saved preset pack to:\n{filepath}")

    def _accept_if_valid(self) -> None:
        if self.selected_pack() is None:
            QMessageBox.warning(self, "Choose Preset Pack", "Load a preset pack file or switch to a built-in pack.")
            return
        self.accept()

    def selected_pack(self) -> Optional[PresetPackDefinition]:
        if self.tabs.currentIndex() == 1:
            return self._custom_pack
        if not self._builtin_packs:
            return None
        return self._builtin_packs[self.builtin_combo.currentIndex()]
