# -*- coding: utf-8 -*-
"""汉诺塔入口。

用法:
    python main.py --gui   启动图形界面（默认）
    python main.py --cli   启动命令行模式
"""

import argparse


def main():
    parser = argparse.ArgumentParser(description="汉诺塔")
    parser.add_argument("--gui", action="store_true", help="启动图形界面（默认）")
    parser.add_argument("--cli", action="store_true", help="启动命令行模式")
    args = parser.parse_args()

    if args.cli:
        from cli import run
        run()
    else:
        from gui import main as gui_main
        gui_main()


if __name__ == "__main__":
    main()
