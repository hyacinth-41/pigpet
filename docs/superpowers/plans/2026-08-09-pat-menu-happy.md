# 右键菜单「拍一拍」触发 happy 动画 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在右键小猪的菜单**顶部**添加「拍一拍」菜单项，点击即从头重播 happy 动画（已在播放也重播），拖动中拍打被忽略。

**Architecture:** `pet_window.py` 新增 `pat_requested` 信号 + 菜单置顶「拍一拍」动作（沿用 `QAction.triggered → Signal.emit` 既有模式）；`app.py` 接线该信号到 `_on_pat_requested`，用 `fsm.force("HAPPY")` 实现重播，`DRAG` 守卫保证不打断拖动。FSM/animator/player 均不改，happy.gif 与 2.5s 自动回 IDLE 全复用。

**Tech Stack:** PySide6 6.11.1 / psutil 7.2.2 / Python 3.13.5（项目 venv `.venv`）。无 pytest，验证用 offscreen 断言脚本 + `--selftest` 全量。

## Global Constraints

- **必须**先 `from ._qt_bootstrap import ensure_qt; ensure_qt()` 再 `import` 任何 Qt 模块（Anaconda venv 的 WinError 127 陷阱）。
- 所有命令在 bash 下运行，Python 用 `.venv/Scripts/python`；offscreen 单测需 `QT_QPA_PLATFORM=offscreen`。
- 无 pytest；验证用 offscreen 断言脚本（放 `/tmp/`）+ `--selftest` 全量。
- 代码注释与文案用中文，保持现有风格。
- 菜单项文字固定为「拍一拍」；置于菜单顶部（第一个非分隔项）。
- 重复拍打用 `fsm.force("HAPPY")`：已在 HAPPY 中再次拍打仍为 HAPPY，不得抛错。
- FSM 为 DRAG 时点「拍一拍」应被忽略（`_on_pat_requested` 的 `DRAG` 守卫）。

---

### Task 1: pet_window.py —「拍一拍」信号 + 置顶菜单动作

**Files:**
- Modify: `pigpet/pet_window.py`（信号区 27-29 行附近；`_build_context_menu` 87-91 行）

**Interfaces:**
- Consumes: 无（仅本窗口内改动）。
- Produces: `pat_requested = Signal()`；右键菜单第一个非分隔项为「拍一拍」。Task 2 接线、Task 3 selftest 依赖此行为。

- [ ] **Step 1: 写失败测试（offscreen 单测脚本）**

```bash
cat > /tmp/test_pat_menu.py <<'PYEOF'
from pigpet._qt_bootstrap import ensure_qt
ensure_qt()
from PySide6.QtWidgets import QApplication
app = QApplication([])
from pigpet.assets import AssetSpec, DEFAULT_ASSET_DIR
from pigpet.player import StaticPlayer
from pigpet.pet_window import PetWindow

player = StaticPlayer()
player.load(AssetSpec(str(DEFAULT_ASSET_DIR / "idle.png")))
win = PetWindow(player)

fired = []
win.pat_requested.connect(lambda: fired.append(1))

acts = win._menu.actions()
assert any(a.text() == "拍一拍" for a in acts), "菜单应包含「拍一拍」"
non_sep = [a for a in acts if not a.isSeparator()]
assert non_sep[0].text() == "拍一拍", f"「拍一拍」应置顶, got: {non_sep[0].text()}"

next(a for a in acts if a.text() == "拍一拍").trigger()
assert fired, "触发「拍一拍」动作应发出 pat_requested"
print("PASS")
PYEOF
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd "D:\little_project\pig" && QT_QPA_PLATFORM=offscreen .venv/Scripts/python /tmp/test_pat_menu.py`
Expected: FAIL——`win.pat_requested` 属性不存在（`AttributeError`）。

- [ ] **Step 3: 实现（修改 pet_window.py）**

信号区（`exit_requested` 之后）新增一行：

```python
    pat_requested = Signal()      # 右键菜单「拍一拍」→ 重播 happy 动画
```

`_build_context_menu`（现第 87-91 行）改为「拍一拍」置顶：

```python
    def _build_context_menu(self) -> None:
        self._menu = QMenu(self)
        self._menu.addAction("拍一拍").triggered.connect(self.pat_requested.emit)
        self._menu.addAction("打开设置").triggered.connect(self.settings_requested.emit)
        self._menu.addSeparator()
        self._menu.addAction("退出").triggered.connect(self.exit_requested.emit)
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd "D:\little_project\pig" && QT_QPA_PLATFORM=offscreen .venv/Scripts/python /tmp/test_pat_menu.py`
Expected: `PASS`，退出码 0。

- [ ] **Step 5: Commit**

```bash
cd "D:\little_project\pig" && git add pigpet/pet_window.py && git commit -m "feat: 右键菜单置顶「拍一拍」+ pat_requested 信号"
```

---

### Task 2: app.py — 接线 pat_requested → force HAPPY（含 DRAG 守卫）

**Files:**
- Modify: `pigpet/app.py`（接线区 103-113 行附近；`_on_pet_clicked` 133-135 行附近）

**Interfaces:**
- Consumes: Task 1 的 `pet_window.pat_requested = Signal()`。
- Produces: `PetApp._on_pat_requested()`——点「拍一拍」→ `fsm.force("HAPPY")`（重播）；FSM 为 DRAG 时忽略。Task 3 selftest 依赖此行为。

- [ ] **Step 1: 写失败测试（offscreen 单测脚本）**

