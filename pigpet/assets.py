"""素材加载：AssetSpec + Assets（状态→素材映射）。纯标准库，无 Qt。

V1 素材为整张图（PNG）或整段 GIF；未来帧表动画（雪碧图/多帧目录）在此
扩展 AssetSpec 字段，Assets/player 的调用方无需改动。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_ASSET_DIR = Path(__file__).resolve().parent.parent / "assets"


@dataclass(frozen=True)
class AssetSpec:
    """一份素材的定位信息。path 为绝对路径。"""

    path: str
    # 未来帧表素材可在此扩展：fps、frame_count、grid_cols/grid_rows 等

    @property
    def name(self) -> str:
        return Path(self.path).name


class Assets:
    """从素材目录加载 AssetSpec，并提供 状态→素材 的映射。"""

    def __init__(self, base_dir: Path = DEFAULT_ASSET_DIR) -> None:
        self._base = Path(base_dir)

    def spec(self, name: str) -> AssetSpec:
        path = self._base / name
        if not path.is_file():
            raise FileNotFoundError(f"素材不存在：{path}")
        return AssetSpec(str(path))

    def state_map(
        self, mapping: dict[str, str | None]
    ) -> dict[str, AssetSpec | None]:
        """把 {状态: 文件名|None} 转成 {状态: AssetSpec|None}。None 表示该状态回退默认素材。"""
        result: dict[str, AssetSpec | None] = {}
        for state, name in mapping.items():
            result[state] = self.spec(name) if name else None
        return result
