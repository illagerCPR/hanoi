# -*- coding: utf-8 -*-
"""汉诺塔图形界面（tkinter）。

三种模式：
- 挑战模式：玩家手动操作，完成后记录挑战记录。
- 自动模式：按最优解自动演示，步间间隔可调，不计入记录。
- 推断模式：按最优解逐步执行，每一步由玩家确认，不计入记录。
"""

import colorsys
import time
import tkinter as tk
from tkinter import messagebox, ttk

import game
import storage

CANVAS_W = 880
CANVAS_H = 470
GROUND_Y = 420
TOP_Y = 70
PEG_X = (170, 440, 710)
PEG_W = 12
DISK_H = 26

MODE_CHALLENGE = "挑战模式"
MODE_AUTO = "自动模式"
MODE_GUESS = "推断模式"

CONGRAT_10 = "恭喜通关10层汉诺塔！更精彩的挑战已经解锁！"
CONGRAT_20 = "恭喜通关20层汉诺塔！你是当之无愧的汉诺塔大师！"


class HanoiApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("汉诺塔")
        self.geometry(f"{CANVAS_W}x720")
        self.resizable(False, False)

        self.n = game.MIN_LEVEL
        self.mode = MODE_CHALLENGE
        self.state = game.initial_state(self.n)
        self.moves_done = 0
        self.start_time = None
        self.selected = None
        self.animating = False

        self.plan = []
        self.plan_index = 0
        self.auto_running = False
        self.auto_paused = False

        self.passed_10 = storage.passed(10)
        self.passed_20 = storage.passed(20)

        self._build_widgets()
        self._refresh_banner()
        self._refresh_levels()
        self._refresh_mode()
        self._update_status()
        self._redraw()
        self._tick_timer()

    # ---------- 界面构建 ----------

    def _build_widgets(self):
        banner = tk.Frame(self, bg="#fff8e1")
        banner.pack(fill="x")
        inner = tk.Frame(banner, bg="#fff8e1")
        inner.pack(pady=6)
        self.emoji_label = tk.Label(inner, text="", font=("Segoe UI Emoji", 18),
                                    bg="#fff8e1", fg="#d4a017")
        self.emoji_label.pack(side="left", padx=(0, 6))
        self.banner_label = tk.Label(inner, text="", font=("Microsoft YaHei UI", 14, "bold"),
                                     bg="#fff8e1", fg="#b8860b")
        self.banner_label.pack(side="left")
        self.banner2_label = tk.Label(banner, text="", font=("Microsoft YaHei UI", 11),
                                      bg="#fff8e1", fg="#8a6d1a")
        self.banner2_label.pack(pady=(0, 6))

        self.canvas = tk.Canvas(self, width=CANVAS_W, height=CANVAS_H, bg="#f7f4ee",
                                highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self._on_click)

        ctrl = tk.Frame(self, bg="#ececec")
        ctrl.pack(fill="x", side="bottom")
        row1 = tk.Frame(ctrl, bg="#ececec")
        row1.pack(pady=(10, 4))

        tk.Label(row1, text="层数:", bg="#ececec", font=("Microsoft YaHei UI", 10)).pack(side="left")
        self.level_combo = ttk.Combobox(row1, state="readonly", width=4)
        self.level_combo.pack(side="left")
        self.level_combo.bind("<<ComboboxSelected>>", self._on_level_change)

        tk.Label(row1, text="   模式:", bg="#ececec", font=("Microsoft YaHei UI", 10)).pack(side="left")
        self.mode_var = tk.StringVar(value=MODE_CHALLENGE)
        for m in (MODE_CHALLENGE, MODE_AUTO, MODE_GUESS):
            ttk.Radiobutton(row1, text=m, value=m, variable=self.mode_var,
                            command=self._refresh_mode).pack(side="left", padx=(0, 4))

        self.interval_var = tk.StringVar(value="1.0")
        tk.Label(row1, text="   间隔:", bg="#ececec", font=("Microsoft YaHei UI", 10)).pack(side="left")
        self.interval_spin = ttk.Spinbox(row1, from_=0.1, to=5.0, increment=0.1,
                                         width=4, textvariable=self.interval_var)
        self.interval_spin.pack(side="left")
        tk.Label(row1, text="秒", bg="#ececec", font=("Microsoft YaHei UI", 10)).pack(side="left")

        row2 = tk.Frame(ctrl, bg="#ececec")
        row2.pack(pady=(4, 10))
        self.start_btn = ttk.Button(row2, text="开始挑战", command=self._on_start)
        self.start_btn.pack(side="left", padx=4)
        self.pause_btn = ttk.Button(row2, text="暂停", command=self._on_toggle_pause, state="disabled")
        self.pause_btn.pack(side="left", padx=4)
        self.step_btn = ttk.Button(row2, text="执行下一步", command=self._on_step, state="disabled")
        self.step_btn.pack(side="left", padx=4)
        self.restart_btn = ttk.Button(row2, text="重置", command=self._on_reset)
        self.restart_btn.pack(side="left", padx=4)
        self.records_btn = ttk.Button(row2, text="挑战记录", command=self._show_records)
        self.records_btn.pack(side="left", padx=4)

        self.status_label = tk.Label(ctrl, text="", font=("Microsoft YaHei UI", 10),
                                     anchor="w", bg="#ececec", fg="#333")
        self.status_label.pack(fill="x", padx=12, pady=(0, 10))

    # ---------- 状态刷新 ----------

    def _refresh_banner(self):
        if self.passed_20:
            self.emoji_label.config(text="🏆")
            self.banner_label.config(text=CONGRAT_20)
            self.banner2_label.config(text="🎉 " + CONGRAT_10)
        elif self.passed_10:
            self.emoji_label.config(text="🎉")
            self.banner_label.config(text=CONGRAT_10)
            self.banner2_label.config(text="")
        else:
            self.emoji_label.config(text="")
            self.banner_label.config(text="")
            self.banner2_label.config(text="")

    def _refresh_levels(self):
        hi = game.HIDDEN_LEVELS if self.passed_10 else game.MAX_VISIBLE_LEVEL
        levels = [str(i) for i in range(game.MIN_LEVEL, hi + 1)]
        self.level_combo["values"] = levels
        self.level_combo.set(str(self.n))

    def _refresh_mode(self):
        self.mode = self.mode_var.get()
        self.auto_running = False
        self.auto_paused = False
        if self.mode == MODE_AUTO:
            self.start_btn.config(text="开始自动演示", state="normal")
            self.pause_btn.config(state="disabled")
            self.step_btn.config(state="disabled")
            self.interval_spin.config(state="normal")
        elif self.mode == MODE_GUESS:
            self.start_btn.config(text="开始推断演示", state="normal")
            self.pause_btn.config(state="disabled")
            self.step_btn.config(state="disabled")
            self.interval_spin.config(state="disabled")
        else:
            self.start_btn.config(text="开始挑战", state="normal")
            self.pause_btn.config(state="disabled")
            self.step_btn.config(state="disabled")
            self.interval_spin.config(state="disabled")
        self._update_status()

    def _interval(self):
        try:
            return max(0.05, min(5.0, float(self.interval_var.get())))
        except ValueError:
            return 1.0

    def _update_status(self):
        best = game.optimal_steps(self.n)
        msg = ""
        if self.mode == MODE_GUESS and self.plan:
            if self.plan_index < len(self.plan):
                src, dst = self.plan[self.plan_index]
                msg = f"下一步: {src} → {dst}，请点击【执行下一步】"
            else:
                msg = "推断演示已完成"
        if self.mode == MODE_CHALLENGE:
            msg = "点击柱子选择源柱，再点击目标柱移动盘子"
        secs = self._elapsed_text()
        self.status_label.config(
            text=f"层数: {self.n}   步数: {self.moves_done} / 最优: {best}   用时: {secs}   {msg}")

    def _elapsed_text(self):
        if self.start_time is None:
            return "--"
        return f"{int(time.time() - self.start_time)}秒"

    def _tick_timer(self):
        self._update_status()
        self.after(250, self._tick_timer)

    # ---------- 绘制 ----------

    def _disk_width(self, disk):
        span = 200
        factor = span / max(self.n - 1, 1)
        return 50 + (disk - 1) * factor

    def _disk_color(self, disk):
        h = ((disk - 1) / max(self.n, 1)) * 0.82
        r, g, b = colorsys.hsv_to_rgb(h, 0.72, 0.92)
        return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))

    def _draw_static(self, skip_disk=None):
        self.canvas.delete("all")
        self.canvas.create_rectangle(40, GROUND_Y, CANVAS_W - 40, GROUND_Y + 16,
                                     fill="#8d6e63", outline="")
        for i, x in enumerate(PEG_X):
            self.canvas.create_rectangle(x - PEG_W // 2, TOP_Y, x + PEG_W // 2, GROUND_Y,
                                         fill="#a1887f", outline="")
            self.canvas.create_text(x, GROUND_Y + 34, text=str(i),
                                    font=("Consolas", 14, "bold"), fill="#666")
        for peg in (0, 1, 2):
            for k, disk in enumerate(self.state[peg]):
                if disk == skip_disk:
                    continue
                w = self._disk_width(disk)
                x0 = PEG_X[peg] - w / 2
                y0 = GROUND_Y - (k + 1) * DISK_H
                self.canvas.create_rectangle(x0, y0, x0 + w, y0 + DISK_H - 2,
                                             fill=self._disk_color(disk), outline="#4a4a4a")
                self.canvas.create_text(PEG_X[peg], y0 + DISK_H // 2 - 1, text=str(disk),
                                        font=("Consolas", 9, "bold"), fill="#ffffff")
        if self.selected is not None:
            x = PEG_X[self.selected]
            self.canvas.create_rectangle(x - 36, TOP_Y - 30, x + 36, TOP_Y - 8,
                                         fill="#ffd54f", outline="#f9a825")
            self.canvas.create_text(x, TOP_Y - 19, text="已选",
                                    font=("Microsoft YaHei UI", 9, "bold"), fill="#5d4037")

    def _redraw(self):
        self._draw_static()

    # ---------- 动画 ----------

    def _animate_move(self, src, dst, on_done):
        self.animating = True
        disk = self.state[src][-1]
        w = self._disk_width(disk)
        x = PEG_X[src] - w / 2
        y = GROUND_Y - len(self.state[src]) * DISK_H
        y_up = TOP_Y + 24
        y_land = GROUND_Y - len(self.state[dst]) * DISK_H
        phase = "up"

        def draw_floating():
            self._draw_static(skip_disk=disk)
            self.canvas.create_rectangle(x, y, x + w, y + DISK_H - 2,
                                         fill=self._disk_color(disk), outline="#4a4a4a")
            self.canvas.create_text(x + w / 2, y + DISK_H // 2 - 1, text=str(disk),
                                    font=("Consolas", 9, "bold"), fill="#ffffff")

        def step():
            nonlocal x, y, phase
            if phase == "up":
                if y > y_up + 6:
                    y = max(y - 10, y_up)
                else:
                    phase = "across"
            elif phase == "across":
                tx = PEG_X[dst] - w / 2
                if abs(tx - x) > 10:
                    x += 12 if tx > x else -12
                else:
                    x = tx
                    phase = "down"
            else:
                if y < y_land - 6:
                    y = min(y + 10, y_land)
                else:
                    game.apply_move(self.state, src, dst)
                    self.animating = False
                    self._redraw()
                    on_done()
                    return
            draw_floating()
            self.after(16, step)

        draw_floating()
        self.after(16, step)

    # ---------- 交互 ----------

    def _on_click(self, event):
        if self.mode != MODE_CHALLENGE or self.animating:
            return
        peg = min(range(3), key=lambda i: abs(PEG_X[i] - event.x))
        if abs(PEG_X[peg] - event.x) > 80 or event.y > GROUND_Y - 6:
            return
        if self.selected is None:
            if not self.state[peg]:
                self.status_label.config(text="该柱为空，请选择有盘子的柱子")
                return
            self.selected = peg
            self._redraw()
        elif self.selected == peg:
            self.selected = None
            self._redraw()
        else:
            src, dst = self.selected, peg
            self.selected = None
            if not game.is_legal(self.state, src, dst):
                self._redraw()
                self.status_label.config(text="非法移动：大盘不能压在小盘上")
                return
            self._animate_move(src, dst, self._on_challenge_step_done)

    def _on_challenge_step_done(self):
        self.moves_done += 1
        self._update_status()
        if game.is_solved(self.state, self.n):
            self._on_challenge_finish()

    def _on_challenge_finish(self):
        elapsed = time.time() - self.start_time
        self.start_time = None
        best = game.optimal_steps(self.n)
        storage.add_record(self.n, self.moves_done, best, elapsed)
        result = storage.register_clear(self.n)
        first_10 = result["passed_10"] and not self.passed_10
        first_20 = result["passed_20"] and not self.passed_20
        self.passed_10 = self.passed_10 or result["passed_10"]
        self.passed_20 = self.passed_20 or result["passed_20"]
        self._refresh_banner()
        self._refresh_levels()
        text = (f"挑战成功！层数: {self.n}，步数: {self.moves_done}，"
                f"理论最优: {best}，用时: {int(elapsed)}秒\n\n挑战记录已保存！")
        if first_20:
            messagebox.showinfo("🏆 隐藏挑战通关！", "🏆 " + CONGRAT_20 + "\n\n" + CONGRAT_10)
        elif first_10:
            messagebox.showinfo("🎉 重大突破！", "🎉 " + CONGRAT_10)
        else:
            messagebox.showinfo("挑战成功！", text)

    def _on_level_change(self, _event=None):
        try:
            n = int(self.level_combo.get())
        except ValueError:
            return
        self.n = n
        self._on_reset()

    def _on_reset(self):
        self.auto_running = False
        self.auto_paused = False
        self.state = game.initial_state(self.n)
        self.moves_done = 0
        self.selected = None
        self.plan = []
        self.plan_index = 0
        self.start_time = None
        if self.mode == MODE_CHALLENGE:
            self.start_time = time.time()
        self._refresh_mode()
        self._update_status()
        self._redraw()

    def _on_start(self):
        if self.mode == MODE_CHALLENGE:
            self._on_reset()
            return
        self.auto_running = True
        self.auto_paused = False
        self.state = game.initial_state(self.n)
        self.moves_done = 0
        self.selected = None
        self.plan = game.generate_optimal_moves(self.n)
        self.plan_index = 0
        self._redraw()
        if self.mode == MODE_AUTO:
            self.pause_btn.config(state="normal")
            self.step_btn.config(state="disabled")
            self.start_btn.config(state="disabled")
            self.after(int(self._interval() * 1000), self._auto_next)
        else:
            self.step_btn.config(state="normal")
            self.start_btn.config(state="disabled")
        self._update_status()

    def _auto_next(self):
        if not self.auto_running or self.auto_paused:
            return
        if self.plan_index >= len(self.plan):
            self._on_demo_finish()
            return
        src, dst = self.plan[self.plan_index]
        self._animate_move(src, dst, self._on_auto_step_done)

    def _on_auto_step_done(self):
        self.plan_index += 1
        self._update_status()
        self.after(int(self._interval() * 1000), self._auto_next)

    def _on_toggle_pause(self):
        if self.auto_running:
            self.auto_paused = not self.auto_paused
            self.pause_btn.config(text="继续" if self.auto_paused else "暂停")

    def _on_step(self):
        if self.mode != MODE_GUESS or self.animating or self.plan_index >= len(self.plan):
            return
        src, dst = self.plan[self.plan_index]
        self.step_btn.config(state="disabled")
        self._animate_move(src, dst, self._on_guess_step_done)

    def _on_guess_step_done(self):
        self.plan_index += 1
        if self.plan_index >= len(self.plan):
            self.step_btn.config(state="disabled")
            self.start_btn.config(state="normal")
            self._on_demo_finish()
        else:
            self.step_btn.config(state="normal")
            self._update_status()

    def _on_demo_finish(self):
        self.auto_running = False
        self.start_btn.config(state="normal")
        self.pause_btn.config(state="disabled")
        self._update_status()
        messagebox.showinfo("演示完成", "已完成最优解演示。本模式不计入挑战记录。")

    def _show_records(self):
        win = tk.Toplevel(self)
        win.title("挑战记录")
        win.geometry("640x300")
        records = storage.load_records()
        columns = ("time", "level", "moves", "best", "duration")
        tree = ttk.Treeview(win, columns=columns, show="headings")
        tree.heading("time", text="时间")
        tree.heading("level", text="层数")
        tree.heading("moves", text="步数")
        tree.heading("best", text="理论最优")
        tree.heading("duration", text="用时(秒)")
        tree.column("time", width=170, anchor="center")
        tree.column("level", width=70, anchor="center")
        tree.column("moves", width=90, anchor="center")
        tree.column("best", width=110, anchor="center")
        tree.column("duration", width=100, anchor="center")
        tree.pack(fill="both", expand=True, padx=6, pady=6)
        if not records:
            tree.insert("", "end", values=("暂无挑战记录", "", "", "", ""))
        for r in records:
            tree.insert("", "end", values=(r["timestamp"], r["level"], r["moves"],
                                           r["best"], r["duration_sec"]))


def main():
    app = HanoiApp()
    app.mainloop()
