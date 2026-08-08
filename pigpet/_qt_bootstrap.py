"""PySide6 DLL 加载引导（Windows / Anaconda venv 专用）。

背景
----
Anaconda 的 ``python313.dll`` 在进程启动时就从其目录抢先加载了
``VCRUNTIME140.dll``（14.44.35208）。PySide6 6.11.1 捆绑的是 35211 系列
运行时。Python 3.8+ 导入 ``.pyd`` 使用受限 DLL 搜索（不会经过 PATH），
受限搜索下捆绑的 ``msvcp140.dll`` (35211) 无法绑定到进程内已加载的
35208 版 ``vcruntime140.dll``，导致：

    ImportError: DLL load failed while importing QtCore: 找不到指定的程序
    (WinError 127)

验证结论
--------
- 单独预加载运行库 DLL 不奏效；
- 用非受限搜索手动加载 ``QtCore.pyd``（连同 Qt6Core.dll、msvcp140 等
  整条依赖链）后，Python 后续受限 import 命中"已加载模块"即直接成功。

本模块把该步骤固化为 ``ensure_qt()``，必须在任何 ``from PySide6.QtCore``
类 import 之前调用。非 Windows 环境是空操作。
"""

from __future__ import annotations

import ctypes
import os
import sys


def _warmup_qtcore() -> None:
    """手动以非受限搜索加载 QtCore.pyd，暖机整条 Qt 依赖链。"""
    import PySide6  # 只做目录设置 + 导入 shiboken6，本身是安全的

    pyside_dir = os.path.dirname(PySide6.__file__)
    qcore = os.path.join(pyside_dir, "QtCore.pyd")
    if not os.path.isfile(qcore):
        return  # 环境异常时交给正常 import 报错，不给误导性提示

    kernel32 = ctypes.windll.kernel32
    kernel32.LoadLibraryExW.restype = ctypes.c_void_p
    kernel32.LoadLibraryExW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_void_p,
        ctypes.c_ulong,
    ]
    # LOAD_WITH_ALTERED_SEARCH_PATH (0x8)：依赖从 QtCore.pyd 所在目录开始找，
    # 不受受限搜索影响；失败不 raise，让真正的 import 抛原始错误。
    kernel32.LoadLibraryExW(qcore, None, 0x8)


def ensure_qt() -> None:
    """确保后续 ``from PySide6.QtCore import ...`` 可用。幂等，可重复调用。"""
    if sys.platform != "win32":
        return
    # 若 QtCore 已经能正常导入（例如换成了干净环境），无需暖机
    if "PySide6" in sys.modules and any(
        m for m in sys.modules if m == "PySide6.QtCore" or m.startswith("PySide6.QtCore.")
    ):
        return
    _warmup_qtcore()
