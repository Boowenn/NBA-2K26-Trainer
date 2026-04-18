"""Desktop entry point for NBA 2K26 Trainer."""

from __future__ import annotations

import ctypes
import os
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QMessageBox

from nba2k26_trainer.resources import app_icon_path


_single_instance_mutex = None


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin() -> None:
    if getattr(sys, "frozen", False):
        executable = sys.executable
        arguments = " ".join(f'"{item}"' for item in sys.argv[1:])
    else:
        executable = sys.executable
        arguments = " ".join(f'"{item}"' for item in sys.argv)
    ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, arguments, os.getcwd(), 1)


def acquire_single_instance_mutex() -> bool:
    global _single_instance_mutex

    kernel32 = ctypes.windll.kernel32
    _single_instance_mutex = kernel32.CreateMutexW(
        None,
        False,
        "Global\\NBA2K26Trainer.SingleInstance",
    )
    if not _single_instance_mutex:
        return True

    error_already_exists = 183
    return kernel32.GetLastError() != error_already_exists


def main() -> None:
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("NBA 2K26 Trainer")
    app.setOrganizationName("NBA2K26Trainer")

    icon_path = app_icon_path()
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    if not is_admin():
        result = QMessageBox.question(
            None,
            "需要管理员权限",
            "修改器建议以管理员权限启动，这样内存读写会更稳定。\n\n"
            "点击“是”将以管理员身份重新启动。\n"
            "点击“否”则继续以当前权限运行。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if result == QMessageBox.Yes:
            relaunch_as_admin()
            sys.exit(0)

    if not acquire_single_instance_mutex():
        QMessageBox.warning(
            None,
            "NBA 2K26 Trainer",
            "已有一个修改器实例在运行。\n\n"
            "请先关闭另一个窗口，避免同时写入内存导致冲突。",
        )
        sys.exit(0)

    from nba2k26_trainer.ui.main_window import MainWindow

    window = MainWindow()
    if os.path.exists(icon_path):
        window.setWindowIcon(QIcon(icon_path))
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
