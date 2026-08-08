"""系统托盘图标。可用性由 app 用 isSystemTrayAvailable() 守卫，不可用则忽略（桌宠右键菜单兜底退出）。
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon
from PySide6.QtCore import QObject, Signal


class TrayIcon(QObject):
    settings_requested = Signal()
    exit_requested = Signal()

    def __init__(self, icon: QIcon, tooltip: str = "小猪桌宠", parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._tray = QSystemTrayIcon(icon, self)
        self._tray.setToolTip(tooltip)

        menu = QMenu()
        menu.addAction("打开设置").triggered.connect(self.settings_requested.emit)
        menu.addSeparator()
        menu.addAction("退出").triggered.connect(self.exit_requested.emit)
        self._tray.setContextMenu(menu)

    def show(self) -> None:
        self._tray.show()

    def hide(self) -> None:
        self._tray.hide()

    @staticmethod
    def is_available() -> bool:
        return QSystemTrayIcon.isSystemTrayAvailable()
