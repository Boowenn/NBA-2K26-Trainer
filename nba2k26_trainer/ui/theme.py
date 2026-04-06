"""UI 主题 - 暗色 NBA 风格"""

DARK_STYLE = """
QMainWindow {
    background-color: #1a1a2e;
}

QWidget {
    background-color: #1a1a2e;
    color: #e0e0e0;
    font-family: "Segoe UI", "Microsoft YaHei";
    font-size: 13px;
}

QLabel {
    color: #e0e0e0;
    padding: 2px;
}

QLabel#title {
    font-size: 20px;
    font-weight: bold;
    color: #f77f00;
    padding: 8px;
}

QLabel#status_connected {
    color: #00e676;
    font-weight: bold;
}

QLabel#status_disconnected {
    color: #ff5252;
    font-weight: bold;
}

QPushButton {
    background-color: #16213e;
    color: #e0e0e0;
    border: 1px solid #0f3460;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
    min-height: 20px;
}

QPushButton:hover {
    background-color: #0f3460;
    border-color: #f77f00;
}

QPushButton:pressed {
    background-color: #f77f00;
    color: #1a1a2e;
}

QPushButton#btn_apply {
    background-color: #00695c;
    border-color: #00897b;
    font-weight: bold;
}

QPushButton#btn_apply:hover {
    background-color: #00897b;
}

QPushButton#btn_max {
    background-color: #b71c1c;
    border-color: #d32f2f;
    font-weight: bold;
}

QPushButton#btn_max:hover {
    background-color: #d32f2f;
}

QPushButton#btn_refresh {
    background-color: #1565c0;
    border-color: #1976d2;
}

QPushButton#btn_refresh:hover {
    background-color: #1976d2;
}

QLineEdit {
    background-color: #16213e;
    color: #e0e0e0;
    border: 1px solid #0f3460;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 13px;
}

QLineEdit:focus {
    border-color: #f77f00;
}

QComboBox {
    background-color: #16213e;
    color: #e0e0e0;
    border: 1px solid #0f3460;
    border-radius: 4px;
    padding: 6px 10px;
    min-height: 20px;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #16213e;
    color: #e0e0e0;
    selection-background-color: #0f3460;
    border: 1px solid #0f3460;
}

QTableWidget {
    background-color: #16213e;
    alternate-background-color: #1a1a2e;
    color: #e0e0e0;
    gridline-color: #0f3460;
    border: 1px solid #0f3460;
    border-radius: 4px;
    selection-background-color: #f77f00;
    selection-color: #1a1a2e;
}

QTableWidget::item {
    padding: 4px 8px;
}

QHeaderView::section {
    background-color: #0f3460;
    color: #f77f00;
    padding: 6px 8px;
    border: none;
    border-right: 1px solid #16213e;
    font-weight: bold;
}

QTabWidget::pane {
    background-color: #16213e;
    border: 1px solid #0f3460;
    border-radius: 4px;
}

QTabBar::tab {
    background-color: #1a1a2e;
    color: #e0e0e0;
    padding: 8px 16px;
    border: 1px solid #0f3460;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #0f3460;
    color: #f77f00;
    font-weight: bold;
}

QTabBar::tab:hover {
    background-color: #16213e;
    color: #f77f00;
}

QSpinBox {
    background-color: #16213e;
    color: #e0e0e0;
    border: 1px solid #0f3460;
    border-radius: 4px;
    padding: 4px 8px;
    min-width: 70px;
}

QSpinBox:focus {
    border-color: #f77f00;
}

QSpinBox::up-button, QSpinBox::down-button {
    background-color: #0f3460;
    border: none;
    width: 20px;
}

QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #f77f00;
}

QSlider::groove:horizontal {
    background: #0f3460;
    height: 6px;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #f77f00;
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}

QSlider::sub-page:horizontal {
    background: #f77f00;
    border-radius: 3px;
}

QScrollBar:vertical {
    background-color: #1a1a2e;
    width: 10px;
    border: none;
}

QScrollBar::handle:vertical {
    background-color: #0f3460;
    border-radius: 5px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #f77f00;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QStatusBar {
    background-color: #0f3460;
    color: #e0e0e0;
    font-size: 12px;
}

QGroupBox {
    border: 1px solid #0f3460;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: bold;
    color: #f77f00;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
}

QToolTip {
    background-color: #16213e;
    color: #e0e0e0;
    border: 1px solid #f77f00;
    padding: 4px;
}

QMessageBox {
    background-color: #1a1a2e;
}
"""
