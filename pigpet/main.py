"""应用入口：QApplication + 事件循环 + 可选自检。

必须先调用 _qt_bootstrap.ensure_qt()（解决 Anaconda venv 下 PySide6
DLL 加载问题），再导入任何 Qt 模块——因此这里所有 Qt 导入都放在函数内。
"""

from __future__ import annotations

import sys
from typing import Optional

from ._qt_bootstrap import ensure_qt


def _run_selftest(app, pet_app) -> None:
    """P3 自动化验证：
    1. 窗口可见、初始 IDLE；
    2. 单击（按住期间轻微漂移 10px）→ 无动作（状态保持 IDLE）；
    3. HAPPY 动画路径：触发右键菜单「拍一拍」动作 → pat_requested → force HAPPY
       → happy.gif 经 QMovie 多帧加载（非静态单帧兜底），2500ms 自动回 IDLE；
       HAPPY 中重拍仍为 HAPPY；
    4. 拖动（按下 + 移动 80px 超阈值）→ DRAG 素材，窗口尺寸恒定，松手 → IDLE。
    漂移用例回归：真实点按的按住期抖动不得被误判为拖动。
    随后退出。
    """
    from PySide6.QtCore import QPoint, QTimer

    from .app import HAPPY_AUTO_BACK_MS as HAPPY_BACK_MS

    it = pet_app.interaction
    monitor_rows: list[str] = []
    checks: dict[str, bool] = {}  # single_ok / drag_ok 等逐段断言
    print("[selftest] window visible:", pet_app.window.isVisible())
    # 默认缩放 0.5：素材 512 → 窗口应 256×256
    win_size = pet_app.window.size()
    size_ok = win_size.width() == 256 and win_size.height() == 256
    print(f"[selftest] window size: {win_size.width()}x{win_size.height()} (expect 256x256) -> {'OK' if size_ok else 'FAIL'}")
    print("[selftest] initial state:", pet_app.fsm.current)

    def step_single_click() -> None:
        pos = QPoint(800, 600)
        # 按住期间轻微漂移 10px(真实点按普遍存在),不得被误判为拖动
        it.on_mouse_press(pos, QPoint(0, 0))
        it.on_mouse_move(pos + QPoint(10, 0))
        it.on_mouse_release(pos + QPoint(10, 0))
        print("[selftest] single click sent; checking no-op...")
        QTimer.singleShot(100, step_single_check)  # 单击无确认窗,短暂等待后判定

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

    def step_happy_check() -> None:
        checks["happy_ok"] = checks["happy_ok"] and not pet_app.player.current_pixmap().isNull()
        # 动画断言（回归）：happy.gif 须走 QMovie 后端且为多帧动画——
        # 历史根因就是它被 StaticPlayer 按单帧静态加载、画面看似停在 idle。
        movie = getattr(pet_app.player, "_movie", None)
        frames_ok = movie is not None and movie.frameCount() > 1
        checks["happy_ok"] = checks["happy_ok"] and frames_ok
        frame_desc = f"{movie.frameCount()} 帧" if frames_ok else "非动画"
        print(
            f"[selftest] in HAPPY: pixmap null={pet_app.player.current_pixmap().isNull()}, "
            f"动画={frame_desc} -> {'OK' if frames_ok else 'FAIL'}"
        )
        QTimer.singleShot(HAPPY_BACK_MS + 200, step_drag)

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

    def step_monitor() -> None:
        # 监控首拍已发出，面板行应已由 "--" 占位变成真实值（GPU 可为“不可用”）
        monitor_rows[:] = pet_app.panel.texts()
        print("[selftest] panel rows:", monitor_rows)
        QTimer.singleShot(300, step_settings)

    def step_settings() -> None:
        from .config import resolve_config_path
        from .settings import Settings

        # 模拟设置窗口：关掉 GPU、改间隔、取消置顶、放大到 0.8
        s = Settings(
            show_cpu=True,
            show_ram=True,
            show_gpu=False,
            show_panel=True,
            always_on_top=False,
            monitor_interval_ms=1500,
            pet_scale=0.8,
        )
        # 设置窗口表单自身
        win = pet_app.settings_window
        win.load(s)
        cur = win.current_settings()
        ok_window = cur.show_gpu is False and cur.monitor_interval_ms == 1500 and cur.pet_scale == 0.8

        pet_app._apply_settings(s)  # 模拟点“应用”
        ok_rows = len(pet_app.panel.texts()) == 2  # GPU 行已移除
        # 缩放生效：窗口应变 512×0.8 = 410（约）
        win_w = pet_app.window.size().width()
        ok_scale = abs(win_w - int(512 * 0.8)) <= 1
        cfg = resolve_config_path()
        ok_cfg = cfg.exists()
        reloaded = Settings.load(cfg)
        ok_persist = (
            reloaded.monitor_interval_ms == 1500
            and reloaded.show_gpu is False
            and reloaded.always_on_top is False
            and abs(reloaded.pet_scale - 0.8) < 1e-6
        )
        print(f"[selftest] settings: window_form={ok_window}, rows_after={len(pet_app.panel.texts())}, win_w={win_w}, scale_ok={ok_scale}, config_exists={ok_cfg}, reloaded_ok={ok_persist}")

        ok_monitor = bool(monitor_rows) and not any("--" in t for t in monitor_rows)
        ok = (
            size_ok
            and checks.get("single_ok", False)
            and checks.get("happy_ok", False)
            and checks.get("drag_ok", False)
            and ok_monitor
            and ok_window
            and ok_rows
            and ok_scale
            and ok_cfg
            and ok_persist
        )
        print("[selftest]", "PASS" if ok else "FAIL")
        app.quit()

    QTimer.singleShot(400, step_single_click)


def run(argv: Optional[list[str]] = None, selftest: bool = False) -> int:
    ensure_qt()

    if selftest:
        # 自检用临时配置目录，每次清空，保证结果确定（不读用户已有配置）
        import os
        import tempfile

        cfg_dir = os.path.join(tempfile.gettempdir(), "pig_selftest")
        os.environ["PIG_CONFIG_DIR"] = cfg_dir
        try:
            os.remove(os.path.join(cfg_dir, "config.json"))
        except OSError:
            pass

    from PySide6.QtWidgets import QApplication

    from .app import PetApp

    app = QApplication(argv if argv is not None else sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 关闭对话框不应退出宠物

    pet_app = PetApp(app)

    if selftest:
        _run_selftest(app, pet_app)

    return app.exec()


if __name__ == "__main__":
    _selftest = "--selftest" in sys.argv
    if _selftest:
        sys.argv = [a for a in sys.argv if a != "--selftest"]
    sys.exit(run(selftest=_selftest))
