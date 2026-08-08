# 双击 HAPPY + drag.png 丝滑切换 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 单击无动作、双击触发 HAPPY;拖动时切换到 drag.png 且切换丝滑(窗口尺寸恒定、素材统一缩到窗口绘制)。

**Architecture:** 交互层 `interaction.py` 用"双击确认窗"(系统双击间隔,单次 QTimer)区分单击/双击,单击仅发扩展信号、双击发 HAPPY;视图层 `pet_window.py` 把窗口基准尺寸固定为首次素材(512×512)×缩放,状态切换不再触发 resize,素材一律由 paintEvent 等比缩到窗口;`app.py` 检测 `drag.png` 存在则启用该素材并关闭变暗兜底。

**Tech Stack:** PySide6 6.11.1 / psutil 7.2.2 / Python 3.13.5(项目 venv `.venv`)。无 pytest,验证用 offscreen 断言脚本 + `--selftest` 全量。

## Global Constraints

- **必须**先 `from ._qt_bootstrap import ensure_qt; ensure_qt()` 再 `import` 任何 Qt 模块(Anaconda venv 的 WinError 127 陷阱)。
- 所有命令在 bash 下运行,Python 用 `.venv/Scripts/python`。
- 素材与窗口同为正方形(512×512 基准),等比绘制无变形;若引入非正方形素材需另改绘制。
- 双击间隔取 `QGuiApplication.styleHints().mouseDoubleClickInterval()`(Windows 默认 ≈400ms),不硬编码。
- `DRAG_THRESHOLD_PX = 8`(拖动阈值)保持不变。
- 代码注释与文案用中文,保持现有风格。

---

### Task 1: 重命名素材 darg.png → drag.png

**Files:**
- Rename: `assets/darg.png` → `assets/drag.png`(git mv 保留历史)

**Interfaces:**
- Produces: `assets/drag.png` 存在(1024×1024)。后续 Task 5 依赖该文件名。

- [ ] **Step 1: 重命名**

```bash
cd "D:\little_project\pig" && git mv assets/darg.png assets/drag.png
```

- [ ] **Step 2: 验证文件已改名且内容仍在**

```bash
cd "D:\little_project\pig" && ls assets/ && git status --short
```
Expected: `assets/drag.png` 存在;`git status` 显示 renamed。

- [ ] **Step 3: Commit**

```bash
git commit -m "assets: darg.png 拼写修正重命名为 drag.png"
```

---

### Task 2: interaction.py 双击判定

**Files:**
- Modify: `pigpet/interaction.py`

**Interfaces:**
- Consumes: 无(独立逻辑)。
- Produces: `double_clicked = Signal(QPoint)`;单击不再直接发 `HAPPY`,仅在确认窗超时时发 `pet_clicked`;双击发 `double_clicked` + `state_requested("HAPPY")`。Task 3 的 selftest 与 Task 6 依赖此行为。

- [ ] **Step 1: 写失败测试(offscreen 单测脚本)**

