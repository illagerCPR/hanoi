# 汉诺塔（Hanoi Tower）

经典汉诺塔游戏，使用 Python 标准库实现，零第三方依赖。

## 功能特性

### 图形界面模式（GUI）

```bash
python main.py --gui      # 或直接 python main.py
```

- 可视化棋盘：鼠标点击柱子选取/移动盘子，带平滑移动动画
- 层数选择：**5~10 层**（完成 10 层挑战后解锁更多层数）
- **挑战模式**：玩家亲自挑战，完成后自动记录挑战记录
- **自动模式**：按最优解自动演示（步数 = 2^n − 1），每步执行间隔可调（0.1~5 秒）
- **推断模式**：按最优解逐步演示，每一步由玩家点击"执行下一步"确认
- 自动模式与推断模式**不计入挑战记录**
- 挑战记录窗口：时间戳、层数、移动步数、理论最佳步数、挑战时长

### 命令行模式（CLI）

```bash
python main.py --cli
```

- 仅提供挑战模式，命令设计与输出约定见 [CLI.md](CLI.md)（面向 AI Agent 的完整说明书）
- 支持 `start` / `move` / `hint` / `best` / `status` / `record` / `help` / `quit`
- UTF-8 输入输出，错误消息统一以 `错误: ` 开头，方便自动化解析

### 终端界面模式（TUI v2，Textual）

```bash
python main.py --tui-v2        # 需先 pip install -r requirements.txt
```

- 基于 [Textual](https://textual.textualize.io/) 框架：现代终端 UI、鼠标支持、CSS 主题
- 三模式与 GUI 对齐：挑战（计入记录）/ 自动（间隔 0.1~5 秒、可暂停）/ 推断（逐步确认）
- **鼠标点击棋盘柱子**选柱（挑战模式），或键盘 `←/→`+`回车`、`1/2/3` 直选
- 按钮化控制条 + `DataTable` 记录表 + 模态弹窗（帮助/层数/胜利通知）
- 仅此模式需要第三方依赖；`--gui`/`--cli`/`--tui` 保持零依赖

### 终端界面模式（TUI v1，零依赖）

```bash
python main.py --tui
```

- 纯标准库 ANSI 渲染（256 色彩色棋盘、备用屏、帧间 diff 防闪烁），Windows 与 Linux 通用
- 三模式与 GUI 对齐：挑战（计入记录）/ 自动（间隔 0.1~5 秒可调、可暂停）/ 推断（逐步确认），后两者不计记录
- 键盘操作：`←/→` 或 `A/D` 移动柱光标，`回车/空格` 两段式选柱，`1/2/3` 直选柱子
- `S` 开始/重置、`P` 暂停、`N` 执行下一步、`+/-` 调间隔、`L` 层数、`R` 记录、`H` 帮助、`M` 切换模式、`Q` 退出
- 层数范围与解锁进度和 GUI/CLI 共享（通关 10 层后解锁更多层数）
- 建议终端尺寸 ≥ 80×32（20 层通关挑战需要更高）

## 安装与运行

要求：Python 3.8+（开发环境为 3.14，tkinter 为标准库自带，无需安装）

```bash
python main.py --gui     # 图形界面（默认）
python main.py --cli     # 命令行
python main.py --tui     # 终端界面 v1（零依赖）
python main.py --tui-v2  # 终端界面 v2（Textual，需 pip install -r requirements.txt）
python -m unittest       # 运行单元测试
```

## 目录结构

```
main.py          # 程序入口
game.py          # 核心逻辑：棋盘状态、移动合法性、最优解生成
gui.py           # 图形界面（tkinter）
tui.py           # 终端界面 v1（ANSI，纯标准库）
tui_v2.py        # 终端界面 v2（Textual 框架）
cli.py           # 命令行模式
storage.py       # 数据持久化（挑战记录、通关进度）
CLI.md           # 命令行模式说明书
requirements.txt # tui-v2 依赖（仅 --tui-v2 需要）
test_game.py     # 单元测试（核心逻辑）
test_tui.py      # 单元测试（TUI v1 布局/状态机/解锁保密）
test_tui_v2.py   # 单元测试（TUI v2 Pilot 交互测试）
data/            # 运行时自动生成（records.json / progress.json）
```

## 玩法说明

- 三根柱子：0（起始）、1（辅助）、2（目标）
- 一次只能移动一个盘子，大盘不能压在小盘上
- 目标：将全部盘子从柱 0 移到柱 2，理论最少步数 = 2^n − 1
- 完成挑战后自动记录：时间戳、层数、移动步数、理论最佳步数、挑战时长

## 隐藏内容

通关 10 层挑战后将有新的内容解锁——具体的惊喜由你在游戏中亲自发现。

## 数据文件

- `data/records.json`：挑战记录
- `data/progress.json`：通关进度（GUI 与 CLI 共享）
- 可通过环境变量 `HANOI_DATA_DIR` 指定数据目录（便于测试）

## 下载与完整性校验

Release 提供 `SHA256SUMS.txt`，下载后建议校验：

- PowerShell: `Get-FileHash .\Hanoi-windows-x64.exe -Algorithm SHA256`，与 `SHA256SUMS.txt` 比对
- Linux/macOS: `sha256sum -c SHA256SUMS.txt`
- 若 Windows 提示"文件已被阻止"或 PyInstaller 报 `Could not load PyInstaller's embedded PKG archive`，先执行 `Unblock-File .\Hanoi-windows-x64.exe`，并确认文件大小与哈希一致（多半是下载不完整或杀软拦截）

## 单元测试

```bash
python -m unittest -v
```

覆盖：最优步数公式、最优解序列合法性、移动规则、任意盘面求解、记录持久化、进度解锁逻辑、TUI v1/v2 布局几何与按键状态机、未通关时的隐藏信息保密。

## OpenCode 对话链接

https://opncd.ai/share/VDkHjSN0