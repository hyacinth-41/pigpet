"""设置数据类与本地配置读写。纯 Python，无 Qt，可独立测试。

V1 不含温度字段（与需求决策一致）；未来加入温度/网络等开关时在此扩展。
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

# 字段集合，用于容错解析（不依赖注解自省，避免版本差异）
_BOOL_FIELDS = ("show_cpu", "show_ram", "show_gpu", "show_panel", "always_on_top")
_INT_FIELDS = ("monitor_interval_ms",)
_FLOAT_FIELDS = ("pet_scale",)

MIN_INTERVAL_MS = 500
MAX_INTERVAL_MS = 30000
MIN_PET_SCALE = 0.2   # 角色最小缩放（素材 512 → 最小约 102px）
MAX_PET_SCALE = 1.5


@dataclass
class Settings:
    show_cpu: bool = True
    show_ram: bool = True
    show_gpu: bool = True
    show_panel: bool = True
    always_on_top: bool = True
    monitor_interval_ms: int = 2000
    pet_scale: float = 0.5  # 角色显示缩放倍率（素材 512 → 默认 256）

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: object) -> "Settings":
        """容错解析：非字典忽略；未知键忽略；坏值回默认。"""
        result = cls()
        if not isinstance(data, dict):
            return result
        for name in _BOOL_FIELDS:
            if name in data:
                try:
                    setattr(result, name, bool(data[name]))
                except (TypeError, ValueError):
                    pass
        for name in _INT_FIELDS:
            if name in data:
                try:
                    value = int(data[name])
                except (TypeError, ValueError):
                    continue
                if name == "monitor_interval_ms":
                    value = min(max(value, MIN_INTERVAL_MS), MAX_INTERVAL_MS)
                setattr(result, name, value)
        for name in _FLOAT_FIELDS:
            if name in data:
                try:
                    value = float(data[name])
                except (TypeError, ValueError):
                    continue
                if name == "pet_scale":
                    value = min(max(value, MIN_PET_SCALE), MAX_PET_SCALE)
                setattr(result, name, value)
        return result

    def save(self, path: Path) -> None:
        """原子写：先写临时文件再替换，防止写一半损坏配置。"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp, path)

    @classmethod
    def load(cls, path: Path) -> "Settings":
        """缺失/损坏的配置文件一律回默认，绝不让应用无法启动。"""
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()
        return cls.from_dict(data)
