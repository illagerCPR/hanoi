# -*- coding: utf-8 -*-
"""汉诺塔终端界面 v2（Textual 框架版）。

功能与 GUI / tui v1 对齐：挑战 / 自动 / 推断三模式、层数门槛（通关 10 层
解锁更多）、挑战记录。相比 v1 增加：鼠标点击选柱、DataTable 记录表、
按钮化控制条、模态弹窗。

需要第三方依赖 Textual（仅本模块）：pip install textual
其余入口（--gui/--cli/--tui）保持零第三方依赖。

按键：
    左/右 或 A/D   移动柱光标          回车/空格   选源柱、再选目标柱
    1/2/3       直选柱子            S           开始/重置
    P           暂停/继续（自动）   N           执行下一步（推断）
    +/-         调整演示间隔        L           层数选择
    R           挑战记录            H           帮助
    M           切换模式            Q           退出
    鼠标        点击棋盘柱子选柱（挑战模式）

无头自检（CI 用）：HANOI_TUI_V2_SELFTEST=1 python main.py --tui-v2
"""

import asyncio
import os
import sys
import time

from rich.text import Text

import game
import storage
import tui
from tui import (COL_W, CONGRAT_10, CONGRAT_20, GAP, MODE_AUTO, MODE_CHALLENGE,
                 MODE_GUESS, MODE_ORDER, disk_color_code, disk_width)

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, DataTable, Footer, Header, Static

BOARD_W = 3 * COL_W + 2 * GAP          # 80，与 v1 几何一致


# ---------- 棋盘绘制（复用 v1 几何与配色，转 Rich Text） ----------

