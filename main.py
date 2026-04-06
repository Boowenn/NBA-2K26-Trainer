"""NBA 2K26 Trainer - 球员属性修改器 入口"""

import sys
import ctypes

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt


def check_admin():
    """检查是否以管理员权限运行"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def request_admin():
    """请求管理员权限重启"""
    import os
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), os.getcwd(), 1
    )


def main():
    # 检查管理员权限
    if not check_admin():
        reply = QApplication(sys.argv)  # 临时 app 用于弹窗
        result = QMessageBox.question(
            None, "需要管理员权限",
            "修改游戏内存需要管理员权限运行。\n是否以管理员权限重新启动？",
            QMessageBox.Yes | QMessageBox.No
        )
        if result == QMessageBox.Yes:
            request_admin()
        sys.exit(0)

    # 启用高DPI支持
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("NBA 2K26 Trainer")
    app.setOrganizationName("NBA2K26Trainer")

    from nba2k26_trainer.ui.main_window import MainWindow
    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
