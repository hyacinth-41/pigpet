"""动画帧源抽象。UI 只消费 current_pixmap()，不关心后端。

V1 两个后端：
- StaticPlayer   —— 静态图（PNG），单帧；
- GifPlayer      —— QMovie 懒解码 GIF，可变速。
未来帧表动画通过扩展 make_player() 工厂接入，FSM/窗口无需改动。

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


class StaticPlayer(AnimationPlayer):
    """静态图（PNG/WebP 等单帧）。"""

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._pix = QPixmap()

    def load(self, spec: AssetSpec) -> None:
        self._pix = QPixmap(spec.path)
        if self._pix.isNull():
            raise ValueError(f"无法加载图片素材：{spec.path}")
        self.frame_changed.emit()

    def set_speed(self, speed: float) -> None:
        pass  # 静态图没有速度概念

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def current_pixmap(self) -> QPixmap:
        return self._pix


class GifPlayer(AnimationPlayer):
    """QMovie 后端，GIF 懒解码。"""

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._movie = QMovie(self)
        self._movie.frameChanged.connect(lambda _frame: self.frame_changed.emit())

    def load(self, spec: AssetSpec) -> None:
        self._movie.stop()
        self._movie.setFileName(spec.path)
        if not self._movie.isValid():
            raise ValueError(f"无法加载 GIF 素材：{spec.path}")
        self._movie.start()
        self.frame_changed.emit()  # 首帧立即可画

    def set_speed(self, speed: float) -> None:
        # QMovie.setSpeed 接受整数百分比（100 = 原始速度）
        self._movie.setSpeed(int(speed * 100))

    def start(self) -> None:
        self._movie.start()

    def stop(self) -> None:
        self._movie.stop()

    def current_pixmap(self) -> QPixmap:
        return self._movie.currentPixmap()


def make_player(spec: AssetSpec) -> AnimationPlayer:
    """按素材类型创建播放器。未来帧表素材在此分派。"""
    ext = Path(spec.path).suffix.lower()
    if ext == ".gif":
        return GifPlayer()
    return StaticPlayer()
