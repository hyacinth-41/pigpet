"""应用元信息与配置路径解析。纯标准库，无需 Qt。"""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "LittlePig"
APP_VERSION = "0.1.0"

# 环境变量覆盖（用于开发/测试），例如 PIG_CONFIG_DIR=/tmp/pig
_CONFIG_DIR_ENV = "PIG_CONFIG_DIR"


def resolve_config_path(override: str | os.PathLike | None = None) -> Path:
    """解析配置文件路径。

    优先级：显式 override > 环境变量 PIG_CONFIG_DIR > %APPDATA%/LittlePig/config.json
    """
    if override is not None:
        return Path(override)

    env_dir = os.environ.get(_CONFIG_DIR_ENV)
    if env_dir:
        return Path(env_dir) / "config.json"

    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(base) / APP_NAME / "config.json"
