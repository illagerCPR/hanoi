# -*- coding: utf-8 -*-
"""汉诺塔命令行模式（仅挑战模式）。

命令设计详见 CLI.md。输出保持稳定可解析，错误信息以“错误: ”开头。
"""

import sys
import time

import game
import storage

PEG_ALIAS = {"0": 0, "1": 1, "2": 2, "a": 0, "b": 1, "c": 2,
             "A": 0, "B": 1, "C": 2}


class CliGame:
    def __init__(self):
        self.n = None
        self.state = None
        self.moves_done = 0
        self.start_time = None

    # ---------- 主循环 ----------

    def run(self):
        print("汉诺塔 - 命令行挑战模式")
        print("输入 help 查看命令说明")
        while True:
            try:
                line = input("> ")
            except (EOFError, KeyboardInterrupt):
                print()
                print("再见！")
                return
            line = line.strip()
            if line.startswith("\ufeff"):
                line = line[1:].strip()
            if not line:
                continue
            parts = line.split()
            cmd = parts[0].lower()
            args = parts[1:]
            if not self._dispatch(cmd, args):
                return

    def _dispatch(self, cmd, args):
        if cmd in ("quit", "exit", "q"):
            return False
        if cmd == "help":
            self._help()
        elif cmd == "start":
            self._start(args)
        elif cmd == "move":
            self._move(args)
        elif cmd == "hint":
            self._hint()
        elif cmd == "best":
            self._best()
        elif cmd == "status":
            self._status()
        elif cmd == "record":
            self._record()
        else:
            print(f"错误: 未知命令 '{cmd}'，输入 help 查看命令说明")
        return True

    # ---------- 辅助 ----------

    def _require_game(self):
        if self.n is None:
            print("错误: 尚未开始挑战，请先使用 start <n> 开始")
            return False
        return True

    def _level_limit(self):
        return game.HIDDEN_LEVELS if storage.passed(10) else game.MAX_VISIBLE_LEVEL

    def _show_board(self):
        print(game.format_state(self.state, self.moves_done,
                                game.optimal_steps(self.n)))

    def _elapsed_text(self):
        if self.start_time is None:
            return "--"
        return f"{int(time.time() - self.start_time)}秒"

    # ---------- 命令实现 ----------

    def _help(self):
        limit = self._level_limit()
        print("可用命令:")
        print(f"  start <n>         开始新的挑战，n 为层数（{game.MIN_LEVEL}~{limit}）")
        print("  move <a> <b>      移动盘子，a/b 为柱子编号 0/1/2（或 A/B/C）")
        print("  hint              提示下一步建议移动")
        print("  best              显示当前层数的理论最优步数")
        print("  status            查看当前棋盘状态")
        print("  record            查看挑战记录")
        print("  help              显示本帮助")
        print("  quit              退出程序")

    def _start(self, args):
        if len(args) != 1:
            print("错误: 用法: start <n>")
            return
        try:
            n = int(args[0])
        except ValueError:
            print("错误: 层数必须是整数")
            return
        limit = self._level_limit()
        if not (game.MIN_LEVEL <= n <= limit):
            print(f"错误: 层数必须在 {game.MIN_LEVEL} 到 {limit} 之间")
            return
        self.n = n
        self.state = game.initial_state(n)
        self.moves_done = 0
        self.start_time = time.time()
        best = game.optimal_steps(n)
        print(f"开始挑战：{n} 层（理论最优步数: {best}）")
        self._show_board()

    def _move(self, args):
        if not self._require_game():
            return
        if len(args) != 2:
            print("错误: 用法: move <a> <b>")
            return
        src = PEG_ALIAS.get(args[0])
        dst = PEG_ALIAS.get(args[1])
        if src is None or dst is None:
            print("错误: 柱子编号必须是 0/1/2 或 A/B/C")
            return
        if src == dst:
            print("错误: 源柱与目标柱相同")
            return
        if not self.state[src]:
            print("错误: 源柱上没有盘子")
            return
        if self.state[dst] and self.state[dst][-1] < self.state[src][-1]:
            print("错误: 非法移动（大盘不能放在小盘上）")
            return
        game.apply_move(self.state, src, dst)
        self.moves_done += 1
        self._show_board()
        if game.is_solved(self.state, self.n):
            self._finish()

    def _hint(self):
        if not self._require_game():
            return
        if game.is_solved(self.state, self.n):
            print("提示: 已经完成挑战！")
            return
        plan = plan_from_state(self.state, self.n)
        if not plan:
            print("提示: 没有可行的下一步")
            return
        src, dst = plan[0]
        print(f"建议下一步: {src} → {dst}")

    def _best(self):
        if not self._require_game():
            return
        print(f"理论最优步数: {game.optimal_steps(self.n)}")

    def _status(self):
        if not self._require_game():
            return
        self._show_board()
        print(f"用时: {self._elapsed_text()}")

    def _record(self):
        records = storage.load_records()
        if not records:
            print("暂无挑战记录")
            return
        print("时间                  层数  步数   最优   用时(秒)")
        for r in records:
            print(f"{r['timestamp']}  {r['level']:>3}  {r['moves']:>4}  "
                  f"{r['best']:>4}  {r['duration_sec']:>6.1f}")

    def _finish(self):
        elapsed = time.time() - self.start_time
        self.start_time = None
        best = game.optimal_steps(self.n)
        storage.add_record(self.n, self.moves_done, best, elapsed)
        result = storage.register_clear(self.n)
        print("恭喜！你完成了汉诺塔挑战！")
        print(f"层数: {self.n}，步数: {self.moves_done}，理论最优: {best}，"
              f"用时: {int(elapsed)}秒")
        print("挑战记录已保存。")
        if result["passed_20"]:
            print("🏆 恭喜通关最高层挑战！你是当之无愧的汉诺塔大师！")
        elif result["passed_10"]:
            print("🎉 恭喜通关10层！已解锁更高层数的挑战！")
        self.state = game.initial_state(self.n)
        self.n = None
        self.moves_done = 0


def plan_from_state(state, n, target=game.TARGET):
    """从当前（任意合法）状态出发，生成移动到目标柱的可行序列。

    玩家走过弯路后仍可用：将更大的盘先归位。不保证全局步数最优，
    但保证每一步合法且最终完成。
    """
    work = [list(p) for p in state]
    plan = []

    def move(src, dst):
        plan.append((src, dst))
        game.apply_move(work, src, dst)

    def solve(k, tgt):
        if k <= 0:
            return
        src = game.find_disk(work, k)
        if src == tgt:
            solve(k - 1, tgt)
            return
        aux = 3 - src - tgt
        solve(k - 1, aux)
        move(src, tgt)
        solve(k - 1, tgt)

    solve(n, target)
    return plan


def run():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    cli = CliGame()
    cli.run()


if __name__ == "__main__":
    run()
