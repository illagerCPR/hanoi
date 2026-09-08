# -*- coding: utf-8 -*-
"""汉诺塔入口。

用法:
    python main.py --gui     启动图形界面（默认）
    python main.py --cli     启动命令行模式
    python main.py --tui     启动终端界面（TUI v1，零依赖）
    python main.py --tui-v2  启动终端界面 v2（Textual，需 pip install textual）
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="汉诺塔")
    parser.add_argument("--gui", action="store_true", help="启动图形界面（默认）")
    parser.add_argument("--cli", action="store_true", help="启动命令行模式")
    parser.add_argument("--tui", action="store_true", help="启动终端界面（TUI v1，零依赖）")
    parser.add_argument("--tui-v2", action="store_true",
                        help="启动终端界面 v2（Textual，需 pip install textual）")
    args = parser.parse_args()

    if args.cli:
        from cli import run
        run()
    elif args.tui:
        import tui
        tui.main()
    elif args.tui_v2:
        try:
            import tui_v2
        except ModuleNotFoundError as exc:
            if exc.name == "textual":
                raise SystemExit(
                    "错误: --tui-v2 需要 Textual 框架，请先安装: pip install textual")
            raise
        tui_v2.main()
    else:
        from gui import main as gui_main
        gui_main()


if __name__ == "__main__":
    main()
