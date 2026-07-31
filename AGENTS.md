# AGENTS.md

汉诺塔游戏：Python 3.14 标准库（tkinter），零第三方依赖。文件平铺，无包结构。

## 命令

- 运行：`python main.py --gui`（默认）或 `python main.py --cli`
- 测试：`python -m unittest test_game`（12 项）
- 冒烟测试 GUI（无头环境）：`python -c "import gui; app = gui.HanoiApp(); app.after(800, app.destroy); app.mainloop()"`
- 验证 CLI 管道输入：PowerShell 5.1 不支持 `<` 重定向，须用 `cmd /c "python main.py --cli < in.txt"`

## 硬性约束：隐藏挑战保密

通关 10 层前**不得**以任何形式（代码输出、帮助文本、CLI.md、README）出现 11~20 层、奖杯等隐藏信息。文档只允许模糊写"通关 10 层后解锁更多内容"。解锁逻辑集中在 `storage.passed(10)` / `storage.register_clear()` 与各处的 `_level_limit()`。

## 架构要点

- `game.py`：纯逻辑（状态=三柱 list，栈顶在末尾；`generate_optimal_moves` 2^n−1；`cli.plan_from_state` 对任意盘面求解）
- `storage.py`：模块级路径常量，测试中直接替换 `storage.DATA_DIR`；也可用环境变量 `HANOI_DATA_DIR` 覆盖（测试隔离推荐）
- `gui.py`：三模式（挑战/自动/推断）。自动/推断不计记录；仅挑战模式调用 `add_record` + `register_clear`
- `cli.py`：入口 `run()` 强制 `stdout/stdin.reconfigure(encoding="utf-8")` 并防御输入 BOM；错误消息统一 `错误: ` 前缀；`help` 文本随解锁状态变化
- 挑战记录字段：timestamp / level / moves / best（2^n−1）/ duration_sec

## 其他

- 修改 CLI 命令时须同步更新 `CLI.md`（面向 AI Agent 的说明书，含输出格式约定）
- GUI 画布无头不可测；改动 `_disk_width` 等绘制参数后靠冒烟测试 + 人工目检
- 盘宽设计：柱间距 270，最大盘宽 ≤ 250 以免重叠（`_disk_width` 为 `50 + (disk-1)*span/(n-1)`）
- `data/` 目录运行时自动创建；未通关时不应残留 progress/records 数据在仓库
