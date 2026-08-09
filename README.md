# 小猪桌宠（LittlePig）

Windows 2D 桌面宠物。V1 范围：透明桌宠窗口 + 动画状态机 + 鼠标交互 + 系统监控 + 设置。不包含 AI 聊天 / 宠物成长 / 语音 / 小游戏（预留扩展接口）。

## 运行

```bat
cd D:\little_project\pig
.venv\Scripts\python -m pigpet
```

依赖：`requirements.txt`（PySide6、psutil）。已用项目内 `.venv` 安装。

自检模式（P2 阶段用于验证状态机/动画，跑完自动退出）：

```bat
.venv\Scripts\python -m pigpet --selftest
```

## 项目结构

```
pigpet/
├─ _qt_bootstrap.py     # PySide6 DLL 加载引导（见下方“已知问题”）
├─ __main__.py          # 入口：python -m pigpet
├─ main.py              # run(): QApplication + 事件循环 + 自检
├─ app.py               # PetApp：装配中枢，唯一的信号接线点
├─ config.py            # APP_NAME、配置路径解析
├─ settings.py          # Settings 数据类 + JSON 原子读写（无 Qt）
├─ assets.py            # AssetSpec + Assets（状态→素材映射）
├─ state_machine.py     # 通用 FSM：IDLE / DRAG / HAPPY + 定时自动转换
├─ player.py            # AnimationPlayer 抽象 + Gif/Static 两个后端
├─ animator.py          # AnimationManager：状态→素材 + 每状态播放速度
├─ interaction.py       # InteractionController（P3）
├─ monitor.py           # SystemMonitor + Cpu/Ram/Gpu 指标（P5）
├─ pet_window.py        # 无边框透明窗口：绘制、鼠标转发、热点区
├─ info_panel.py        # 随桌宠移动的信息面板（P5）
├─ settings_window.py   # 设置对话框（P6）
└─ tray.py              # 系统托盘（P6）
assets/                 # idle.png、happy.gif（512×512 占位素材）
```

**解耦原则**：FSM、拖拽数学、设置、指标等无 Qt 逻辑独立成模块；`app.py` 是唯一知道各模块如何连接的地方。

## 已知问题：Anaconda venv 下 PySide6 加载失败（WinError 127）

### 现象
```text
ImportError: DLL load failed while importing QtCore: 找不到指定的程序
```

### 根因（已用 PE 导入表 + 模块枚举定位）
Anaconda 的 `python313.dll` 在进程启动时**抢先加载**了 `C:\ProgramData\anaconda3\VCRUNTIME140.dll`（14.44.35208）。PySide6 6.11.1 捆绑的是 **35211** 系列运行时（`msvcp140.dll` 等）。Python 3.8+ 导入 `.pyd` 使用**受限 DLL 搜索**（不经过 PATH），受限搜索下捆绑的 `msvcp140.dll` (35211) 无法绑定到进程内已加载的 35208 版 `vcruntime140.dll`，报“找不到指定的程序”。

### 解决方案（本仓库已采用）
暖机（warm-up）：先用非受限搜索手动加载 `QtCore.pyd`（连同整条依赖链），此后 Python 受限 import 命中“已加载模块”即成功。见 `pigpet/_qt_bootstrap.py` 的 `ensure_qt()`，`main.py` 在导入任何 Qt 之前调用它。已验证完整场景（透明置顶窗口 + 事件循环）通过。

### 备选方案（如需彻底绕开，可自行选用）
1. **新建干净 conda 环境**（`conda create -n pig python=3.13`），再用 pip 装 PySide6 —— 从根上避开 Anaconda 基环境的 35208 运行时；
2. **降级 PySide6** 到与系统运行时匹配的版本（未验证）；
3. 安装 Microsoft Visual C++ Redistributable（未验证，因 35208 已在进程内抢先加载，可能仍无效）。

## 分阶段开发状态

| 阶段 | 内容 | 状态 |
|---|---|---|
| P1 | 架构 / 环境搭建（venv、requirements、PySide6 可用） | ✅ |
| P2 | 透明窗口 + 占位角色 + 基础动画（FSM、player、animator） | ✅ |
| P3 | 鼠标点击与拖动（InteractionController） | ✅ |
| P4 | DRAG 状态与被拎起动画接口 | ✅ |
| P5 | SystemMonitor 与信息面板 | ✅ |
| P6 | 设置界面、配置持久化与托盘 | ✅ |

## 验证方式

运行 `python -m pigpet` 人工验收；另提供 `--selftest` 自动化检查（跑完自动退出，
覆盖：窗口可见、单击无动作、HAPPY 动画→自动回、拖动→DRAG→回 IDLE、监控数值、设置生效与持久化）。
