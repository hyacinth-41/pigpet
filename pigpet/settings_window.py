"""设置窗口（非模态，应用/关闭）。只管收集/提交表单，不直接改运行状态。

- applied(Settings) 信号发出后，由 app._apply_settings 落实并持久化；
- 点“应用”或“关闭”都不阻塞桌宠（非模态 show()）；
- 关闭按钮只隐藏窗口，不销毁，可反复打开。
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .settings import (
    MAX_INTERVAL_MS,
    MAX_PET_SCALE,
    MIN_INTERVAL_MS,
    MIN_PET_SCALE,
    Settings,
)


class SettingsWindow(QDialog):
    applied = Signal(Settings)

    def __init__(
        self,
        settings: Settings,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("小猪设置")
        self.setModal(False)  # 非模态：设置时桌宠继续工作

        self.cb_cpu = QCheckBox("显示 CPU 使用率")
        self.cb_ram = QCheckBox("显示 内存使用率")
        self.cb_gpu = QCheckBox("显示 GPU 使用率")
        self.cb_panel = QCheckBox("显示信息面板")
        self.cb_top = QCheckBox("桌宠始终置顶")
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(MIN_INTERVAL_MS, MAX_INTERVAL_MS)
        self.spin_interval.setSingleStep(250)
        self.spin_interval.setSuffix(" ms")
        self.spin_scale = QDoubleSpinBox()
        self.spin_scale.setRange(MIN_PET_SCALE, MAX_PET_SCALE)
        self.spin_scale.setSingleStep(0.1)
        self.spin_scale.setDecimals(1)
        self.spin_scale.setSuffix("×")

        form = QFormLayout()
        form.addRow(self.cb_cpu)
        form.addRow(self.cb_ram)
        form.addRow(self.cb_gpu)
        form.addRow(self.cb_panel)
        form.addRow(self.cb_top)
        form.addRow("监控刷新间隔", self.spin_interval)
        form.addRow("角色大小", self.spin_scale)

        btn_apply = QPushButton("应用")
        btn_close = QPushButton("关闭")
        btn_apply.clicked.connect(self._on_apply)
        btn_close.clicked.connect(self.close)
        btns = QHBoxLayout()
        btns.addStretch(1)
        btns.addWidget(btn_apply)
        btns.addWidget(btn_close)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addLayout(btns)

        self.load(settings)

    def load(self, settings: Settings) -> None:
        """用当前配置初始化表单。"""
        self.cb_cpu.setChecked(settings.show_cpu)
        self.cb_ram.setChecked(settings.show_ram)
        self.cb_gpu.setChecked(settings.show_gpu)
        self.cb_panel.setChecked(settings.show_panel)
        self.cb_top.setChecked(settings.always_on_top)
        self.spin_interval.setValue(settings.monitor_interval_ms)
        self.spin_scale.setValue(settings.pet_scale)

    def current_settings(self) -> Settings:
        return Settings(
            show_cpu=self.cb_cpu.isChecked(),
            show_ram=self.cb_ram.isChecked(),
            show_gpu=self.cb_gpu.isChecked(),
            show_panel=self.cb_panel.isChecked(),
            always_on_top=self.cb_top.isChecked(),
            monitor_interval_ms=self.spin_interval.value(),
            pet_scale=round(self.spin_scale.value(), 1),
        )

    def _on_apply(self) -> None:
        self.applied.emit(self.current_settings())
