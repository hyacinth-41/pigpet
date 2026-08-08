# 双击 HAPPY + drag.png 丝滑切换 — 设计

日期：2026-08-09 · 项目：LittlePig 小猪桌宠 · 状态：已批准

## 背景与目标

在 V1 基础上完善两项交互：

1. **双击播放 HAPPY**：目前单击（原地按下+松开、未拖动）即触发 HAPPY。改为**双击**触发，单击无动作（仅发扩展信号）。
2. **拖动使用 drag.png**：用户新增 `drag.png` 素材，期望鼠标单击拖动时切换到它，且切换**丝滑**（无尺寸/位置跳变）。

已与用户确认的决策：

- 单击行为：**无动作**（单击仅发 `pet_clicked` 扩展点信号，桌宠保持 IDLE）。
- 丝滑程度：**窗口尺寸恒定 + 素材直接切换**（不做淡入淡出过渡）。
- 素材处理：`darg.png`（拼写错误）**重命名**为 `drag.png`；1024×1024 素材**缩放到窗口显示**，身体居中。

## 现状分析（关键发现）

- `interaction.py:72-73`：release 未拖动分支直接 `state_requested("HAPPY")`，无双击概念。
- `pet_window.py:67-69`：DRAG 状态无条件叠加 70/255 黑色变暗覆盖（占位指示）。
- `pet_window.py:119-123`（`_resize_to_asset`）：窗口尺寸 = **当前素材尺寸** × 缩放。这是尺寸跳变根源——素材 512→1024 时窗口会瞬间放大一倍。
- 素材：`idle.png` 512×512、`happy.gif` 512×512（无尺寸隐患）、`drag.png`（原 `darg.png`）**1024×1024**。
- `app.py`：DRAG 检测的是 `drag.gif`（不存在），故新素材从未被使用，自动回退 idle+变暗。
- 全部素材均为正方形 → 等比绘制无变形约束当前满足。

## 功能一：双击触发 HAPPY

改动集中在 `interaction.py`（UI 无关，可单测）。

### 新增状态

- `_click_timer`：单次 QTimer，作为"双击确认窗"。
- `_pending_click`：是否在等待第二次点击（等待期间桌宠保持 IDLE）。
- 记住首次点击位置，供单击/双击信号使用。

### 双击间隔

取系统值：`QGuiApplication.styleHints().mouseDoubleClickInterval()`（Windows 默认 ≈400ms），随用户系统设置自适应。构造时读取一次。

### 判定逻辑（`on_mouse_release` 未拖动分支）

| 时序 | 行为 |
|---|---|
| 第一次点击（按下+松开，未拖） | 置 `_pending_click`，启动确认窗；**不切 HAPPY**，桌宠保持 IDLE |
| 确认窗内第二次点击 | 停表、清 `_pending_click` → 发 `double_clicked` + `state_requested("HAPPY")` → happy.gif 播放 2.5s 自动回 IDLE |
| 确认窗超时（=单击） | 清 `_pending_click` → 仅发 `pet_clicked`（现有扩展点，无动作） |
| 双击途中移动越过 8px 拖动阈值 | 进入 DRAG 时**取消确认窗**（拖动打断，不算点击），清 `_pending_click` |

### 信号

- 新增 `double_clicked = Signal(QPoint)`。
- 单击继续使用现有 `pet_clicked = Signal(QPoint)`。
- `app.py` 无需新增连接（双击的 HAPPY 走现有 `state_requested`）。

## 功能二：drag.png 丝滑切换

核心：**窗口尺寸基准从"当前素材"改为"固定基准素材"，素材统一缩到窗口绘制**。

### 素材

- `assets/darg.png` → 重命名为 `assets/drag.png`。

### pet_window.py

- 新增 `_base_size: QSize`，首次取当前素材尺寸（启动时即 idle 512×512），之后恒定。
- `set_scale(scale)` 改为按 `_base_size` 计算窗口尺寸（`_resize_to_base`）。
- **切换状态不再触发 resize**（`animator.on_state_changed` 只 `player.load`，不碰窗口尺寸）。
- `paintEvent` 不变：`drawPixmap(0,0,w,h,pix)` 拉伸到窗口。1024 素材等比缩到窗口、居中显示（窗口始终 512×scale 正方形）。
- 变暗条件由 `if state == "DRAG"` 改为显式开关 `set_drag_dim(on: bool)`（构造默认 True，保持现行为兜底）。

### app.py

- 检测 `drag.png`：有 → DRAG 状态映射到它，并 `window.set_drag_dim(False)`（去掉变暗叠加）；无 → 保持现回退（idle + 变暗，稳健兜底）。

### 丝滑原理

idle 与 drag 均为正方形、绘制时居中 → 缩放后中心对齐。切换瞬间窗口不 resize、位置不动，仅画面内容替换，无跳跃。原先"窗口随素材变"是跳 1 倍的原因。

### 性能

1024 素材在拖动中每帧 `drawPixmap` 缩放到窗口（约 256px），单张位图缩放开销 <1ms，无感。首次解码约 20–40ms，仅进 DRAG 一瞬，可接受。V1 不预缓存缩放结果。

## 验证（更新 `--selftest`）

- 单击（单次 press+release）→ 等待超确认窗 → 状态仍 **IDLE**（新断言）。
- 双击（两次 press+release，间隔约 60ms，小于系统双击窗）→ **HAPPY**，2.5s 自动回 IDLE。
- 拖动 → **DRAG**，当前素材为 `drag.png`；窗口尺寸保持 **256×256**（512×scale）不变，不被 1024 素材撑大。
- 回归：单击 HAPPY 旧逻辑被双击替代后，其余（拖动跟手、面板、设置）不受影响。

## 风险

1. 单击后的确认窗期（≈400ms）内桌宠无反应——已确认接受。
2. `drag.png` 构图若主体占满画面，缩到 256px 会比 idle 显小——已确认接受，可用"角色大小"调大。
3. 1024 PNG 首次解码 20–40ms，进 DRAG 一瞬可能轻微迟滞；拖动中无影响。
4. 等比绘制依赖"素材与窗口同纵横比"（当前全为正方形）；将来引入非正方形素材需同步调整绘制方式。

## 改动文件清单

| 文件 | 改动 |
|---|---|
| `assets/darg.png` | 重命名 → `assets/drag.png` |
| `pigpet/interaction.py` | 双击确认窗、`double_clicked` 信号、单击无动作 |
| `pigpet/pet_window.py` | `_base_size` 基准尺寸、`set_drag_dim` 开关、`set_scale` 按基准 |
| `pigpet/app.py` | `drag.png` 检测与映射、`set_drag_dim` 装配 |
| `pigpet/main.py`（selftest） | 双击/单击/尺寸恒定断言 |