```bash
cat > /tmp/test_pat_app.py <<'PYEOF'
from pigpet._qt_bootstrap import ensure_qt
ensure_qt()
from PySide6.QtWidgets import QApplication
app = QApplication([])
from pigpet.app import PetApp

pet_app = PetApp(app)
try:
    act = next(a for a in pet_app.window._menu.actions() if a.text() == "拍一拍")

    act.trigger()
    assert pet_app.fsm.current == "HAPPY", f"拍一拍应触发 HAPPY, got {pet_app.fsm.current}"

    # 重播：HAPPY 中再触发仍为 HAPPY（force 幂等、不抛错）
    act.trigger()
    assert pet_app.fsm.current == "HAPPY", f"HAPPY 中重拍应仍为 HAPPY, got {pet_app.fsm.current}"

    # DRAG 守卫：拖动中拍一拍不打断
    pet_app.fsm.force("DRAG")
    act.trigger()
    assert pet_app.fsm.current == "DRAG", f"拖动中拍一拍不应切走, got {pet_app.fsm.current}"
    print("PASS")
finally:
    pet_app.shutdown()
PYEOF
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd "D:\little_project\pig" && QT_QPA_PLATFORM=offscreen .venv/Scripts/python /tmp/test_pat_app.py`
Expected: FAIL——首次 `act.trigger()` 后 FSM 仍为 IDLE（`pat_requested` 未接线），断言 `拍一拍应触发 HAPPY` 触发。

- [ ] **Step 3: 实现（修改 app.py）**

接线区（`self.interaction.pet_clicked.connect(...)` 之后）新增一行：

```python
        self.window.pat_requested.connect(self._on_pat_requested)
```

`_on_pet_clicked` 旁新增方法：

```python
    def _on_pat_requested(self) -> None:
        """「拍一拍」：重播 happy 动画（即使已在播放）。"""
        if self.fsm.current != "DRAG":  # 拖动中被拍一拍不打断拖动
            self.fsm.force("HAPPY")
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd "D:\little_project\pig" && QT_QPA_PLATFORM=offscreen .venv/Scripts/python /tmp/test_pat_app.py`
Expected: `PASS`，退出码 0。

- [ ] **Step 5: Commit**

```bash
cd "D:\little_project\pig" && git add pigpet/app.py && git commit -m "feat: 拍一拍接线 force HAPPY 重播(含 DRAG 守卫)"
```

---

### Task 3: selftest — 改经菜单动作触发 HAPPY + 重播断言

**Files:**
- Modify: `pigpet/main.py`（`_run_selftest` 的 `step_single_check`，现 40-52 行附近；docstring 15-25 行）

**Interfaces:**
- Consumes: Task 1 的菜单「拍一拍」动作、Task 2 的 `_on_pat_requested`。
- Produces: 全量 selftest 经真实菜单路径验证 HAPPY（触发 + 重播 + happy.gif 加载），`happy_ok` 仍并入最终 `ok`。

- [ ] **Step 1: 更新 selftest docstring**

`_run_selftest` docstring 第 3 行改为经菜单动作触发：

```python
    3. HAPPY 动画路径：触发右键菜单「拍一拍」动作 → pat_requested → force HAPPY
       → happy.gif 加载，2500ms 自动回 IDLE；HAPPY 中重拍仍为 HAPPY；
```

- [ ] **Step 2: 替换 `step_single_check` 为菜单动作触发 + 重播断言**

把现 `step_single_check`（`pet_app.fsm.request("HAPPY")` 那段）整体替换为：

```python
    def step_single_check() -> None:
        checks["single_ok"] = pet_app.fsm.current == "IDLE"  # 单击无动作
        print(f"[selftest] after single click -> state: {pet_app.fsm.current} (expect IDLE) -> {'OK' if checks['single_ok'] else 'FAIL'}")
        # HAPPY 走真实路径：右键菜单「拍一拍」动作 → pat_requested → force HAPPY
        pat = next(a for a in pet_app.window._menu.actions() if a.text() == "拍一拍")
        pat.trigger()
        checks["happy_ok"] = pet_app.fsm.current == "HAPPY"
        print(f"[selftest] menu 拍一拍 -> state: {pet_app.fsm.current} (expect HAPPY) -> {'OK' if checks['happy_ok'] else 'FAIL'}")
        # 重播断言：HAPPY 中再触发一次仍为 HAPPY（force 幂等可用）
        pat.trigger()
        checks["happy_ok"] = checks["happy_ok"] and pet_app.fsm.current == "HAPPY"
        print(f"[selftest] replay 拍一拍 -> state: {pet_app.fsm.current} (expect HAPPY) -> {'OK' if checks['happy_ok'] else 'FAIL'}")
        QTimer.singleShot(400, step_happy_check)
```

`step_happy_check` 保持不变（pixmap 非空 + 自动回后进 `step_drag`）。

- [ ] **Step 3: 运行全量 selftest，确认通过**

Run: `cd "D:\little_project\pig" && PYTHONIOENCODING=utf-8 .venv/Scripts/python -m pigpet --selftest`
Expected: 打印含 `menu 拍一拍 -> state: HAPPY -> OK`、`replay 拍一拍 -> state: HAPPY -> OK`、`in HAPPY, pixmap null: False`、拖动行 `-> OK`、最终 `[selftest] PASS`。

- [ ] **Step 4: Commit**

```bash
cd "D:\little_project\pig" && git add pigpet/main.py && git commit -m "test: selftest 改经菜单动作触发 HAPPY + 重播断言"
```

---

### Task 4: 人工验收

- [ ] **Step 1: 运行应用**

Run: `cd "D:\little_project\pig" && .venv/Scripts/python -m pigpet`
Expected: 右键小猪 → 菜单顶部出现「拍一拍」；点击 → happy 动画从头播放，2.5s 自动回 idle；播放中再拍 → 从头重播；单击小猪无动作；拖动小猪仍切 drag.png 且窗口不跳。

- [ ] **Step 2: 推送**

```bash
cd "D:\little_project\pig" && git push
```