def board_screen(state, n: int, selected, cursor_peg, challenge: bool):
    """用 v1 的 Screen 画棋盘（origin=0，宽 BOARD_W，高 n+3）。"""
    screen = tui.Screen(BOARD_W, n + 3)
    for peg in range(3):
        cx = peg * (COL_W + GAP) + COL_W // 2
        for r in range(n):
            screen.put(r, cx, "|", fg=245)
        screen.put(n + 1, cx, str(peg), fg=250)
    screen.put(n, 0, "-" * BOARD_W, fg=138)
    for peg, stack in enumerate(state):
        cx = peg * (COL_W + GAP) + COL_W // 2
        for k, disk in enumerate(stack):
            w = disk_width(disk, n)
            col0 = cx - w // 2
            color = disk_color_code(disk, n)
            if selected == peg and k == len(stack) - 1:
                color = 226
            screen.put(n - 1 - k, col0, "#" * w, fg=color)
            text = str(disk)
            screen.put(n - 1 - k, cx - len(text) // 2, text, fg=16, bg=color)
    marker_row = n + 2
    for peg in range(3):
        cx = peg * (COL_W + GAP) + COL_W // 2
        if challenge and selected == peg:
            screen.put(marker_row, cx - 2, "已选", fg=226)
        elif challenge and cursor_peg == peg:
            screen.put(marker_row, cx, "^", fg=220)
    return screen


def screen_to_rich(screen) -> Text:
    """把 v1 Screen 的字符网格转换为 Rich Text（颜色/背景映射为 Rich 样式）。"""
    text = Text()
    for row in screen.grid:
        cur = (None, None)
        for ch, fg, bg in row:
            key = (fg, bg)
            style = None
            if key != cur:
                parts = []
                if fg is not None:
                    parts.append(f"color({fg})")
                if bg is not None:
                    parts.append(f"on color({bg})")
                style = " ".join(parts) or None
                cur = key
            if ch:                       # 全角延续格为空串，跳过
                text.append(ch, style=style)
        text.append("\n")
    return text


# ---------- 弹层 ----------

class NoticeScreen(ModalScreen):
    """通用通知弹层：标题 + 正文 + 继续按钮（胜利/演示完成）。"""

    BINDINGS = [("escape", "close", "关闭"), ("space", "close", "关闭"),
                ("enter", "close", "关闭")]

    def __init__(self, title: str, lines):
        super().__init__()
        self._title = title
        self._lines = list(lines)

    def compose(self) -> ComposeResult:
        with Container(id="notice-box"):
            yield Static(self._title, id="notice-title")
            yield Static("\n".join(self._lines), id="notice-body")
            yield Button("继续 (Esc)", id="notice-close")

    def action_close(self):
        self.dismiss()

    def on_button_pressed(self, event: Button.Pressed):
        self.dismiss()


class HelpScreen(ModalScreen):
    BINDINGS = [("escape", "close", "关闭")]

    def compose(self) -> ComposeResult:
        with Container(id="notice-box"):
            yield Static("帮助", id="notice-title")
            yield Static("\n".join(self.app.help_body()), id="help-body")
            yield Button("关闭 (Esc)", id="notice-close")

    def action_close(self):
        self.dismiss()

    def on_button_pressed(self, event: Button.Pressed):
        self.dismiss()


class RecordsScreen(ModalScreen):
    BINDINGS = [("escape", "close", "关闭")]

    def compose(self) -> ComposeResult:
        with Container(id="notice-box"):
            yield Static("挑战记录", id="notice-title")
            yield DataTable(id="records-table")
            yield Button("关闭 (Esc)", id="notice-close")

    def on_mount(self):
        table = self.query_one("#records-table", DataTable)
        table.add_columns("时间", "层数", "步数", "最优", "用时(秒)")
        records = storage.load_records()
        if not records:
            table.add_row("暂无挑战记录", "", "", "", "")
        for r in records[-15:]:
            table.add_row(str(r["timestamp"]), str(r["level"]), str(r["moves"]),
                          str(r["best"]), str(r["duration_sec"]))

    def action_close(self):
        self.dismiss()

    def on_button_pressed(self, event: Button.Pressed):
        self.dismiss()


class LevelsScreen(ModalScreen):
    """层数选择：列出当前解锁范围内全部层数。"""

    BINDINGS = [("escape", "close", "取消")]

    def __init__(self, choices, current: int):
        super().__init__()
        self._choices = list(choices)
        self._current = current

    def compose(self) -> ComposeResult:
        with Container(id="notice-box"):
            yield Static("选择层数", id="notice-title")
            with Horizontal(id="level-grid"):
                for lv in self._choices:
                    yield Button(str(lv), id=f"level-{lv}",
                                 variant="success" if lv == self._current else "default")
            yield Static("Esc 取消", id="notice-body")

    def action_close(self):
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id and event.button.id.startswith("level-"):
            self.dismiss(int(event.button.id.split("-")[1]))
        else:
            self.dismiss(None)


# ---------- 棋盘控件 ----------

class BoardWidget(Widget):
    """自绘棋盘：render 输出 Rich Text，点击映射到柱子。"""

    def render(self) -> Text:
        app = self.app
        return screen_to_rich(board_screen(
            app.state, app.n, app.selected, app.cursor_peg,
            app.mode == MODE_CHALLENGE))

    def on_click(self, event) -> None:
        app = self.app
        if app.mode != MODE_CHALLENGE:
            return
        centers = [peg * (COL_W + GAP) + COL_W // 2 for peg in range(3)]
        peg = min(range(3), key=lambda i: abs(centers[i] - event.x))
        app.pick_peg(peg)


# ---------- 应用 ----------

class HanoiV2App(App):
    TITLE = "汉诺塔 v2"
    SUB_TITLE = "Textual 版"

    CSS = """
    #banner { height: auto; text-align: center; color: $warning; }
    #board-wrap { height: 1fr; align: center middle; }
    BoardWidget { width: 80; height: auto; }
    #controls { height: auto; align-horizontal: center; }
    #status { height: 1; text-align: center; }
    NoticeScreen { align: center middle; }
    #notice-box { width: 64; height: auto; border: round $primary; padding: 1 2; }
    #notice-title { text-style: bold; color: $warning; }
    #level-grid { height: auto; }
    #records-table { height: auto; max-height: 16; }
    """

    BINDINGS = [
        ("left", "cursor(-1)", "左移"),
        ("right", "cursor(1)", "右移"),
        ("space", "pick_cursor", "选柱"),
        ("enter", "pick_cursor", "选柱"),
        ("1", "peg(0)", "柱1"),
        ("2", "peg(1)", "柱2"),
        ("3", "peg(2)", "柱3"),
        ("s", "start", "开始/重置"),
        ("p", "pause", "暂停"),
        ("n", "step", "下一步"),
        ("+", "interval(0.1)", "间隔+"),
        ("=", "interval(0.1)", "间隔+"),
        ("-", "interval(-0.1)", "间隔-"),
        ("_", "interval(-0.1)", "间隔-"),
        ("l", "levels", "层数"),
        ("r", "records", "记录"),
        ("h", "help", "帮助"),
        ("m", "mode", "切换模式"),
        ("q", "quit", "退出"),
    ]

    def __init__(self, clock=time.monotonic):
        super().__init__()
        self.clock = clock
        self.mode = MODE_CHALLENGE
        self.n = game.MIN_LEVEL
        self.state = game.initial_state(self.n)
        self.moves_done = 0
        self.start_time = clock()
        self.selected = None
        self.cursor_peg = 0
        self.message = ""

        self.plan = []
        self.plan_index = 0
        self.auto_running = False
        self.auto_paused = False
        self.interval = 1.0
        self._last_auto_at = None

        self.passed_10 = storage.passed(10)
        self.passed_20 = storage.passed(20)
        self.last_legal_move = None

    # ---------- 布局 ----------

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Static("", id="banner")
        with Container(id="board-wrap"):
            yield BoardWidget(id="board")
        with Horizontal(id="controls"):
            yield Button("挑战", id="mode-challenge")
            yield Button("自动", id="mode-auto")
            yield Button("推断", id="mode-guess")
            yield Button("开始/重置 (S)", id="btn-start")
            yield Button("暂停 (P)", id="btn-pause", disabled=True)
            yield Button("下一步 (N)", id="btn-step", disabled=True)
            yield Button("记录 (R)", id="btn-records")
            yield Button("帮助 (H)", id="btn-help")
        yield Static("", id="status")
        yield Footer()

    def on_mount(self):
        # 缓存控件引用：定时器回调（含弹层/关闭期间）不得依赖 DOM 查询
        self._banner = self.query_one("#banner", Static)
        self._status = self.query_one("#status", Static)
        self._board = self.query_one("#board", BoardWidget)
        self._btn_pause = self.query_one("#btn-pause", Button)
        self._btn_step = self.query_one("#btn-step", Button)
        self.set_interval(0.25, self._tick)
        self._refresh_ui()

    # ---------- 状态刷新 ----------

    def _refresh_ui(self):
        self._board.refresh()
        self._update_banner()
        self._update_status()
        self._update_buttons()

    def _update_banner(self):
        lines = []
        if self.passed_20:
            lines = ["🏆 " + CONGRAT_20, "🎉 " + CONGRAT_10]
        elif self.passed_10:
            lines = ["🎉 " + CONGRAT_10]
        self._banner.update("\n".join(lines))

    def _status_text(self) -> str:
        best = game.optimal_steps(self.n)
        secs = ("--" if self.start_time is None
                else f"{int(self.clock() - self.start_time)}秒")
        status = f"层数: {self.n}   步数: {self.moves_done} / 最优: {best}   用时: {secs}"
        if self.message:
            status += f"   {self.message}"
        elif self.mode == MODE_AUTO and self.auto_running:
            status += "   [已暂停]" if self.auto_paused else "   [演示中]"
        elif self.mode == MODE_GUESS and self.plan:
            if self.plan_index < len(self.plan):
                src, dst = self.plan[self.plan_index]
                status += f"   下一步: {src} -> {dst}，按 N 执行"
            else:
                status += "   推断演示已完成"
        return status

    def _update_status(self):
        self._status.update(self._status_text())

    def _update_buttons(self):
        self._btn_pause.disabled = not (
            self.mode == MODE_AUTO and self.auto_running)
        self._btn_pause.label = "继续 (P)" if self.auto_paused else "暂停 (P)"
        self._btn_step.disabled = not (
            self.mode == MODE_GUESS and self.plan
            and self.plan_index < len(self.plan))

    def _tick(self):
        if not self.is_running:            # 关闭/挂起期间跳过
            return
        try:
            self._tick_count = getattr(self, "_tick_count", 0) + 1
            if self._tick_count % 8 == 0:  # 周期性强制棋盘全量重绘，防终端残影
                self._board.refresh(layout=True)
            if (self.mode == MODE_AUTO and self.auto_running
                    and not self.auto_paused):
                now = self.clock()
                if self._last_auto_at is None:
                    self._last_auto_at = now
                if now - self._last_auto_at >= self.interval:
                    self._last_auto_at = now
                    self._auto_step()
                    return
            self._update_status()
        except Exception:                  # noqa: BLE001 显示刷新失败不中断应用
            pass

    def _force_repaint(self):
        """弹层关闭等时机强制整屏全量重绘，清除差分刷新遗留的残影。"""
        self.refresh(layout=True)
        self._board.refresh(layout=True)
        self._update_status()

    # ---------- 核心流程（与 tui v1 语义一致） ----------

    def pick_peg(self, peg: int):
        """两段式选柱（对应 GUI 点击语义）。"""
        if self.selected is None:
            if not self.state[peg]:
                self.message = "该柱为空，请选择有盘子的柱子"
            else:
                self.selected = peg
                self.message = ""
            self._refresh_ui()
            return
        if self.selected == peg:
            self.selected = None
            self._refresh_ui()
            return
        src, dst = self.selected, peg
        self.selected = None
        if not game.is_legal(self.state, src, dst):
            self.message = "非法移动：大盘不能压在小盘上"
            self._refresh_ui()
            return
        game.apply_move(self.state, src, dst)
        self.moves_done += 1
        self.message = ""
        self.last_legal_move = (src, dst)
        if game.is_solved(self.state, self.n):
            self._finish_challenge()
        self._refresh_ui()

    def _finish_challenge(self):
        """通关处理：与 gui._on_challenge_finish 语义一致（仅挑战模式调用）。"""
        elapsed = (self.clock() - self.start_time
                   if self.start_time is not None else 0.0)
        self.start_time = None
        best = game.optimal_steps(self.n)
        storage.add_record(self.n, self.moves_done, best, elapsed)
        result = storage.register_clear(self.n)
        first_10 = result["passed_10"] and not self.passed_10
        first_20 = result["passed_20"] and not self.passed_20
        self.passed_10 = self.passed_10 or result["passed_10"]
        self.passed_20 = self.passed_20 or result["passed_20"]
        title = "挑战成功"
        body = [f"层数: {self.n}   步数: {self.moves_done}   理论最优: {best}",
                f"用时: {int(elapsed)}秒", "", "挑战记录已保存！"]
        if first_20:
            title = "🏆 隐藏挑战通关！"
            body = ["🏆 " + CONGRAT_20, "", "🎉 " + CONGRAT_10] + body
        elif first_10:
            title = "🎉 重大突破！"
            body = ["🎉 " + CONGRAT_10, ""] + body
        body += ["", "按 Esc 或点击「继续」返回"]
        self.push_screen(NoticeScreen(title, body), lambda _: self._force_repaint())

    def _set_mode(self, mode: str):
        self.mode = mode
        self.auto_running = False
        self.auto_paused = False
        self.plan = []
        self.plan_index = 0
        self.selected = None
        if self.mode == MODE_CHALLENGE and self.start_time is None:
            self.start_time = self.clock()
        self.message = ""
        self._refresh_ui()

    def _cycle_mode(self):
        nxt = MODE_ORDER[(MODE_ORDER.index(self.mode) + 1) % 3]
        self._set_mode(nxt)

    def _on_start(self):
        self.auto_running = False
        self.auto_paused = False
        self.state = game.initial_state(self.n)
        self.moves_done = 0
        self.selected = None
        self.plan = []
        self.plan_index = 0
        self._last_auto_at = None
        if self.mode == MODE_CHALLENGE:
            self.start_time = self.clock()
            self.message = ""
        elif self.mode == MODE_AUTO:
            self.plan = game.generate_optimal_moves(self.n)
            self.auto_running = True
            self.start_time = None
            self._last_auto_at = self.clock()
            self.message = ""
        else:
            self.plan = game.generate_optimal_moves(self.n)
            self.start_time = None
            self.message = "按 N 执行下一步"
        self._refresh_ui()

    def _guess_step(self):
        if self.mode != MODE_GUESS:
            return
        if not self.plan or self.plan_index >= len(self.plan):
            if self.plan and self.plan_index >= len(self.plan):
                return
            self.message = "先按 S 开始推断演示"
            self._refresh_ui()
            return
        src, dst = self.plan[self.plan_index]
        if game.is_legal(self.state, src, dst):
            game.apply_move(self.state, src, dst)
        self.plan_index += 1
        self.message = ""
        if self.plan_index >= len(self.plan):
            self.push_screen(NoticeScreen("演示完成",
                             ["已完成最优解演示。", "本模式不计入挑战记录。"]),
                             lambda _: self._force_repaint())
        self._refresh_ui()

    def _auto_step(self):
        if self.plan_index >= len(self.plan):
            self.auto_running = False
            self.push_screen(NoticeScreen("演示完成",
                             ["已完成最优解演示。", "本模式不计入挑战记录。"]),
                             lambda _: self._force_repaint())
            self._refresh_ui()
            return
        src, dst = self.plan[self.plan_index]
        game.apply_move(self.state, src, dst)
        self.plan_index += 1
        if self.plan_index >= len(self.plan):
            self.auto_running = False
            self.push_screen(NoticeScreen("演示完成",
                             ["已完成最优解演示。", "本模式不计入挑战记录。"]),
                             lambda _: self._force_repaint())
        self._refresh_ui()

    def _adjust_interval(self, delta: float):
        self.interval = max(0.1, min(5.0, self.interval + delta))
        self.message = f"间隔: {self.interval:.1f}秒"
        self._refresh_ui()

    # ---------- 门槛与文案（隐藏挑战保密约束同 v1） ----------

    def level_choices(self):
        hi = game.HIDDEN_LEVELS if self.passed_10 else game.MAX_VISIBLE_LEVEL
        return list(range(game.MIN_LEVEL, hi + 1))

    def help_body(self):
        hi = game.HIDDEN_LEVELS if self.passed_10 else game.MAX_VISIBLE_LEVEL
        return [
            "左/右 或 A/D：移动柱光标；回车/空格：选源柱、再选目标柱",
            "1/2/3：直选柱子；鼠标：点击棋盘柱子（挑战模式）",
            "S：开始/重置    M：切换模式    L：选择层数",
            "P：暂停/继续（自动模式）    N：执行下一步（推断模式）",
            "+/-：调整自动演示间隔（0.1~5.0 秒）",
            "R：挑战记录    H：帮助    Esc：关闭弹层    Q：退出",
            f"层数范围: {game.MIN_LEVEL}~{hi}",
            "挑战模式通关计入记录；自动/推断模式不计入。",
        ]

    # ---------- Textual 动作 ----------

    def action_cursor(self, delta: int):
        if self.mode == MODE_CHALLENGE:
            self.cursor_peg = max(0, min(2, self.cursor_peg + delta))
            self._refresh_ui()

    def action_pick_cursor(self):
        if self.mode == MODE_CHALLENGE:
            self.pick_peg(self.cursor_peg)

    def action_peg(self, peg: int):
        if self.mode == MODE_CHALLENGE:
            self.pick_peg(peg)

    def action_start(self):
        self._on_start()

    def action_pause(self):
        if self.mode == MODE_AUTO and self.auto_running:
            self.auto_paused = not self.auto_paused
            if not self.auto_paused:
                self._last_auto_at = self.clock()
            self._refresh_ui()

    def action_step(self):
        self._guess_step()

    def action_interval(self, delta: float):
        self._adjust_interval(delta)

    def action_mode(self):
        self._cycle_mode()

    def action_levels(self):
        self.push_screen(LevelsScreen(self.level_choices(), self.n),
                         self._on_level_picked)

    def _on_level_picked(self, level):
        self._force_repaint()
        if level is None:
            return
        self.n = int(level)
        self._on_start()

    def action_records(self):
        self.push_screen(RecordsScreen(), lambda _: self._force_repaint())

    def action_help(self):
        self.push_screen(HelpScreen(), lambda _: self._force_repaint())

    def on_button_pressed(self, event: Button.Pressed):
        bid = event.button.id or ""
        if bid == "mode-challenge":
            self._set_mode(MODE_CHALLENGE)
        elif bid == "mode-auto":
            self._set_mode(MODE_AUTO)
        elif bid == "mode-guess":
            self._set_mode(MODE_GUESS)
        elif bid == "btn-start":
            self._on_start()
        elif bid == "btn-pause":
            self.action_pause()
        elif bid == "btn-step":
            self._guess_step()
        elif bid == "btn-records":
            self.push_screen(RecordsScreen())
        elif bid == "btn-help":
            self.push_screen(HelpScreen())


# ---------- 无头自检 ----------

def _selftest_async() -> bool:
    async def run():
        app = HanoiV2App()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.press("1", "3")
            assert app.last_legal_move == (0, 2), "移动未生效"
            await pilot.press("h")
            assert isinstance(app.screen, HelpScreen), "帮助弹层未打开"
            await pilot.press("escape")
            await pilot.press("r")
            assert isinstance(app.screen, RecordsScreen), "记录弹层未打开"
            await pilot.press("escape")
            await pilot.press("m", "m")
            assert app.mode == MODE_GUESS, "模式切换失败"
            await pilot.press("s")
            assert len(app.plan) == game.optimal_steps(5), "推断计划未生成"
            await pilot.press("n")
            assert app.plan_index == 1, "推断步进失败"
            banner = str(app.query_one("#banner", Static).render())
            assert "解锁" not in banner, "未通关时横幅泄露隐藏信息"
        assert storage.load_records() == [], "自动/推断不应写记录"
        return True

    return asyncio.run(run())


def selftest() -> bool:
    """无头自检：Pilot 跑核心流程并断言（CI 用）。"""
    try:
        sys.stdout.reconfigure(encoding="utf-8")   # Windows 管道下防 charmap 编码错误
    except Exception:
        pass
    try:
        ok = _selftest_async()
    except Exception as exc:            # noqa: BLE001
        print(f"SELFTEST FAILED: {exc!r}")
        return False
    print("SELFTEST OK" if ok else "SELFTEST FAILED")
    return ok


def main():
    if os.environ.get("HANOI_TUI_V2_SELFTEST"):
        raise SystemExit(0 if selftest() else 1)
    HanoiV2App().run()


if __name__ == "__main__":
    main()
