# AGENTS.md

汉诺塔游戏：Python 3.14 标准库（tkinter + ANSI TUI），零第三方依赖。文件平铺，无包结构。

## 命令

- 运行：`python main.py --gui`（默认）、`python main.py --cli` 或 `python main.py --tui`
- 测试：`python -m unittest`（31 项，覆盖 game/cli/storage/tui）
- 冒烟测试 GUI（无头环境）：`python -c "import gui; app = gui.HanoiApp(); app.after(800, app.destroy); app.mainloop()"`
- 冒烟测试 TUI（无头环境）：`HANOI_TUI_SELFTEST=1 python main.py --tui`（假终端跑核心流程，输出 `SELFTEST OK`）
- 验证 CLI 管道输入：PowerShell 5.1 不支持 `<` 重定向，须用 `cmd /c "python main.py --cli < in.txt"`

## 硬性约束：隐藏挑战保密

通关 10 层前**不得**以任何形式（代码输出、帮助文本、CLI.md、README）出现 11~20 层、奖杯等隐藏信息。文档只允许模糊写"通关 10 层后解锁更多内容"。解锁逻辑集中在 `storage.passed(10)` / `storage.register_clear()` 与各处的 `_level_limit()`。

## 架构要点

- `game.py`：纯逻辑（状态=三柱 list，栈顶在末尾；`generate_optimal_moves` 2^n−1；`cli.plan_from_state` 对任意盘面求解）
- `storage.py`：模块级路径常量，测试中直接替换 `storage.DATA_DIR`；也可用环境变量 `HANOI_DATA_DIR` 覆盖（测试隔离推荐）；`load_progress()` 必须返回副本（曾因返回默认值本体导致幻影解锁，勿回退）
- `gui.py`：三模式（挑战/自动/推断）。自动/推断不计记录；仅挑战模式调用 `add_record` + `register_clear`
- `tui.py`：ANSI 自绘终端界面，三模式与 GUI 对齐；`Screen` 字符帧缓冲 + 帧间 diff 防闪烁；宽度用 `east_asian_width` 计算且全角占 2 格（延续格存 `""`）；全角字符 join 后字符串索引 ≠ 屏幕列，测试断言须查 `grid`；`FakeTerminal`/`HANOI_TUI_SELFTEST` 支撑无头测试
- `cli.py`：入口 `run()` 强制 `stdout/stdin.reconfigure(encoding="utf-8")` 并防御输入 BOM；错误消息统一 `错误: ` 前缀；`help` 文本随解锁状态变化
- 挑战记录字段：timestamp / level / moves / best（2^n−1）/ duration_sec

## 其他

- 修改 CLI 命令时须同步更新 `CLI.md`（面向 AI Agent 的说明书，含输出格式约定）
- GUI 画布无头不可测；改动 `_disk_width` 等绘制参数后靠冒烟测试 + 人工目检
- 盘宽设计：柱间距 270，最大盘宽 ≤ 250 以免重叠（`_disk_width` 为 `50 + (disk-1)*span/(n-1)`）
- `data/` 目录运行时自动创建；未通关时不应残留 progress/records 数据在仓库
