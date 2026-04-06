"""NBA 2K26 Trainer - 球员属性修改器 入口"""

import sys
import os
import ctypes

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt


def is_admin() -> bool:
    """检查是否以管理员权限运行"""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin():
    """以管理员权限重新启动自己"""
    # 对 PyInstaller 打包的 exe，sys.executable 就是 exe 本身
    if getattr(sys, 'frozen', False):
        exe = sys.executable
        args = " ".join(f'"{a}"' for a in sys.argv[1:])
    else:
        exe = sys.executable
        args = " ".join(f'"{a}"' for a in sys.argv)
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", exe, args, os.getcwd(), 1
    )


def main():
    # 启用高DPI支持（必须在 QApplication 创建之前）
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # 只创建一个 QApplication，全程使用
    app = QApplication(sys.argv)
    app.setApplicationName("NBA 2K26 Trainer")
    app.setOrganizationName("NBA2K26Trainer")

    # 检查管理员权限
    if not is_admin():
        result = QMessageBox.question(
            None, "需要管理员权限",
            "修改游戏内存需要管理员权限运行。\n\n"
            "点击「Yes」将以管理员权限重新启动。\n"
            "点击「No」继续运行（可能无法连接游戏）。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if result == QMessageBox.Yes:
            relaunch_as_admin()
            sys.exit(0)
        # 用户选 No，继续运行但可能连接失败

    from nba2k26_trainer.ui.main_window import MainWindow
    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
