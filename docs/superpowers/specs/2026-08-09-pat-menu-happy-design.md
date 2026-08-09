# 右键菜单「拍一拍」触发 happy 动画 — 设计

日期：2026-08-09 · 项目：LittlePig 小猪桌宠 · 状态：已批准

## 背景与目标

双击触发 HAPPY 的方案经两轮修复（`854f49f`、`07d87e5`）仍不可靠（真实双击按住期漂移、慢按单击误判等根因难以穷尽）。已决定**放弃双击方案**，改用右键菜单显式触发：

- **回滚双击逻辑**：移除 `interaction.py` 的确认窗机制与 `double_clicked` 信号，单击无动作（仅发 `pet_clicked` 扩展信号）。**拖动切 drag 部分不回滚**（拖动候选机制、`drag.png`、窗口基准尺寸恒定、`set_drag_dim` 全保留）。
- **新增「拍一拍」**：右键小猪的菜单栏顶部添加「拍一拍」菜单项，点击即触发 happy 动画。

已与用户确认的决策：

- 单击行为：**无动作**（回滚后恢复，HAPPY 只由「拍一拍」显式触发）。
- 重复拍打：**重新播放**——已在 HAPPY 中再点「拍一拍」，从头重播 happy.gif 并重置 2.5s 自动回计时（用 `fsm.force("HAPPY")`）。
- 菜单位置：**置顶**（右键菜单第一项）。

## 现状分析（关键发现）

- `pet_window.py` `_build_context_menu()`：右键菜单现有「打开设置」「退出」，均通过 `QAction.triggered → Signal.emit` 发出，由 `app.py` 统一接线。这是本仓库的既有模式。
- `app.py` 已有 `_on_pet_clicked` 扩展点（单击无动作）；`pet_clicked` 已接好，无需新接线。
- HAPPY 触发路径：`fsm.force/request("HAPPY")` → `state_changed` → `animator.on_state_changed` → `GifPlayer.load(happy.gif)` → 播放；FSM `HAPPY` 状态自带 `auto_after_ms=2500` 自动回 IDLE。全部复用。
- `GifPlayer.load()`（`player.py:78-84`）每次 `stop()` + `setFileName()` + `start()`，QMovie 从头重播；`fsm.force("HAPPY")` 即使已在 HAPPY 也会触发 `state_changed("HAPPY","HAPPY")` → 重载重播，并 `_schedule_auto()` 重置 2.5s 计时。**重播可达成**。
- 边界：Qt 左键拖动中按右键仍会弹上下文菜单，此时点「拍一拍」若直接 `force("HAPPY")` 会把 FSM 从 DRAG 切走、拖动画面变成 happy.gif。需 `DRAG` 守卫。

## 功能：右键菜单「拍一拍」

改动三个文件：

### pet_window.py

- 信号区新增一行（与 `settings_requested`/`exit_requested` 并列）：

```python
    pat_requested = Signal()      # 右键菜单「拍一拍」→ 重播 happy 动画
```

- `_build_context_menu()` 顶部插入（置顶）：

```python
        self._menu.addAction("拍一拍").triggered.connect(self.pat_requested.emit)
        self._menu.addAction("打开设置").triggered.connect(self.settings_requested.emit)
```

### app.py

- 接线区新增（`self.interaction.pet_clicked.connect(...)` 附近）：

```python
        self.window.pat_requested.connect(self._on_pat_requested)
```

- 新增方法（放 `_on_pet_clicked` 旁）：

```python
    def _on_pat_requested(self) -> None:
        """「拍一拍」：重播 happy 动画（即使已在播放）。"""
        if self.fsm.current != "DRAG":  # 拖动中被拍一拍不打断拖动
            self.fsm.force("HAPPY")
```

### main.py（selftest）

- 用「触发真实菜单动作」替代现在的直接 `pet_app.fsm.request("HAPPY")`：

```python
    def step_single_check() -> None:
        checks["single_ok"] = pet_app.fsm.current == "IDLE"  # 单击无动作
        print(...)
        # HAPPY 走真实路径：右键菜单「拍一拍」动作 → pat_requested → force HAPPY
        act = next(a for a in pet_app.window._menu.actions() if a.text() == "拍一拍")
        act.trigger()
        checks["happy_ok"] = pet_app.fsm.current == "HAPPY"
        print(...)
        # 重播断言：HAPPY 中再触发一次仍为 HAPPY（force 幂等可用、不抛错）
        act.trigger()
        checks["happy_ok"] = checks["happy_ok"] and pet_app.fsm.current == "HAPPY"
        print(...)
        QTimer.singleShot(400, step_happy_check)
```

`step_happy_check` 不变（pixmap 非空 + 等待自动回）。`happy_ok` 已并入最终 `ok`（回滚时已改）。

## 边界与不特判项

- **拖动中被拍一拍**：`_on_pat_requested` 的 `DRAG` 守卫忽略之，拖动不受影响（这是唯一需特判的边界）。
- **HAPPY 中拍一拍**：重播（已确认）。
- **素材缺失**：happy.gif 与现有 HAPPY 状态映射一致，不引入新风险。

## 风险

1. `fsm.force("HAPPY")` 触发同状态 `state_changed("HAPPY","HAPPY")`，animator 会重载重播——已验证 GifPlayer.load 从头播；StaticPlayer 场景（happy 为 PNG 时）重播即重绘同帧，无副作用。
2. 右键菜单弹窗期间 FSM 无变化，不会出现状态竞态。

## 改动文件清单

| 文件 | 改动 |
|---|---|
| `pigpet/pet_window.py` | `pat_requested` 信号 + 菜单置顶「拍一拍」动作 |
| `pigpet/app.py` | `pat_requested` 接线 + `_on_pat_requested`（含 DRAG 守卫） |
| `pigpet/main.py` | selftest：菜单动作触发 HAPPY + 重播断言 |

不改：`interaction.py`、`state_machine.py`、`animator.py`、`player.py`、`assets.py`。
