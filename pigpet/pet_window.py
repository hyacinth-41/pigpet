"""桌宠窗口：唯一“知道自己是窗口”的类，只负责视图。

- 无边框 + 透明 + 置顶 + 不抢焦点；
- 绘制 AnimationPlayer 当前帧（frame_changed → update 由 app.py 接线）；
- 鼠标事件转发（P3 交给 InteractionController）；右键菜单（P3）；
- pos_changed 通知面板跟随（P5 使用）。

注意：整窗透明，P2 阶段点击整窗都算“点击角色”；P3 用热点区过滤。
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPainter
from PySide6.QtWidgets import QMenu, QWidget

from .interaction import InteractionController
from .player import AnimationPlayer

EDGE_MARGIN = 48  # 默认位置距屏幕边缘留白（px）
DRAG_DARKEN = 70  # DRAG 状态下的变暗叠加透明度（0-255）


class PetWindow(QWidget):
    pos_changed = Signal(QPoint)      # 窗口位置变化（P5 面板跟随用）
    settings_requested = Signal()     # 右键菜单“打开设置”
    exit_requested = Signal()         # 右键菜单“退出”

    def __init__(self, player: AnimationPlayer, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._player = player
        self._hotspot: Optional[QRect] = None
        self._interaction: Optional[InteractionController] = None
        self._state = "IDLE"  # 由 app.py 通过 set_state 跟随 FSM
        self._scale = 1.0     # 显示缩放（见 set_scale）
        self._build_context_menu()

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)  # PNG 透明
        self.setAttribute(Qt.WA_NoSystemBackground)     # 防黑闪
        self.setAttribute(Qt.WA_ShowWithoutActivating)  # 不抢焦点

    # ---------- 视图 ----------

    def set_state(self, state: str) -> None:
        """跟随 FSM 状态，用于 DRAG 视觉指示（P4）。"""
        self._state = state
        self.update()

    @property
    def current_state(self) -> str:
        return self._state

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt 命名)
        painter = QPainter(self)
        pix = self._player.current_pixmap()
        if not pix.isNull():
            # 按窗口尺寸绘制；窗口尺寸 == 素材尺寸时 1:1，素材换大小时等比缩放
            painter.drawPixmap(0, 0, self.width(), self.height(), pix)
        if self._state == "DRAG":
            # 被拎起视觉指示（占位；换正式 drag 素材后此叠加自然消失）
            painter.fillRect(self.rect(), QColor(0, 0, 0, DRAG_DARKEN))

    def set_hotspot(self, rect: Optional[QRect]) -> None:
        """只让角色身体区域响应鼠标。None 表示整窗响应。"""
        self._hotspot = rect

    def set_interaction(self, interaction: InteractionController) -> None:
        self._interaction = interaction

    # ---------- 右键菜单 ----------

    def _build_context_menu(self) -> None:
        self._menu = QMenu(self)
        self._menu.addAction("打开设置").triggered.connect(self.settings_requested.emit)
        self._menu.addSeparator()
        self._menu.addAction("退出").triggered.connect(self.exit_requested.emit)

    def contextMenuEvent(self, event) -> None:  # noqa: N802 (Qt 命名)
        self._menu.exec(event.globalPos())

    # ---------- 鼠标转发（热点区过滤后交给 InteractionController） ----------

    def _accept_mouse(self, local_pos: QPoint) -> bool:
        if self._hotspot is None:
            return True
        return self._hotspot.contains(local_pos)

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt 命名)
        if event.button() == Qt.LeftButton and self._interaction is not None:
            if self._accept_mouse(event.position().toPoint()):
                self._interaction.on_mouse_press(
                    event.globalPosition().toPoint(), event.position().toPoint()
                )
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 (Qt 命名)
        if self._interaction is not None:
            self._interaction.on_mouse_move(event.globalPosition().toPoint())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt 命名)
        if event.button() == Qt.LeftButton and self._interaction is not None:
            self._interaction.on_mouse_release(event.globalPosition().toPoint())
        super().mouseReleaseEvent(event)

    def set_scale(self, scale: float) -> None:
        """按素材尺寸 × 缩放 重新定窗口尺寸。paintEvent 已把素材等比缩放到窗口。"""
        self._scale = scale
        self._resize_to_asset()

    def _resize_to_asset(self) -> None:
        base = self._player.current_pixmap().size()
        self.setFixedSize(
            QSize(int(base.width() * self._scale), int(base.height() * self._scale))
        )
        # 面板锚定依赖窗口尺寸，尺寸变化后通知一次
        self.pos_changed.emit(self.pos())

    def show_at_default_position(self) -> None:
        """主屏右下角，留边距。"""
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.show()
            return
        geo = screen.availableGeometry()
        x = geo.right() - self.width() - EDGE_MARGIN
        y = geo.bottom() - self.height() - EDGE_MARGIN
        self.move(x, y)
        self.show()

    # ---------- 层级/位置 ----------

    def set_always_on_top(self, on: bool) -> None:
        """切换置顶。setWindowFlag 后用 show() 应用；必要时 hide+show 回退。"""
        was_visible = self.isVisible()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, on)
        if was_visible:
            self.hide()
        self.show()

    def moveEvent(self, event) -> None:  # noqa: N802 (Qt 命名)
        super().moveEvent(event)
        self.pos_changed.emit(self.pos())