```python
# 临时文件 /tmp/test_dclick.py
from pigpet._qt_bootstrap import ensure_qt
ensure_qt()
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint
app = QApplication([])
from pigpet.interaction import InteractionController

# 用例A: 双击 → 一次 HAPPY + 一次 double_clicked,无 pet_clicked
it = InteractionController()
hits = {"happy": [], "double": [], "single": []}
it.state_requested.connect(lambda s: hits["happy"].append(s) if s == "HAPPY" else None)
it.double_clicked.connect(lambda p: hits["double"].append(p))
it.pet_clicked.connect(lambda p: hits["single"].append(p))

p = QPoint(100, 100)
it.on_mouse_press(p, QPoint(0, 0)); it.on_mouse_release(p)   # 第一次点击
assert hits["happy"] == [], "第一次点击不应触发 HAPPY"
it.on_mouse_press(p, QPoint(0, 0)); it.on_mouse_release(p)   # 第二次点击
assert hits["happy"] == ["HAPPY"], hits
assert len(hits["double"]) == 1
assert hits["single"] == []
print("PASS: double-click")

# 用例B: 第一次点击后拖动 → 取消双击,不触发 HAPPY
it2 = InteractionController()
hits2 = {"happy": [], "double": [], "single": []}
it2.state_requested.connect(lambda s: hits2["happy"].append(s) if s == "HAPPY" else None)
it2.double_clicked.connect(lambda p: hits2["double"].append(p))
it2.pet_clicked.connect(lambda p: hits2["single"].append(p))
it2.on_mouse_press(QPoint(100, 100), QPoint(0, 0))
it2.on_mouse_release(QPoint(100, 100))          # 第一次点击,pending
assert it2._pending_click is True
it2.on_mouse_press(QPoint(200, 100), QPoint(0, 0))
it2.on_mouse_move(QPoint(250, 100))             # 超 8px → DRAG,打断
assert it2._pending_click is False, "拖动应取消待确认单击"
it2.on_mouse_release(QPoint(250, 100))
assert hits2["happy"] == [], "拖动不应触发 HAPPY"
print("PASS: drag breaks pending click")
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `cd "D:\little_project\pig" && QT_QPA_PLATFORM=offscreen .venv/Scripts/python /tmp/test_dclick.py`
Expected: FAIL——`double_clicked` 信号不存在(`AttributeError`),或第一次点击即触发 HAPPY(旧行为)。

- [ ] **Step 3: 实现(修改 interaction.py)**

顶部 import 增加 `QGuiApplication`:

```python
from PySide6.QtGui import QCursor, QGuiApplication
```

信号区新增一行:

```python
    double_clicked = Signal(QPoint)  # 双击(确认窗内两次点击);单击走 pet_clicked
```

`__init__` 末尾新增(放在 `self._timer.timeout.connect(...)` 之后):

```python
        self._pending_click = False            # 双击确认窗内等待第二次点击
        self._click_pos = QPoint()             # 第一次点击位置(供信号使用)
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.setInterval(
            QGuiApplication.styleHints().mouseDoubleClickInterval()
        )
        self._click_timer.timeout.connect(self._on_click_timeout)
```

`on_mouse_move` 进入 DRAG 分支处(在 `self._dragging = True` 之后、发信号之前)插入取消逻辑:

```python
        self._pending_click = False
        self._click_timer.stop()
```

`on_mouse_release` 的"未拖动"分支(现第 71-73 行 `else: ... emit("HAPPY")`)整体替换为:

```python
        else:
            if self._pending_click:
                # 确认窗内第二次点击 → 双击
                self._pending_click = False
                self._click_timer.stop()
                self.double_clicked.emit(global_pos)
                self.state_requested.emit("HAPPY")
            else:
                # 第一次点击:进入确认窗,等待第二次;超时即单击(无动作)
                self._pending_click = True
                self._click_pos = global_pos
                self._click_timer.start()
```

新增方法(放在 `_poll_cursor` 之前):

```python
    def _on_click_timeout(self) -> None:
        """双击确认窗超时 = 单击:无动作,仅发扩展信号。"""
        self._pending_click = False
        self.pet_clicked.emit(self._click_pos)
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `cd "D:\little_project\pig" && QT_QPA_PLATFORM=offscreen .venv/Scripts/python /tmp/test_dclick.py`
Expected: `PASS: double-click`、`PASS: drag breaks pending click`,退出码 0。

- [ ] **Step 5: Commit**

```bash
cd "D:\little_project\pig" && git add pigpet/interaction.py && git commit -m "feat: 双击触发 HAPPY,单击无动作(确认窗判定)"
```

---

### Task 3: 更新 selftest 的单击/双击段

**Files:**
- Modify: `pigpet/main.py`(selftest 内 `step_click` → 单击+双击两步)

**Interfaces:**
- Consumes: Task 2 的双击行为(`double_clicked`/`state_requested("HAPPY")`)。
- Produces: 全量 selftest 在双击语义下通过;`single_ok`(单击无动作)、`drag_ok`(拖动素材/尺寸)两个外层断言变量供最终 `ok` 使用。

