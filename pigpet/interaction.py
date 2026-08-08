"""InteractionController：点击/拖动交互控制器（UI 无关）。

只发出「状态请求」与「期望窗口位置」信号，不碰 QWidget。偏移数学是
“不跳动、贴手”的保证：

- press 时捕获一次抓取点 grab_point（窗口内本地坐标），全程不变；
  目标始终是：窗口左上角 = 当前光标 − grab_point，即抓取点在光标正下方；
- 移动超过阈值(≈8px)判定为拖动 → 请求 DRAG，启动 ~16ms 轮询定时器；
  （Windows 拖动时鼠标事件可能滞后，轮询全局光标保证贴手）
- 定时器每拍发出 期望窗口位置 = 当前光标 − grab_point；
- release：拖动过 → 回 IDLE（并补最后一帧位置）；否则进入双击确认窗：
  确认窗内第二次点击 → 双击（double_clicked + HAPPY）；超时 = 单击
  （仅发 pet_clicked，无 HAPPY）。

拖动候选机制（防止双击被按住期抖动吞掉）：
- 真实双击时手指按住的瞬间常有 5~40px 漂移，若越过阈值就立即判为拖动，
  双击确认窗会被取消（历史 bug：双击无反应）。
- 因此越过阈值先进入“拖动候选”：① 位移 ≥ TAP_MAX_DRIFT_PX 立即拖动；
  ② 否则等 TAP_MAX_HOLD_MS，期间松开 → 按点击结算（进双击确认窗）；
  ③ 超过 TAP_MAX_HOLD_MS 仍按住 → 正式拖动。候选期窗口不跟随，避免点按滑走。

注意：grab_point 是“窗口内本地坐标”，不是窗口左上角位置。
若误用 `global − local`，会得到按下时的窗口左上角，导致拖动瞬移、不贴手。
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, QPoint, QTimer, Signal
from PySide6.QtGui import QCursor, QGuiApplication

DRAG_THRESHOLD_PX = 8  # 位移超过该值 → 进入拖动候选
TAP_MAX_HOLD_MS = 300  # 候选期按住 ≤300ms 松开 → 视为快速点按（进双击确认窗）
TAP_MAX_DRIFT_PX = 40  # 位移超过该值 → 立即判定为拖动（不等候选期）
POLL_MS = 16           # 拖动跟随的光标轮询间隔（≈60fps）


class InteractionController(QObject):
    state_requested = Signal(str)   # "HAPPY" | "DRAG" | "IDLE"
    pet_clicked = Signal(QPoint)    # 点击位置（全局坐标），未来行为扩展点
    double_clicked = Signal(QPoint)  # 双击（确认窗内两次点击）；单击走 pet_clicked
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
        self._pending_click = False            # 双击确认窗内等待第二次点击
        self._click_resolved = False           # 本次手势是否已在按住期间按单击处理（超时），松手不再重开确认窗
        self._click_pos = QPoint()             # 第一次点击位置（供信号使用）
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.setInterval(
            QGuiApplication.styleHints().mouseDoubleClickInterval()
        )
        self._click_timer.timeout.connect(self._on_click_timeout)
        self._drag_candidate = False   # 已越过拖动阈值但尚未正式判定为拖动
        self._drag_timer = QTimer(self)  # 候选保持期到点 → 正式拖动
        self._drag_timer.setSingleShot(True)
        self._drag_timer.setInterval(TAP_MAX_HOLD_MS)
        self._drag_timer.timeout.connect(self._start_drag)

    def on_mouse_press(self, global_pos: QPoint, window_pos: QPoint) -> None:
        """window_pos 是窗口内的本地坐标（抓取点）。"""
        self._pressed = True
        self._dragging = False
        self._drag_candidate = False  # 新手势开始，重置拖动候选
        self._click_resolved = False  # 新手势开始，重置按住超时标记
        self._press_global = global_pos
        self._offset = window_pos  # 抓取点：窗口左上角应保持 光标−offset 与光标对齐

    def on_mouse_move(self, global_pos: QPoint) -> None:
        if not self._pressed or self._dragging:
            return
        dist = (global_pos - self._press_global).manhattanLength()
        # 累计位移超阈值才算“真的在拖”，避免按下瞬间的抖动误判
        if dist < DRAG_THRESHOLD_PX:
            return
        if dist >= TAP_MAX_DRIFT_PX:
            # 大位移 → 立即拖动（真实拖动不会停在候选区）
            self._drag_candidate = True
            self._start_drag()
            return
        if not self._drag_candidate:
            # 小位移越阈 → 进入候选：快速松开按点击结算；持续按住则正式拖动
            self._drag_candidate = True
            self._drag_timer.start()

    def on_mouse_release(self, global_pos: QPoint) -> None:
        if not self._pressed:
            return
        self._pressed = False
        self._timer.stop()
        self._drag_timer.stop()
        if self._dragging:
            self._dragging = False
            self._drag_candidate = False
            self.move_requested.emit(global_pos - self._offset)  # 补最后一帧
            self.state_requested.emit("IDLE")
            return  # 真拖动：不进入双击判定
        # 未正式拖动（含候选期快速松开的“点按”）→ 单击/双击判定
        self._drag_candidate = False
        if self._pending_click:
            # 确认窗内第二次点击 → 双击
            self._pending_click = False
            self._click_timer.stop()
            self.double_clicked.emit(global_pos)
            self.state_requested.emit("HAPPY")
        elif self._click_resolved:
            # 按住期间已超时按单击处理：松手仅清标记，不再重开确认窗
            self._click_resolved = False
        else:
            # 第一次点击：进入确认窗，等待第二次；超时即单击（无动作）
            self._pending_click = True
            self._click_pos = global_pos
            self._click_timer.start()

    def _start_drag(self) -> None:
        """正式进入拖动：取消双击确认窗，请求 DRAG，启动跟随轮询。"""
        if not self._pressed or self._dragging:
            return
        self._dragging = True
        self._drag_timer.stop()
        # 拖动打断双击确认窗：不再等待第二次点击
        self._pending_click = False
        self._click_timer.stop()
        self.state_requested.emit("DRAG")
        self._timer.start()
        self._poll_cursor()  # 立即先对齐一帧

    def _on_click_timeout(self) -> None:
        """双击确认窗超时 = 单击：无动作，仅发扩展信号。"""
        self._pending_click = False
        self._click_resolved = True  # 按住期间超时：本次手势已按单击处理
        self.pet_clicked.emit(self._click_pos)

    def _poll_cursor(self) -> None:
        # 窗口左上角 = 当前光标 − 抓取点，抓取点始终在光标正下方，保证贴手
        self.move_requested.emit(QCursor.pos() - self._offset)
