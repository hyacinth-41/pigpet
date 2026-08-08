"""InteractionController：点击/拖动交互控制器（UI 无关）。

只发出「状态请求」与「期望窗口位置」信号，不碰 QWidget。偏移数学是
“不跳动、贴手”的保证：

- press 时捕获一次抓取点 grab_point（窗口内本地坐标），全程不变；
  目标始终是：窗口左上角 = 当前光标 − grab_point，即抓取点在光标正下方；
- 移动超过阈值(≈8px)判定为拖动 → 请求 DRAG，启动 ~16ms 轮询定时器；
  （Windows 拖动时鼠标事件可能滞后，轮询全局光标保证贴手）
- 定时器每拍发出 期望窗口位置 = 当前光标 − grab_point；
- release：拖动过 → 回 IDLE（并补最后一帧位置）；否则视为点击 →
  请求 HAPPY + 发出 pet_clicked（未来点击行为扩展点）。

注意：grab_point 是“窗口内本地坐标”，不是窗口左上角位置。
若误用 `global − local`，会得到按下时的窗口左上角，导致拖动瞬移、不贴手。
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, QPoint, QTimer, Signal
from PySide6.QtGui import QCursor

DRAG_THRESHOLD_PX = 8  # 判定为拖动的累计位移阈值
POLL_MS = 16           # 拖动跟随的光标轮询间隔（≈60fps）


class InteractionController(QObject):
    state_requested = Signal(str)   # "HAPPY" | "DRAG" | "IDLE"
    pet_clicked = Signal(QPoint)    # 点击位置（全局坐标），未来行为扩展点
    move_requested = Signal(QPoint) # 期望窗口左上角（屏幕坐标）

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._pressed = False
        self._dragging = False
        self._offset = QPoint()     # 抓取点（窗口内本地坐标），按下时捕获，全程不变
        self._press_global = QPoint()
        self._timer = QTimer(self)
        self._timer.setInterval(POLL_MS)
        self._timer.timeout.connect(self._poll_cursor)

    def on_mouse_press(self, global_pos: QPoint, window_pos: QPoint) -> None:
        """window_pos 是窗口内的本地坐标（抓取点）。"""
        self._pressed = True
        self._dragging = False
        self._press_global = global_pos
        self._offset = window_pos  # 抓取点：窗口左上角应保持 光标−offset 与光标对齐

    def on_mouse_move(self, global_pos: QPoint) -> None:
        if not self._pressed or self._dragging:
            return
        # 累计位移超阈值才算“真的在拖”，避免按下瞬间的抖动误判
        if (global_pos - self._press_global).manhattanLength() < DRAG_THRESHOLD_PX:
            return
        self._dragging = True
        self.state_requested.emit("DRAG")
        self._timer.start()
        self._poll_cursor()  # 立即先对齐一帧

    def on_mouse_release(self, global_pos: QPoint) -> None:
        if not self._pressed:
            return
        self._pressed = False
        self._timer.stop()
        if self._dragging:
            self._dragging = False
            self.move_requested.emit(global_pos - self._offset)  # 补最后一帧
            self.state_requested.emit("IDLE")
        else:
            self.pet_clicked.emit(global_pos)
            self.state_requested.emit("HAPPY")

    def _poll_cursor(self) -> None:
        # 窗口左上角 = 当前光标 − 抓取点，抓取点始终在光标正下方，保证贴手
        self.move_requested.emit(QCursor.pos() - self._offset)