- [ ] **Step 1: 修改 selftest 断言变量(外层)**

`_run_selftest` 内 `monitor_rows: list[str] = []` 之后新增一个共享断言字典(供各 step 写入、最终 `ok` 汇总读取):

```python
    checks: dict[str, bool] = {}  # single_ok / drag_ok 等逐段断言
```

- [ ] **Step 2: 替换 `step_click` 为单击+双击流程**

把现 `step_click`(第 35-40 行)整体替换为:

```python
    def step_single_click() -> None:
        pos = QPoint(800, 600)
        it.on_mouse_press(pos, QPoint(0, 0))   # 单击:按下+松开
        it.on_mouse_release(pos)
        print("[selftest] single click sent; waiting for double-click window...")
        QTimer.singleShot(600, step_single_check)  # > 系统双击窗(≈400ms)

    def step_single_check() -> None:
        checks["single_ok"] = pet_app.fsm.current == "IDLE"
        print(f"[selftest] after single click -> state: {pet_app.fsm.current} (expect IDLE) -> {'OK' if checks['single_ok'] else 'FAIL'}")
        pos = QPoint(800, 600)
        it.on_mouse_press(pos, QPoint(0, 0))   # 双击第一步
        it.on_mouse_release(pos)
        QTimer.singleShot(60, step_dclick_second)  # 60ms 内第二次

    def step_dclick_second() -> None:
        pos = QPoint(800, 600)
        it.on_mouse_press(pos, QPoint(0, 0))   # 双击第二步 → HAPPY
        it.on_mouse_release(pos)
        print("[selftest] after double click -> state:", pet_app.fsm.current)
        QTimer.singleShot(400, step_happy_check)
```

注意:`_run_selftest` 是嵌套函数,step 内对普通 bool 直接赋值需 `nonlocal`,所以统一写入 Step 1 的 `checks` 字典(避免 nonlocal 麻烦,写法与现 `monitor_rows` 一致)。

- [ ] **Step 3: 修改启动入口**

现第 120 行 `QTimer.singleShot(400, step_click)` → `QTimer.singleShot(400, step_single_click)`。

- [ ] **Step 4: 更新最终 `ok` 汇总**

现第 116 行 `ok = size_ok and ok_monitor and ...` → 并入单击断言:

```python
        ok = size_ok and checks.get("single_ok", False) and ok_monitor and ok_window and ok_rows and ok_scale and ok_cfg and ok_persist
```

- [ ] **Step 5: 运行全量 selftest,确认通过**

Run: `cd "D:\little_project\pig" && PYTHONIOENCODING=utf-8 .venv/Scripts/python -m pigpet --selftest`
Expected: 打印含 `after single click -> state: IDLE -> OK`、`after double click -> state: HAPPY`、最终 `[selftest] PASS`。

- [ ] **Step 6: Commit**

```bash
cd "D:\little_project\pig" && git add pigpet/main.py && git commit -m "test: selftest 改双击语义(单击无动作断言)"
```

---

### Task 4: pet_window.py 基准尺寸 + set_drag_dim

**Files:**
- Modify: `pigpet/pet_window.py`

**Interfaces:**
- Consumes: `AnimationPlayer.current_pixmap()`(首次取 512×512)。
- Produces: `set_scale(scale)` 按固定基准 `_base_size` 定窗口尺寸,状态切换不再 resize;`set_drag_dim(on: bool)` 显式控制 DRAG 变暗。Task 5 依赖 `set_drag_dim`。

- [ ] **Step 1: 写失败测试(offscreen 单测)**

