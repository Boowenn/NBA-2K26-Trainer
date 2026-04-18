"""Shared UI theme for the desktop trainer."""

DARK_STYLE = """
QMainWindow {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 #0b1017,
        stop: 0.55 #111926,
        stop: 1 #182130
    );
}

QWidget {
    background-color: transparent;
    color: #eef3f8;
    font-family: "Microsoft YaHei UI", "Segoe UI";
    font-size: 13px;
}

QFrame#heroCard {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 #121b26,
        stop: 0.5 #172332,
        stop: 1 #1d2b3d
    );
    border: 1px solid #30445d;
    border-radius: 22px;
}

QFrame#metricCard,
QFrame#actionCard,
QFrame#workspaceCard {
    background-color: rgba(18, 27, 38, 0.88);
    border: 1px solid #27384d;
    border-radius: 18px;
}

QLabel {
    color: #eef3f8;
    padding: 1px;
}

QLabel#title {
    font-size: 30px;
    font-weight: 700;
    color: #f7fbff;
}

QLabel#subtitle {
    font-size: 14px;
    color: #9fb3cb;
}

QLabel#heroBadge {
    color: #081018;
    background-color: #ff9f1c;
    border-radius: 10px;
    padding: 4px 10px;
    font-weight: 700;
}

QLabel#metricLabel,
QLabel#sectionLabel {
    color: #8ea5bf;
    font-size: 12px;
    font-weight: 600;
}

QLabel#metricValue {
    color: #f7fbff;
    font-size: 22px;
    font-weight: 700;
}

QLabel#subtleText {
    color: #95a8be;
}

QPushButton {
    background-color: #162435;
    color: #eef3f8;
    border: 1px solid #30445d;
    border-radius: 12px;
    padding: 9px 16px;
    font-size: 13px;
    min-height: 22px;
}

QPushButton:hover {
    background-color: #203349;
    border-color: #ff9f1c;
}

QPushButton:pressed {
    background-color: #ff9f1c;
    border-color: #ffb74d;
    color: #081018;
}

QPushButton#btn_apply {
    background-color: #146c5e;
    border-color: #1d8f7d;
    font-weight: 700;
}

QPushButton#btn_apply:hover {
    background-color: #19816f;
}

QPushButton#btn_max {
    background-color: #6f2d28;
    border-color: #9a463f;
    font-weight: 700;
}

QPushButton#btn_max:hover {
    background-color: #85413a;
}

QPushButton#btn_god {
    background-color: #b85c15;
    border-color: #d8792a;
    font-weight: 700;
    font-size: 14px;
    color: #ffffff;
    padding: 9px 18px;
}

QPushButton#btn_god:hover {
    background-color: #d8792a;
    color: #081018;
}

QPushButton#btn_refresh {
    background-color: #1f4f8e;
    border-color: #2e6cc0;
    font-weight: 700;
}

QPushButton#btn_refresh:hover {
    background-color: #2763b2;
}

QLineEdit,
QComboBox,
QSpinBox,
QDoubleSpinBox,
QPlainTextEdit {
    background-color: #111a24;
    color: #eef3f8;
    border: 1px solid #2b3f55;
    border-radius: 10px;
    padding: 7px 10px;
}

QLineEdit:focus,
QComboBox:focus,
QSpinBox:focus,
QDoubleSpinBox:focus,
QPlainTextEdit:focus {
    border-color: #ff9f1c;
}

QComboBox::drop-down {
    border: none;
    width: 22px;
}

QComboBox QAbstractItemView {
    background-color: #111a24;
    color: #eef3f8;
    selection-background-color: #203349;
    border: 1px solid #2b3f55;
}

QTableWidget {
    background-color: #101822;
    alternate-background-color: #14202c;
    color: #eef3f8;
    gridline-color: #213040;
    border: 1px solid #27384d;
    border-radius: 14px;
    selection-background-color: #ff9f1c;
    selection-color: #081018;
}

QTableWidget::item {
    padding: 5px 8px;
}

QHeaderView::section {
    background-color: #1b2a3b;
    color: #ffcf87;
    padding: 7px 8px;
    border: none;
    border-right: 1px solid #243447;
    font-weight: 700;
}

QTabWidget::pane {
    background-color: rgba(18, 27, 38, 0.88);
    border: 1px solid #27384d;
    border-radius: 14px;
}

QTabBar::tab {
    background-color: #111926;
    color: #dbe6f1;
    padding: 9px 16px;
    border: 1px solid #27384d;
    border-bottom: none;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    margin-right: 3px;
}

QTabBar::tab:selected {
    background-color: #1b2a3b;
    color: #ffcf87;
    font-weight: 700;
}

QTabBar::tab:hover {
    background-color: #172433;
}

QSpinBox::up-button,
QSpinBox::down-button,
QDoubleSpinBox::up-button,
QDoubleSpinBox::down-button {
    background-color: #1b2a3b;
    border: none;
    width: 18px;
}

QSpinBox::up-button:hover,
QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover,
QDoubleSpinBox::down-button:hover {
    background-color: #ff9f1c;
}

QSlider::groove:horizontal {
    background: #1c2b3a;
    height: 6px;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #ff9f1c;
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}

QSlider::sub-page:horizontal {
    background: #ff9f1c;
    border-radius: 3px;
}

QScrollBar:vertical {
    background-color: transparent;
    width: 10px;
    border: none;
}

QScrollBar::handle:vertical {
    background-color: #30445d;
    border-radius: 5px;
    min-height: 26px;
}

QScrollBar::handle:vertical:hover {
    background-color: #ff9f1c;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}

QStatusBar {
    background-color: rgba(14, 22, 31, 0.96);
    color: #dce7f2;
    border-top: 1px solid #27384d;
    font-size: 12px;
}

QGroupBox {
    background-color: rgba(18, 27, 38, 0.88);
    border: 1px solid #27384d;
    border-radius: 14px;
    margin-top: 14px;
    padding-top: 18px;
    font-weight: 700;
    color: #ffcf87;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    left: 12px;
}

QProgressBar {
    background-color: #111a24;
    border: 1px solid #27384d;
    border-radius: 10px;
    text-align: center;
    color: #eef3f8;
    min-height: 18px;
}

QProgressBar::chunk {
    background-color: #ff9f1c;
    border-radius: 8px;
}

QSplitter::handle {
    background-color: #243447;
}

QToolTip {
    background-color: #101822;
    color: #eef3f8;
    border: 1px solid #ff9f1c;
    padding: 5px 7px;
}

QMessageBox {
    background-color: #111926;
}
"""
