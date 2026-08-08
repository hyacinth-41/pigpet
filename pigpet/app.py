"""PetApp：装配中枢，唯一的信号接线点。

各模块互不感知，只有这里知道如何连接：
  FSM.state_changed → animator / window（状态→素材与视觉指示）
  interaction.state_requested → FSM（点击→HAPPY；拖动→DRAG→回 IDLE）
  interaction.move_requested → window.move（拖动跟随，无跳动）
  window.pos_changed → info panel.anchor_to（面板跟随）
  monitor.values_updated → info panel（数值刷新）
  settings_window.applied → _apply_settings（生效 + 持久化）
  tray / 桌宠右键 → 打开设置 / 退出
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .animator import AnimationManager
from .assets import Assets, DEFAULT_ASSET_DIR
from .config import resolve_config_path
from .info_panel import InfoPanel
from .interaction import InteractionController
from .monitor import SystemMonitor
from .pet_window import PetWindow
from .player import AnimationPlayer, make_player
from .settings import Settings
from .settings_window import SettingsWindow
from .state_machine import StateMachine
from .tray import TrayIcon

HAPPY_AUTO_BACK_MS = 2500  # HAPPY 停留时长后自动回 IDLE


class PetApp(QObject):
    def __init__(self, qt_app: QApplication, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.qt_app = qt_app

        # ---- 配置 ----
        self.config_path = resolve_config_path()
        self.settings = Settings.load(self.config_path)

        # ---- 素材：状态→素材映射（V1：IDLE/HAPPY 有专有素材，DRAG 回退默认） ----
        # 被拎起素材替换点：把正式素材命名为 drag.gif 放进 assets/ 即可自动启用，
        # 无需改代码；没有时回退默认素材 + 变暗指示（P4）。
        self.assets = Assets()
        drag_asset = "drag.png" if (DEFAULT_ASSET_DIR / "drag.png").is_file() else None
        state_assets = self.assets.state_map(
            {"IDLE": "idle.png", "HAPPY": "happy.gif", "DRAG": drag_asset}
        )

        # ---- 动画 ----
        self.player: AnimationPlayer = make_player(state_assets["IDLE"])  # type: ignore[arg-type]
        # 先加载初始素材再创建窗口：窗口尺寸需要 = 素材尺寸，
        # 否则 0×0 窗口画不出小猪（UpdateLayeredWindowIndirect 也会失败）。
        self.player.load(state_assets["IDLE"])  # type: ignore[arg-type]
        self.animator = AnimationManager(self.player)
        self.animator.set_state_assets(state_assets)
        self.animator.set_default_asset(state_assets["IDLE"])
        self.animator.set_state_speed("IDLE", 1.0)
        self.animator.set_state_speed("HAPPY", 1.2)  # 开心时活泼一点

        # ---- 状态机 ----
        self.fsm = StateMachine()
        self.fsm.add_state("IDLE")
        self.fsm.add_state("HAPPY", auto_after_ms=HAPPY_AUTO_BACK_MS, auto_to="IDLE")
        self.fsm.add_state("DRAG")  # 状态已定义；触发逻辑由 InteractionController 驱动

        # ---- 交互（P3：点击 → HAPPY；拖动 → DRAG / 跟随 / 松手回 IDLE） ----
        self.interaction = InteractionController(self)

        # ---- 系统监控 + 信息面板（P5） ----
        enabled_keys = {
            k for k, flag in (
                ("cpu", self.settings.show_cpu),
                ("ram", self.settings.show_ram),
                ("gpu", self.settings.show_gpu),
            ) if flag
        }
        self.monitor = SystemMonitor(
            interval_ms=self.settings.monitor_interval_ms,
            enabled=enabled_keys,
            parent=self,
        )
        self.panel = InfoPanel()
        self.panel.set_metrics([(m.key, m.label) for m in self.monitor.metrics()])

        # ---- 窗口 ----
        self.window = PetWindow(self.player)
        # 有专门 drag 素材就不用变暗兜底;没有则回退 idle+变暗
        self.window.set_drag_dim(drag_asset is None)
        # 窗口尺寸 = 素材尺寸 × 缩放（默认 512×512 → 256×256）
        self.window.set_scale(self.settings.pet_scale)
        self.window.set_always_on_top(self.settings.always_on_top)
        self.window.set_interaction(self.interaction)
        # 面板初始位置：桌宠显示后再锚定
        self._apply_panel_visibility()
        self.panel.set_always_on_top(self.settings.always_on_top)

        # ---- 接线 ----
        self.fsm.state_changed.connect(self.animator.on_state_changed)
        self.fsm.state_changed.connect(lambda _o, n: self.window.set_state(n))
        self.player.frame_changed.connect(self.window.update)
        self.interaction.state_requested.connect(self.fsm.request)
        self.interaction.move_requested.connect(self.window.move)
        self.interaction.pet_clicked.connect(self._on_pet_clicked)
        self.window.exit_requested.connect(self._quit)
        self.window.pos_changed.connect(self._anchor_panel)
        self.monitor.values_updated.connect(self.panel.update_values)
        self.window.settings_requested.connect(self._show_settings)

        # ---- 设置窗口 + 托盘（P6） ----
        self.settings_window = SettingsWindow(self.settings)
        self.settings_window.applied.connect(self._apply_settings)

        self.tray = None
        if TrayIcon.is_available():
            icon_path = DEFAULT_ASSET_DIR / "idle.png"
            self.tray = TrayIcon(QIcon(str(icon_path)))
            self.tray.settings_requested.connect(self._show_settings)
            self.tray.exit_requested.connect(self._quit)
            self.tray.show()

        # ---- 启动 ----
        self.fsm.start()  # 进入 IDLE，触发初始素材加载
        self.window.show_at_default_position()
        self._anchor_panel(self.window.pos())  # 面板锚到初始位置
        self.monitor.start()

    def _on_pet_clicked(self, _pos) -> None:
        """点击行为扩展点。V1 已通过 state_requested("HAPPY") 触发互动；
        未来可在此加入新行为（喂食、说话气泡等）。"""

    def _anchor_panel(self, pos) -> None:
        self.panel.anchor_to(pos, self.window.size())

    def _apply_panel_visibility(self) -> None:
        if self.settings.show_panel:
            self.panel.show()
        else:
            self.panel.hide()

    def _quit(self) -> None:
        self.shutdown()
        self.qt_app.quit()

    def _show_settings(self) -> None:
        """从托盘/桌宠右键菜单打开设置窗口。"""
        self.settings_window.load(self.settings)  # 每次打开都反映最新配置
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    def _apply_settings(self, settings: Settings) -> None:
        """设置生效：缩放/置顶/面板/指标/间隔，并持久化到配置文件。"""
        self.settings = settings
        self.window.set_scale(settings.pet_scale)
        self.window.set_always_on_top(settings.always_on_top)
        self.panel.set_always_on_top(settings.always_on_top)
        self._apply_panel_visibility()
        self.monitor.set_enabled(
            {
                k
                for k, flag in (
                    ("cpu", settings.show_cpu),
                    ("ram", settings.show_ram),
                    ("gpu", settings.show_gpu),
                )
                if flag
            }
        )
        self.panel.set_metrics([(m.key, m.label) for m in self.monitor.metrics()])
        self.monitor.set_interval_ms(settings.monitor_interval_ms)
        settings.save(self.config_path)

    def shutdown(self) -> None:
        """退出前的清理。"""
        self.monitor.stop()
        self.panel.hide()
        self.window.hide()