```python
# 临时文件 /tmp/test_win.py
from pigpet._qt_bootstrap import ensure_qt
ensure_qt()
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSize
app = QApplication([])
from pigpet.assets import AssetSpec, DEFAULT_ASSET_DIR
from pigpet.player import StaticPlayer
from pigpet.pet_window import PetWindow

player = StaticPlayer()
player.load(AssetSpec(str(DEFAULT_ASSET_DIR / "idle.png")))  # 512×512
win = PetWindow(player)
win.set_scale(0.5)
assert win.size() == QSize(256, 256), win.size()

# 切到 1024 的 drag.png,窗口尺寸必须保持 256(不 resize)
player.load(AssetSpec(str(DEFAULT_ASSET_DIR / "drag.png")))
assert win.size() == QSize(256, 256), f"切素材后窗口不应变: {win.size()}"
assert player.current_pixmap().width() == 1024  # 素材本身确实是 1024
win.set_scale(1.0)
assert win.size() == QSize(512, 512), win.size()  # 再放大到 1.0 仍按基准

win.set_drag_dim(False)   # 仅验证 API 存在、不抛异常
win.set_drag_dim(True)
print("PASS")
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `cd "D:\little_project\pig" && QT_QPA_PLATFORM=offscreen .venv/Scripts/python /tmp/test_win.py`
Expected: FAIL——当前实现切到 1024 素材后窗口变 512(`win.size() != QSize(256,256)` 断言触发)。

- [ ] **Step 3: 实现(修改 pet_window.py)**

`__init__` 内 `self._scale = 1.0` 之后新增两个成员:

```python
        self._base_size: Optional[QSize] = None  # 窗口基准尺寸(首次素材),恒定
        self._drag_dim = True                    # 无专门素材时 DRAG 变暗兜底
```

把 `set_scale` + `_resize_to_asset`(第 114-125 行)整体替换为:

```python
    def set_scale(self, scale: float) -> None:
        """窗口尺寸 = 基准素材尺寸 × 缩放;paintEvent 把素材等比缩到窗口。

        基准尺寸取首次加载的素材(启动即 idle 512×512),之后恒定,
        因此切换到 1024 的 drag.png 也不会让窗口放大、切换不跳。
        """
        self._scale = scale
        self._resize_to_base()

    def _resize_to_base(self) -> None:
        if self._base_size is None:
            self._base_size = self._player.current_pixmap().size()
        self.setFixedSize(
            QSize(
                int(self._base_size.width() * self._scale),
                int(self._base_size.height() * self._scale),
            )
        )
        # 面板锚定依赖窗口尺寸,尺寸变化后通知一次
        self.pos_changed.emit(self.pos())
```

新增 `set_drag_dim`,放在 `set_state` 附近:

```python
    def set_drag_dim(self, on: bool) -> None:
        """DRAG 状态是否叠加变暗。有专门 drag 素材时应关闭(on=False)。"""
        self._drag_dim = on
        self.update()
```

`paintEvent` 的变暗条件(第 67 行)改为:

```python
        if self._state == "DRAG" and self._drag_dim:
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `cd "D:\little_project\pig" && QT_QPA_PLATFORM=offscreen .venv/Scripts/python /tmp/test_win.py`
Expected: `PASS`,退出码 0。

- [ ] **Step 5: Commit**

```bash
cd "D:\little_project\pig" && git add pigpet/pet_window.py && git commit -m "feat: 窗口基准尺寸恒定 + set_drag_dim 变暗开关(切素材不再 resize)"
```

---

### Task 5: app.py 接入 drag.png

**Files:**
- Modify: `pigpet/app.py`

**Interfaces:**
- Consumes: Task 4 的 `set_drag_dim`;`assets/drag.png`(Task 1)。
- Produces: DRAG 状态使用 drag.png,且关闭变暗叠加;无 drag.png 时保持回退(idle+变暗)。

- [ ] **Step 1: 修改素材检测与映射**

`app.py` 第 50 行 `drag_asset = "drag.gif" if ... else None` → 改为:

```python
        drag_asset = "drag.png" if (DEFAULT_ASSET_DIR / "drag.png").is_file() else None
```

- [ ] **Step 2: 装配 set_drag_dim**

`self.window = PetWindow(self.player)` 之后、`self.window.set_scale(...)` 之前插入:

```python
        # 有专门 drag 素材就不用变暗兜底;没有则回退 idle+变暗
        self.window.set_drag_dim(drag_asset is None)
```

