"""SystemMonitor：系统状态监控。数据由单个 QTimer 定时读取，绝不逐帧读。

- Metric 抽象：key（标识）、label（显示名）、read()（返回格式化字符串或 None）；
- 任何指标读取失败都返回 None（面板显示“不可用”），绝不抛异常/崩溃；
- CpuMetric 首次用一次 0.1s 阻塞样本预热，避免首拍为 0；
- GpuMetric 调用 nvidia-smi（1.5s 超时 + CREATE_NO_WINDOW 防控制台闪窗），
  缺二进制时退避几拍再试，不逐拍空转；
- 未来新增 网络/磁盘/电池 指标：实现 Metric 子类并加进 _poll 即可。

依赖：psutil（见 requirements.txt）。
"""

from __future__ import annotations

import subprocess
import sys
from abc import ABC, abstractmethod
from typing import Optional

import psutil

from PySide6.QtCore import QObject, QTimer, Signal

GPU_TIMEOUT_S = 1.5          # nvidia-smi 单次超时
GPU_BACKOFF_POLLS = 9        # 缺二进制时跳过多少拍再重试
CPU_PRIME_S = 0.1            # CPU 首拍阻塞预热时长


def _no_window() -> int:
    """Windows 下创建进程不弹控制台窗口；其他平台 0。"""
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


class Metric(ABC):
    key: str
    label: str

    @abstractmethod
    def read(self) -> Optional[str]:
        """返回格式化后的字符串（如 "23%"），失败返回 None。"""


class CpuMetric(Metric):
    key = "cpu"
    label = "CPU"

    def __init__(self) -> None:
        # 预热：先做一次阻塞样本，让首拍有真实值而非 0
        psutil.cpu_percent(interval=CPU_PRIME_S)

    def read(self) -> Optional[str]:
        try:
            return f"{psutil.cpu_percent(interval=None):.0f}%"
        except Exception:
            return None


class RamMetric(Metric):
    key = "ram"
    label = "内存"

    def read(self) -> Optional[str]:
        try:
            return f"{psutil.virtual_memory().percent:.0f}%"
        except Exception:
            return None


class GpuMetric(Metric):
    key = "gpu"
    label = "GPU"

    def __init__(self) -> None:
        self._skip = 0  # 剩余跳过拍数（缺 nvidia-smi 时的退避）

    def read(self) -> Optional[str]:
        if self._skip > 0:
            self._skip -= 1
            return None
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=GPU_TIMEOUT_S,
                creationflags=_no_window(),
                check=False,
            )
            percent = int(out.stdout.strip().splitlines()[0].strip())
            return f"{percent}%"
        except FileNotFoundError:
            self._skip = GPU_BACKOFF_POLLS  # 没有显卡驱动，退避几拍再试
            return None
        except (ValueError, IndexError, subprocess.TimeoutExpired, OSError):
            return None


class SystemMonitor(QObject):
    values_updated = Signal(dict)  # {key: str | None}，如 {"cpu":"23%","ram":"45%","gpu":None}

    def __init__(
        self,
        interval_ms: int = 2000,
        enabled: Optional[set[str]] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._all_metrics: list[Metric] = [CpuMetric(), RamMetric(), GpuMetric()]
        self._enabled: set[str] = {m.key for m in self._all_metrics} if enabled is None else set(enabled)

        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._poll)

    def metrics(self) -> list[Metric]:
        """按启用顺序返回指标（供面板建行/取 label）。"""
        return [m for m in self._all_metrics if m.key in self._enabled]

    def set_enabled(self, enabled: set[str]) -> None:
        self._enabled = set(enabled)

    def set_interval_ms(self, ms: int) -> None:
        self._timer.setInterval(ms)

    def start(self) -> None:
        self._poll()  # 立即采一次，不干等一个间隔
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _poll(self) -> None:
        values: dict[str, Optional[str]] = {}
        for m in self.metrics():
            values[m.key] = m.read()
        self.values_updated.emit(values)
