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

## 安装与运行

要求：Python 3.8+（开发环境为 3.14，tkinter 为标准库自带，无需安装）

```bash
python main.py --gui     # 图形界面
python main.py --cli     # 命令行
python -m unittest       # 运行单元测试
```

## 目录结构

```
main.py        # 程序入口
game.py        # 核心逻辑：棋盘状态、移动合法性、最优解生成
gui.py         # 图形界面（tkinter）
cli.py         # 命令行模式
storage.py     # 数据持久化（挑战记录、通关进度）
CLI.md         # 命令行模式说明书
test_game.py   # 单元测试
data/          # 运行时自动生成（records.json / progress.json）
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

## 单元测试

```bash
python -m unittest test_game -v
```

覆盖：最优步数公式、最优解序列合法性、移动规则、任意盘面求解、记录持久化、进度解锁逻辑。

## OpenCode 对话链接

https://opncd.ai/share/VDkHjSN0