- [ ] **Step 3: 冒烟验证(素材切换生效)**

Run: `cd "D:\little_project\pig" && PYTHONIOENCODING=utf-8 .venv/Scripts/python -m pigpet --selftest`
Expected: 此时 selftest 拖动段仍按旧断言(状态/尺寸),应通过;最终 `[selftest] PASS`。确认无异常、窗口正常创建。

- [ ] **Step 4: Commit**

```bash
cd "D:\little_project\pig" && git add pigpet/app.py && git commit -m "feat: 拖动使用 drag.png 素材,有素材时关闭变暗兜底"
```

---

### Task 6: selftest 拖动段增强 + 全量回归

**Files:**
- Modify: `pigpet/main.py`(selftest 的 `step_drag`)

**Interfaces:**
- Consumes: Task 4 的基准尺寸行为、Task 5 的 drag.png 映射。
- Produces: 拖动段断言"素材已切为 1024 的 drag + 窗口尺寸保持 256",`drag_ok` 并入最终 `ok`。

- [ ] **Step 1: 增强 `step_drag` 断言**

把现 `step_drag`(第 46-70 行)整体替换为:

```python
    def step_drag() -> None:
        print("[selftest] auto-return -> state:", pet_app.fsm.current)
        grab = QPoint(100, 60)
        start = QPoint(900, 600)
        moved = QPoint(980, 660)  # 位移 80px,超阈值
        it.on_mouse_press(start, grab)
        offset_ok = it._offset == grab  # 偏移必须是本地抓取点
        it.on_mouse_move(moved)   # 触发 DRAG + 跟随
        during = pet_app.fsm.current
        window_drag_state = pet_app.window.current_state  # DRAG 视觉指示
        pix = pet_app.player.current_pixmap()
        drag_asset_ok = not pix.isNull() and pix.width() == 1024  # 已是 drag.png
        win_size_drag = pet_app.window.size()
        drag_size_ok = win_size_drag.width() == 256 and win_size_drag.height() == 256  # 不被 1024 撑大
        it.on_mouse_release(moved)
        after = pet_app.fsm.current
        checks["drag_ok"] = (
            during == "DRAG"
            and window_drag_state == "DRAG"
            and after == "IDLE"
            and offset_ok
            and drag_asset_ok
            and drag_size_ok
        )
        print(
            f"[selftest] drag: during={during}, window_state={window_drag_state}, "
            f"after={after}, offset_is_grab={offset_ok}, asset={pix.width()}px, "
            f"win_size={win_size_drag.width()}x{win_size_drag.height()} "
            f"-> {'OK' if checks['drag_ok'] else 'FAIL'}"
        )
        QTimer.singleShot(300, step_monitor)
```

- [ ] **Step 2: 把 `drag_ok` 并入最终 `ok`**

现最终 `ok` 汇总行 → 加入拖动断言:

```python
        ok = (
            size_ok
            and checks.get("single_ok", False)
            and checks.get("drag_ok", False)
            and ok_monitor
            and ok_window
            and ok_rows
            and ok_scale
            and ok_cfg
            and ok_persist
        )
```

- [ ] **Step 3: 运行全量 selftest**

Run: `cd "D:\little_project\pig" && PYTHONIOENCODING=utf-8 .venv/Scripts/python -m pigpet --selftest`
Expected: 拖动行打印 `asset=1024px, win_size=256x256` 且 `OK`;最终 `[selftest] PASS`。

- [ ] **Step 4: 人工验收(用户)**

Run: `cd "D:\little_project\pig" && .venv/Scripts/python -m pigpet`
Expected: 单击小猪无反应;双击播放 happy 动画并自动回 idle;按住拖动时立即换成 drag.png 且窗口不跳、贴手;松开回 idle。

- [ ] **Step 5: Commit**

```bash
cd "D:\little_project\pig" && git add pigpet/main.py && git commit -m "test: 拖动段断言 drag 素材 + 窗口尺寸恒定"
```

- [ ] **Step 6: 推送**

```bash
cd "D:\little_project\pig" && git push
```
