"""动画管理器：把“状态”翻译成“素材 + 播放速度”。

- set_state_assets: 状态→素材映射；set_default_asset: 无专有素材状态的回退；
- set_state_speed: 每状态独立播放速度（HAPPY 可更快，DRAG 可更慢…）；
- on_state_changed 由 FSM 的 state_changed 触发，切换素材并应用速度。
- 素材均为 None 时保持当前画面不动（例如未来“定住”状态）。
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject

from .assets import AssetSpec
from .player import AnimationPlayer


class AnimationManager(QObject):
    def __init__(
        self,
        player: AnimationPlayer,
        default_speed: float = 1.0,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._player = player
        self._default_speed = default_speed
        self._assets: dict[str, Optional[AssetSpec]] = {}
        self._default_spec: Optional[AssetSpec] = None
        self._speeds: dict[str, float] = {}

    def set_state_assets(self, mapping: dict[str, Optional[AssetSpec]]) -> None:
        self._assets.update(mapping)

    def set_default_asset(self, spec: Optional[AssetSpec]) -> None:
        self._default_spec = spec

    def set_state_speed(self, state: str, speed: float) -> None:
        self._speeds[state] = speed

    def on_state_changed(self, _old: str, new: str) -> None:
        spec = self._assets.get(new)
        if spec is None:
            spec = self._default_spec
        if spec is None:
            return  # 保持当前画面
        self._player.load(spec)
        self._player.set_speed(self._speeds.get(new, self._default_speed))
        self._player.start()
