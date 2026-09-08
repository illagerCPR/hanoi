# -*- coding: utf-8 -*-
"""汉诺塔终端界面（TUI）。

功能与 GUI 模式对齐：挑战 / 自动 / 推断三模式、层数门槛（通关 10 层解锁更多）、
挑战记录。纯标准库 ANSI 渲染，POSIX 与 Windows（VT 序列）均支持。

按键：
    左/右 或 A/D   移动柱光标
    回车/空格     选定源柱，再选目标柱（两段式）
    1/2/3         直选柱子（先源柱后目标柱）
    S             开始/重置
    P             暂停/继续（自动模式）
    N             执行下一步（推断模式）
    +/-           调整自动演示间隔（0.1~5.0 秒）
    L             层数选择
    R             挑战记录
    H             帮助
    M             切换模式
    Esc           取消选择/关闭弹层
    Q             退出

无头自检（CI 用）：HANOI_TUI_SELFTEST=1 python main.py --tui
"""

import colorsys
import os
import shutil
import sys
import time
import unicodedata

import game
import storage

MODE_CHALLENGE = "挑战模式"
MODE_AUTO = "自动模式"
MODE_GUESS = "推断模式"
MODE_ORDER = (MODE_CHALLENGE, MODE_AUTO, MODE_GUESS)

CONGRAT_10 = "恭喜通关10层汉诺塔！更精彩的挑战已经解锁！"
CONGRAT_20 = "恭喜通关20层汉诺塔！你是当之无愧的汉诺塔大师！"

COL_W = 24                      # 每柱列宽（字符）
GAP = 4                         # 柱间距（字符）
MIN_COLS = 3 * COL_W + 2 * GAP  # 80
MIN_ROWS_HEAD = 12              # 棋盘之外需要的行数（横幅/模式/底座/状态/提示）
ENTER_KEYS = ("\r", "\n", " ")

ANSI_ALT_ENTER = "\x1b[?1049h\x1b[?25l"
ANSI_ALT_LEAVE = "\x1b[0m\x1b[?25h\x1b[?1049l"


# ---------- 纯函数（可测） ----------

def display_width(text: str) -> int:
    """按终端显示宽度计算（全角字符占 2 列）。"""
    return sum(2 if unicodedata.east_asian_width(ch) in ("F", "W") else 1 for ch in text)


def disk_width(disk: int, n: int) -> int:
    """盘子宽度（字符列），最小 8，最大 COL_W - 2。"""
    span = COL_W - 2 - 8
    return 8 + (disk - 1) * span // max(n - 1, 1)


def disk_color_code(disk: int, n: int) -> int:
    """盘子颜色：HSV 色相映射到 xterm-256 调色板（对应 GUI _disk_color）。"""
    h = ((disk - 1) / max(n, 1)) * 0.82
    r, g, b = colorsys.hsv_to_rgb(h, 0.72, 0.92)
    return 16 + 36 * int(r * 5 + 0.5) + 6 * int(g * 5 + 0.5) + int(b * 5 + 0.5)


def _pad(text: str, width: int) -> str:
    """按显示宽度左对齐补空格（中文对齐用）。"""
    return text + " " * max(0, width - display_width(text))


