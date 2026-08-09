"""动画帧源抽象。UI 只消费 current_pixmap()，不关心后端。

V1.1 单一播放器按素材类型切换后端：
- MixedPlayer  —— load() 按扩展名分派：GIF → QMovie 懒解码动画；其他 → QPixmap 静态。
make_player() 恒返回 MixedPlayer；状态切换由 animator 重载素材，窗口无需感知。
未来帧表动画通过扩展 load() 分派接入，FSM/窗口无需改动。

注意：QMovie 必须被持有否则被 GC；load() 前先 stop() 旧 movie。
GIF 素材通常无限循环（loop=0），HAPPY→IDLE 由 FSM 定时转换负责，不用 finished()。
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QMovie, QPixmap

from .assets import AssetSpec


class AnimationPlayer(QObject):
    """动画帧源抽象基类。"""

    frame_changed = Signal()  # 新帧就绪 → 视图 update()

    def load(self, spec: AssetSpec) -> None:
        raise NotImplementedError

    def set_speed(self, speed: float) -> None:
        """speed: 播放速度倍率，1.0 = 原始速度。"""

    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...

    def current_pixmap(self) -> QPixmap:
        raise NotImplementedError


class MixedPlayer(AnimationPlayer):
    """按素材类型切换后端：GIF → QMovie 动画；其他 → QPixmap 静态。

    idle.png / drag.png 走静态快速路径（无逐帧 QImage→QPixmap 转换），
    happy.gif 真正播放多帧动画。切回静态时停掉仍在播的 QMovie。
    frame_changed 统一转发（首帧立即可画 + 动画每帧）。
    """

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._movie = QMovie(self)
        self._movie.frameChanged.connect(lambda _frame: self.frame_changed.emit())
        self._pix = QPixmap()
        self._is_gif = False

    def load(self, spec: AssetSpec) -> None:
        ext = Path(spec.path).suffix.lower()
        self._is_gif = ext == ".gif"
        self._movie.stop()  # 先停掉可能仍在播的 GIF（含切回静态时）
        if self._is_gif:
            self._movie.setFileName(spec.path)
            if not self._movie.isValid():
                raise ValueError(f"无法加载 GIF 素材：{spec.path}")
            self._movie.start()
        else:
            self._pix = QPixmap(spec.path)
            if self._pix.isNull():
                raise ValueError(f"无法加载图片素材：{spec.path}")
        self.frame_changed.emit()  # 首帧立即可画

    def set_speed(self, speed: float) -> None:
        if self._is_gif:
            # QMovie.setSpeed 接受整数百分比（100 = 原始速度）
            self._movie.setSpeed(int(speed * 100))

    def start(self) -> None:
        if self._is_gif:
            self._movie.start()

    def stop(self) -> None:
        self._movie.stop()

    def current_pixmap(self) -> QPixmap:
        return self._movie.currentPixmap() if self._is_gif else self._pix


def make_player(spec: AssetSpec) -> AnimationPlayer:
    """创建播放器。混合后端按 load() 时的素材类型分派，恒返回同一个即可。

    spec 参数保留用于未来帧表素材的构造期分派；当前后端由 load() 内决定。
    """
    return MixedPlayer()
