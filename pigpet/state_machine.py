"""通用最小状态机。纯转换逻辑，不感知动画/鼠标/素材。

- 状态可携带 on_enter / on_exit 回调与“自动转换”定时（如 HAPPY → 2500ms → IDLE）；
- request(name) 已在当前状态则忽略；force(name) 无条件切换；
- 通过 state_changed(old, new) 信号通知外部，本类自身不关心状态含义。
- 后续增加新状态：add_state 一行即可，无需改其他模块。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from PySide6.QtCore import QObject, QTimer, Signal


@dataclass
class _StateDef:
    on_enter: Optional[Callable[[], None]] = None
    on_exit: Optional[Callable[[], None]] = None
    auto_after_ms: Optional[int] = None  # 进入该状态后多久自动转换（None=不自动）
    auto_to: Optional[str] = None        # 自动转换目标状态


class StateMachine(QObject):
    state_changed = Signal(str, str)  # (old, new)

    def __init__(self, initial: str = "IDLE", parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._states: dict[str, _StateDef] = {}
        self._current = initial
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_auto_timeout)

    def add_state(
        self,
        name: str,
        *,
        on_enter: Optional[Callable[[], None]] = None,
        on_exit: Optional[Callable[[], None]] = None,
        auto_after_ms: Optional[int] = None,
        auto_to: Optional[str] = None,
    ) -> None:
        self._states[name] = _StateDef(on_enter, on_exit, auto_after_ms, auto_to)
        if self._current == name:
            self._schedule_auto()

    def start(self) -> None:
        """进入初始状态，触发其 on_enter 与首次 state_changed。"""
        self.force(self._current)

    def request(self, name: str) -> None:
        """请求切换；若已在当前状态则忽略（幂等）。"""
        if name == self._current:
            return
        self.force(name)

    def force(self, name: str) -> None:
        """无条件切换到指定状态（即使相同也触发一次）。"""
        if name not in self._states:
            raise ValueError(f"未知状态：{name}")
        self._timer.stop()
        old = self._current
        if old in self._states and self._states[old].on_exit:
            self._states[old].on_exit()
        self._current = name
        if self._states[name].on_enter:
            self._states[name].on_enter()
        self.state_changed.emit(old, name)
        self._schedule_auto()

    def _schedule_auto(self) -> None:
        st = self._states.get(self._current)
        if st and st.auto_after_ms and st.auto_to:
            self._timer.start(st.auto_after_ms)

    def _on_auto_timeout(self) -> None:
        st = self._states[self._current]
        self.force(st.auto_to)  # type: ignore[arg-type]  # auto_to 必已设置

    @property
    def current(self) -> str:
        return self._current
