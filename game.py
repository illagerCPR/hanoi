# -*- coding: utf-8 -*-
"""汉诺塔核心逻辑：塔状态、移动合法性、最优解生成。

状态表示：三根柱子（0/1/2），每柱为列表，列表末尾为栈顶。
盘子编号 1..n（1 最小，n 最大）。
"""

from typing import List, Optional, Tuple

SOURCE = 0
TARGET = 2

MIN_LEVEL = 5
MAX_VISIBLE_LEVEL = 10
HIDDEN_LEVELS = 20


def optimal_steps(n: int) -> int:
    """理论最优步数 2^n - 1。"""
    if n < 1:
        return 0
    return 2 ** n - 1


def initial_state(n: int) -> List[List[int]]:
    """初始状态：全部盘子位于柱子 0。"""
    return [list(range(n, 0, -1)), [], []]


def is_legal(state: List[List[int]], src: int, dst: int) -> bool:
    """检查一次移动是否合法。"""
    if src not in (0, 1, 2) or dst not in (0, 1, 2):
        return False
    if src == dst:
        return False
    if not state[src]:
        return False
    if state[dst] and state[dst][-1] < state[src][-1]:
        return False
    return True


def apply_move(state: List[List[int]], src: int, dst: int) -> List[List[int]]:
    """执行移动（原地修改），返回同一对象。调用前需保证合法。"""
    disk = state[src].pop()
    state[dst].append(disk)
    return state


def generate_optimal_moves(n: int) -> List[Tuple[int, int]]:
    """生成从柱子 0 到柱子 2 的最优移动序列，共 2^n - 1 步。"""
    moves: List[Tuple[int, int]] = []

    def hanoi(k: int, src: int, dst: int, aux: int) -> None:
        if k == 0:
            return
        hanoi(k - 1, src, aux, dst)
        moves.append((src, dst))
        hanoi(k - 1, aux, dst, src)

    hanoi(n, SOURCE, TARGET, 1)
    return moves


def is_solved(state: List[List[int]], n: int) -> bool:
    """所有盘子是否已到达目标柱。"""
    return len(state[TARGET]) == n


def find_disk(state: List[List[int]], disk: int) -> Optional[int]:
    """返回盘子所在柱子，找不到返回 None。"""
    for peg in (0, 1, 2):
        if disk in state[peg]:
            return peg
    return None


def format_state(state: List[List[int]], moves_done: int, best: int) -> str:
    """将状态渲染为 ASCII 棋盘文本。"""
    height = max((len(p) for p in state), default=0)
    max_w = max((len(str(d)) for peg in state for d in peg), default=1)
    cell = max_w + 4
    lines = []
    header = "".join(f"{(' ' * (cell - 1) + str(i))[-cell:]}" for i in (0, 1, 2))
    lines.append(header)
    lines.append("".join("=" * cell for _ in range(3)))
    for row in range(height - 1, -1, -1):
        cells = []
        for peg in state:
            if row < len(peg):
                text = str(peg[row])
                cells.append(f"|{text.center(cell - 2)}|")
            else:
                cells.append("|" + " " * (cell - 2) + "|")
        lines.append("".join(cells))
    lines.append("".join("-" * cell for _ in range(3)))
    lines.append(f"步数: {moves_done} / 最优: {best}")
    return "\n".join(lines)