class Screen:
    """字符帧缓冲：每格记录 (字符, 前景, 背景)，可无头渲染，便于测试。"""

    def __init__(self, cols: int, rows: int):
        self.cols = cols
        self.rows = rows
        self.clear()

    def clear(self):
        self.grid = [[(" ", None, None) for _ in range(self.cols)]
                     for _ in range(self.rows)]

    def put(self, row: int, col: int, text: str, fg=None, bg=None):
        if row < 0 or row >= self.rows:
            return
        c = col
        for ch in text:
            w = 2 if unicodedata.east_asian_width(ch) in ("F", "W") else 1
            if 0 <= c < self.cols:
                self.grid[row][c] = (ch, fg, bg)
                for k in range(1, w):        # 全角字符占据的后续格
                    if c + k < self.cols:
                        self.grid[row][c + k] = ("", fg, bg)
            c += w

    def put_center(self, row: int, text: str, fg=None, bg=None):
        col = max(0, (self.cols - display_width(text)) // 2)
        self.put(row, col, text, fg, bg)

    def render(self, color: bool = True) -> list:
        lines = []
        for row in self.grid:
            if not color:
                lines.append("".join(cell[0] for cell in row))
                continue
            parts = []
            cur = (None, None)
            for ch, fg, bg in row:
                key = (fg, bg)
                if key != cur:
                    codes = ["0"]
                    if fg is not None:
                        codes.append(f"38;5;{fg}")
                    if bg is not None:
                        codes.append(f"48;5;{bg}")
                    parts.append("\x1b[" + ";".join(codes) + "m")
                    cur = key
                parts.append(ch)
            parts.append("\x1b[0m")
            lines.append("".join(parts))
        return lines


# ---------- 终端后端 ----------

class PosixTerminal:
    """POSIX 终端：termios cbreak + select 超时读取。"""

    supports_color = True

    def __init__(self):
        import select
        import termios
        import tty
        self._select = select.select
        self._termios = termios
        self._tty = tty
        self.fd = sys.stdin.fileno()
        self._old = None

    def enter(self):
        self._old = self._termios.tcgetattr(self.fd)
        self._tty.setcbreak(self.fd)
        self.write(ANSI_ALT_ENTER)

    def leave(self):
        self.write(ANSI_ALT_LEAVE)
        if self._old is not None:
            self._termios.tcsetattr(self.fd, self._termios.TCSADRAIN, self._old)
            self._old = None

    def size(self):
        size = shutil.get_terminal_size((MIN_COLS, 24))
        return size.columns, size.lines

    def read_key(self, timeout: float):
        r, _, _ = self._select([sys.stdin], [], [], timeout)
        if not r:
            return None
        ch = sys.stdin.read(1)
        if ch != "\x1b":
            return ch
        r2, _, _ = self._select([sys.stdin], [], [], 0.02)
        if not r2:
            return "ESC"
        if sys.stdin.read(1) != "[":
            return "ESC"
        r3, _, _ = self._select([sys.stdin], [], [], 0.02)
        if not r3:
            return "ESC"
        return {"D": "LEFT", "C": "RIGHT", "A": "UP", "B": "DOWN"}.get(
            sys.stdin.read(1), "ESC")

    def write(self, s: str):
        sys.stdout.write(s)
        sys.stdout.flush()


class WindowsTerminal:
    """Windows 终端：msvcrt 读键 + ctypes 启用 VT（ANSI）支持。"""

    def __init__(self):
        import ctypes
        import msvcrt
        self._ctypes = ctypes
        self._msvcrt = msvcrt
        self.supports_color = self._enable_vt()

    def _enable_vt(self) -> bool:
        try:
            k32 = self._ctypes.windll.kernel32
            handle = k32.GetStdHandle(-11)
            mode = self._ctypes.c_uint32()
            if k32.GetConsoleMode(handle, self._ctypes.byref(mode)):
                k32.SetConsoleMode(handle, mode.value | 0x0004)
                return True
        except Exception:
            pass
        return False

    def enter(self):
        self.write(ANSI_ALT_ENTER)

    def leave(self):
        self.write(ANSI_ALT_LEAVE)

    def size(self):
        size = shutil.get_terminal_size((MIN_COLS, 24))
        return size.columns, size.lines

    def read_key(self, timeout: float):
        deadline = time.monotonic() + max(0.0, timeout)
        while True:
            if self._msvcrt.kbhit():
                ch = self._msvcrt.getwch()
                if ch in ("\x00", "\xe0"):
                    ch2 = self._msvcrt.getwch()
                    return {"K": "LEFT", "M": "RIGHT", "H": "UP",
                            "P": "DOWN"}.get(ch2, "ESC")
                if ch == "\x1b":
                    return "ESC"
                return ch
            if time.monotonic() >= deadline:
                return None
            time.sleep(0.01)

    def write(self, s: str):
        sys.stdout.write(s)
        sys.stdout.flush()


class FakeTerminal:
    """测试/自检用假终端：注入按键序列与固定尺寸，不接触真实终端。"""

    supports_color = True

    def __init__(self, keys=(), cols=100, rows=40):
        self.keys = list(keys)
        self.cols = cols
        self.rows = rows
        self.written = []

    def enter(self):
        pass

    def leave(self):
        pass

    def size(self):
        return self.cols, self.rows

    def read_key(self, timeout: float):
        return self.keys.pop(0) if self.keys else "q"

    def write(self, s: str):
        self.written.append(s)


# ---------- 应用 ----------

class TuiApp:
    """TUI 状态机：与 gui.HanoiApp 功能对齐，终端 I/O 全部经 term 注入。"""

    def __init__(self, term, clock=time.monotonic):
        self.term = term
        self.clock = clock
        self.color = getattr(term, "supports_color", True)

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

        self.overlay = None
        self._overlay_title = ""
        self._overlay_body = []
        self.level_index = 0

        self.running = True
        self._prev_lines = None
        self._prev_size = None
        self.screen = None
        self.last_legal_move = None

    # ---------- 按键处理 ----------

    def handle_key(self, key):
        if key is None:
            return
        if isinstance(key, str) and len(key) == 1 and key.isalpha():
            key = key.lower()
        if key == "q":
            self.running = False
            return
        if key == "ESC":
            if self.overlay:
                self.overlay = None
            elif self.selected is not None:
                self.selected = None
                self.message = ""
            return
        if self.overlay == "levels":
            self._handle_levels_key(key)
            return
        if self.overlay:
            self.overlay = None
            return
        if key == "h":
            self.overlay = "help"
            return
        if key == "r":
            self.overlay = "records"
            return
        if key == "l":
            self._open_levels()
            return
        if key == "m":
            self._cycle_mode()
            return
        if key == "s":
            self._on_start()
            return
        if key in ("+", "="):
            self._adjust_interval(0.1)
            return
        if key in ("-", "_"):
            self._adjust_interval(-0.1)
            return
        if key == "p" and self.mode == MODE_AUTO and self.auto_running:
            self.auto_paused = not self.auto_paused
            if not self.auto_paused:
                self._last_auto_at = self.clock()
            return
        if key == "n" and self.mode == MODE_GUESS:
            self._guess_step()
            return
        if self.mode == MODE_CHALLENGE:
            if key in ("LEFT", "a"):
                self.cursor_peg = max(0, self.cursor_peg - 1)
                return
            if key in ("RIGHT", "d"):
                self.cursor_peg = min(2, self.cursor_peg + 1)
                return
            if key in ENTER_KEYS:
                self._pick(self.cursor_peg)
                return
            if key in ("1", "2", "3"):
                self._pick(int(key) - 1)
                return
        # 其余按键忽略

    def _pick(self, peg):
        """两段式选柱（对应 GUI 的点击语义）。"""
        if self.selected is None:
            if not self.state[peg]:
                self.message = "该柱为空，请选择有盘子的柱子"
            else:
                self.selected = peg
                self.message = ""
            return
        if self.selected == peg:
            self.selected = None
            return
        src, dst = self.selected, peg
        self.selected = None
        if not game.is_legal(self.state, src, dst):
            self.message = "非法移动：大盘不能压在小盘上"
            return
        game.apply_move(self.state, src, dst)
        self.moves_done += 1
        self.message = ""
        self.last_legal_move = (src, dst)
        if game.is_solved(self.state, self.n):
            self._finish_challenge()

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
        self._show_overlay("win", title, body + ["", "按任意键继续"])

    def _cycle_mode(self):
        self.mode = MODE_ORDER[(MODE_ORDER.index(self.mode) + 1) % 3]
        self.auto_running = False
        self.auto_paused = False
        self.plan = []
        self.plan_index = 0
        self.selected = None
        if self.mode == MODE_CHALLENGE and self.start_time is None:
            self.start_time = self.clock()
        self.message = ""
        self.overlay = None

    def _on_start(self):
        self.auto_running = False
        self.auto_paused = False
        self.state = game.initial_state(self.n)
        self.moves_done = 0
        self.selected = None
        self.plan = []
        self.plan_index = 0
        self._last_auto_at = None
        self.overlay = None
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

    def _guess_step(self):
        if self.mode != MODE_GUESS:
            return
        if not self.plan or self.plan_index >= len(self.plan):
            if self.plan and self.plan_index >= len(self.plan):
                return
            self.message = "先按 S 开始推断演示"
            return
        src, dst = self.plan[self.plan_index]
        if game.is_legal(self.state, src, dst):
            game.apply_move(self.state, src, dst)
        self.plan_index += 1
        self.message = ""
        if self.plan_index >= len(self.plan):
            self._show_overlay("demo", "演示完成",
                               ["已完成最优解演示。", "本模式不计入挑战记录。",
                                "", "按任意键继续"])

    def _auto_step(self):
        if self.plan_index >= len(self.plan):
            self.auto_running = False
            self._show_overlay("demo", "演示完成",
                               ["已完成最优解演示。", "本模式不计入挑战记录。",
                                "", "按任意键继续"])
            return
        src, dst = self.plan[self.plan_index]
        game.apply_move(self.state, src, dst)
        self.plan_index += 1
        if self.plan_index >= len(self.plan):
            self.auto_running = False
            self._show_overlay("demo", "演示完成",
                               ["已完成最优解演示。", "本模式不计入挑战记录。",
                                "", "按任意键继续"])

    def _adjust_interval(self, delta):
        self.interval = max(0.1, min(5.0, self.interval + delta))
        self.message = f"间隔: {self.interval:.1f}秒"

    # ---------- 弹层 ----------

    def _show_overlay(self, kind, title, body):
        self.overlay = kind
        self._overlay_title = title
        self._overlay_body = body

    def _level_choices(self):
        hi = game.HIDDEN_LEVELS if self.passed_10 else game.MAX_VISIBLE_LEVEL
        return list(range(game.MIN_LEVEL, hi + 1))

    def _open_levels(self):
        choices = self._level_choices()
        self.level_index = choices.index(self.n) if self.n in choices else 0
        self.overlay = "levels"

    def _handle_levels_key(self, key):
        choices = self._level_choices()
        if key == "UP":
            self.level_index = max(0, self.level_index - 1)
            return
        if key == "DOWN":
            self.level_index = min(len(choices) - 1, self.level_index + 1)
            return
        if key in ENTER_KEYS:
            self.n = choices[self.level_index]
            self.overlay = None
            self._on_start()
            return
        self.overlay = None

    def _help_body(self):
        hi = game.HIDDEN_LEVELS if self.passed_10 else game.MAX_VISIBLE_LEVEL
        return [
            "左/右 或 A/D：移动柱光标；回车/空格：选源柱、再选目标柱",
            "1/2/3：直选柱子（先源柱后目标柱）",
            "S：开始/重置    M：切换模式    L：选择层数",
            "P：暂停/继续（自动模式）    N：执行下一步（推断模式）",
            "+/-：调整自动演示间隔（0.1~5.0 秒）",
            "R：挑战记录    H：帮助    Esc：取消/关闭弹层    Q：退出",
            f"层数范围: {game.MIN_LEVEL}~{hi}",
            "挑战模式通关计入记录；自动/推断模式不计入。",
        ]

    def _records_body(self):
        records = storage.load_records()
        if not records:
            return ["暂无挑战记录"]
        lines = [_pad("时间", 20) + _pad("层数", 6) + _pad("步数", 7)
                 + _pad("最优", 7) + "用时(秒)"]
        for r in records[-15:]:
            lines.append(_pad(str(r["timestamp"]), 20)
                         + str(r["level"]).rjust(6)
                         + str(r["moves"]).rjust(7)
                         + str(r["best"]).rjust(7)
                         + str(r["duration_sec"]))
        return lines

    def _levels_body(self):
        lines = ["上/下 选择，回车确认，Esc 取消"]
        for i, lv in enumerate(self._level_choices()):
            mark = "> " if i == self.level_index else "  "
            lines.append(f"{mark}{lv}")
        return lines

    # ---------- 绘制 ----------

    def _draw(self) -> Screen:
        cols, rows = self.term.size()
        screen = Screen(cols, rows)
        self.screen = screen
        if cols < MIN_COLS or rows < self.n + MIN_ROWS_HEAD:
            screen.put_center(rows // 2,
                              f"终端太小：请至少使用 {MIN_COLS} 列 × "
                              f"{self.n + MIN_ROWS_HEAD} 行")
            screen.put_center(rows // 2 + 1, "拉大窗口后画面会自动恢复")
            return screen

        row = 0
        if self.passed_20:
            screen.put_center(row, "🏆 " + CONGRAT_20, fg=214)
            row += 1
            screen.put_center(row, "🎉 " + CONGRAT_10, fg=220)
            row += 1
        elif self.passed_10:
            screen.put_center(row, "🎉 " + CONGRAT_10, fg=220)
            row += 1

        mode_line = f"模式: {self.mode}   层数: {self.n}"
        if self.mode == MODE_AUTO:
            mode_line += f"   间隔: {self.interval:.1f}秒"
        screen.put_center(row, mode_line, fg=250)
        row += 1

        row = self._draw_board(screen, row)

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
        screen.put_center(row, status, fg=252)
        row += 1
        screen.put_center(row, "S 开始/重置  M 模式  L 层数  R 记录  H 帮助  Q 退出",
                          fg=244)

        if self.overlay:
            self._draw_overlay(screen)
        return screen

    def _draw_board(self, screen: Screen, row: int) -> int:
        n = self.n
        total_w = 3 * COL_W + 2 * GAP
        origin = max(0, (screen.cols - total_w) // 2)
        base_row = row + n
        for peg in range(3):
            cx = origin + peg * (COL_W + GAP) + COL_W // 2
            for r in range(n):
                screen.put(row + r, cx, "|", fg=245)
            screen.put(base_row + 1, cx, str(peg), fg=250)
        screen.put(base_row, origin, "-" * total_w, fg=138)

        for peg, stack in enumerate(self.state):
            cx = origin + peg * (COL_W + GAP) + COL_W // 2
            for k, disk in enumerate(stack):
                w = disk_width(disk, n)
                r = base_row - 1 - k
                col0 = cx - w // 2
                color = disk_color_code(disk, n)
                if self.selected == peg and k == len(stack) - 1:
                    color = 226
                screen.put(r, col0, "#" * w, fg=color)
                text = str(disk)
                screen.put(r, cx - len(text) // 2, text, fg=16, bg=color)

        marker_row = base_row + 2
        for peg in range(3):
            cx = origin + peg * (COL_W + GAP) + COL_W // 2
            if self.mode == MODE_CHALLENGE and self.selected == peg:
                screen.put(marker_row, cx - 2, "已选", fg=226)
            elif self.mode == MODE_CHALLENGE and self.cursor_peg == peg:
                screen.put(marker_row, cx, "^", fg=220)
        return marker_row + 1

    def _draw_overlay(self, screen: Screen):
        if self.overlay == "records":
            title, body = "挑战记录", self._records_body()
        elif self.overlay == "help":
            title, body = "帮助", self._help_body()
        elif self.overlay == "levels":
            title, body = "选择层数", self._levels_body()
        else:
            title, body = self._overlay_title, self._overlay_body
        box_w = max([display_width(t) for t in [title] + body] + [10]) + 6
        box_h = len(body) + 4
        top = max(0, (screen.rows - box_h) // 2)
        left = max(0, (screen.cols - box_w) // 2)
        screen.put(top, left, "+" + "-" * (box_w - 2) + "+", fg=250)
        for i in range(1, box_h - 1):
            screen.put(top + i, left, "|", fg=250)
            screen.put(top + i, left + box_w - 1, "|", fg=250)
        screen.put(top + box_h - 1, left, "+" + "-" * (box_w - 2) + "+", fg=250)
        screen.put(top + 1, left + max(1, (box_w - display_width(title)) // 2),
                   title, fg=220)
        for i, line in enumerate(body):
            screen.put(top + 2 + i, left + 2, line, fg=252)

    # ---------- 输出与主循环 ----------

    def flush(self, force: bool = False):
        cols, rows = self.term.size()
        if force or self._prev_size != (cols, rows) or self._prev_lines is None:
            self._prev_lines = None
            self.term.write("\x1b[2J")
        screen = self._draw()
        lines = screen.render(color=self.color)
        prev = self._prev_lines or []
        out = []
        for i, line in enumerate(lines):
            if i < len(prev) and prev[i] == line:
                continue
            out.append(f"\x1b[{i + 1};1H{line}\x1b[0m\x1b[K")
        for i in range(len(lines), len(prev)):
            out.append(f"\x1b[{i + 1};1H\x1b[0m\x1b[K")
        self.term.write("".join(out))
        self._prev_lines = lines
        self._prev_size = (cols, rows)

    def on_timeout(self):
        """无按键超时：驱动自动演示步进并刷新计时。"""
        if (self.mode == MODE_AUTO and self.auto_running
                and not self.auto_paused):
            now = self.clock()
            if self._last_auto_at is None:
                self._last_auto_at = now
            if now - self._last_auto_at >= self.interval:
                self._last_auto_at = now
                self._auto_step()


def run_app(app: TuiApp):
    app.term.enter()
    try:
        last_size = app.term.size()
        app.flush(force=True)
        while app.running:
            if (app.mode == MODE_AUTO and app.auto_running
                    and not app.auto_paused):
                timeout = max(0.05, app.interval)
            else:
                timeout = 0.25
            key = app.term.read_key(timeout)
            size = app.term.size()
            if size != last_size:
                last_size = size
                app.flush(force=True)
                continue
            if key is None:
                app.on_timeout()
            else:
                app.handle_key(key)
            app.flush()
    finally:
        app.term.leave()


# ---------- 入口 ----------

def selftest() -> bool:
    """无头自检：假终端跑核心流程，输出最终画面与检查结果（CI 用）。"""
    try:
        sys.stdout.reconfigure(encoding="utf-8")   # Windows 管道下防 charmap 编码错误
    except Exception:
        pass
    keys = ["1", "3", "h", " ", "r", " ", "l", "\r", "m", "m", "s", "n", "q"]
    term = FakeTerminal(keys=keys, cols=100, rows=40)
    app = TuiApp(term, clock=FakeClockForTest())
    run_app(app)
    frame = "\n".join(app.screen.render(color=False))
    checks = [
        ("移动生效", app.last_legal_move == (0, 2)),
        ("推断模式", app.mode == MODE_GUESS),
        ("推断已步进", app.plan_index == 1),
        ("未写记录", storage.load_records() == []),
        ("画面含模式", "推断模式" in frame),
        ("画面含层数", "层数: 5" in frame),
    ]
    print(frame)
    ok = True
    for name, passed in checks:
        print(f"[{'OK' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    print("SELFTEST OK" if ok else "SELFTEST FAILED")
    return ok


class FakeClockForTest:
    def __init__(self, start=1000.0):
        self.t = start

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


def main():
    if os.environ.get("HANOI_TUI_SELFTEST"):
        raise SystemExit(0 if selftest() else 1)
    term = WindowsTerminal() if os.name == "nt" else PosixTerminal()
    app = TuiApp(term)
    try:
        run_app(app)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
