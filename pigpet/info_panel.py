"""InfoPanel：随桌宠移动的简约信息面板。

- 无边框 + 半透明圆角背景，不抢焦点、不占任务栏；
- 一行一个指标：app 通过 set_metrics 传入 (key, label) 列表；
- update_values(dict) 刷新数值，None → “不可用”；
- anchor_to(pos, size) 把面板贴在桌宠右侧竖直对齐；
- 与桌宠一样可整体置顶（P6 随设置同步）。
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

PANEL_GAP = 8          # 面板距桌宠右侧间距（px）
PANEL_BG = QColor(0, 0, 0, 150)
PANEL_CORNER = 8       # 圆角半径
LABEL_STYLE = "color: white; background: transparent; font: 12px 'Microsoft YaHei';"


class InfoPanel(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._rows: list[tuple[str, str, QLabel]] = []  # (key, label, widget)

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(10, 6, 10, 6)
        self._layout.setSpacing(2)

    def set_metrics(self, rows: list[tuple[str, str]]) -> None:
        """重建显示行。rows: [(key, label), ...]。"""
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._rows = []
        for key, label in rows:
            widget = QLabel(f"{label}: --")
            widget.setStyleSheet(LABEL_STYLE)
            self._layout.addWidget(widget)
            self._rows.append((key, label, widget))
        self.adjustSize()

    def update_values(self, values: dict) -> None:
        for key, label, widget in self._rows:
            value = values.get(key)
            text = "不可用" if value is None else str(value)
            widget.setText(f"{label}: {text}")
        # 数值文本可能比占位文本宽，重新自适应，避免裁剪
        self.adjustSize()

    def texts(self) -> list[str]:
        """当前各行的显示文本（供自检/调试）。"""
        return [w.text() for _k, _l, w in self._rows]

    def anchor_to(self, pos: QPoint, size: QSize) -> None:
        self.move(pos.x() + size.width() + PANEL_GAP, pos.y())

    def set_always_on_top(self, on: bool) -> None:
        was_visible = self.isVisible()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, on)
        if was_visible:
            self.hide()
        self.show()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt 命名)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(PANEL_BG)
        painter.drawRoundedRect(self.rect(), PANEL_CORNER, PANEL_CORNER)
