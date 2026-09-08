# -*- coding: utf-8 -*-
"""TUI v2（Textual）单元测试：Pilot 无头交互、状态机、解锁保密。

运行: python -m unittest test_tui_v2
"""

import os
import shutil
import tempfile
import unittest

import game
import storage
from tui import COL_W, GAP, MODE_AUTO, MODE_CHALLENGE, MODE_GUESS

from tui_v2 import HanoiV2App, HelpScreen, NoticeScreen, RecordsScreen


class FakeClock:
    def __init__(self, start=1000.0):
        self.t = start

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


class TempDataTestCase(unittest.TestCase):
    """隔离数据目录，避免污染真实进度/记录。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = (storage.DATA_DIR, storage.PROGRESS_FILE, storage.RECORDS_FILE)
        storage.DATA_DIR = self.tmp
        storage.PROGRESS_FILE = os.path.join(self.tmp, "progress.json")
        storage.RECORDS_FILE = os.path.join(self.tmp, "records.json")

    def tearDown(self):
        storage.DATA_DIR, storage.PROGRESS_FILE, storage.RECORDS_FILE = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestKeyFlow(TempDataTestCase, unittest.IsolatedAsyncioTestCase):
    async def test_key_move(self):
        app = HanoiV2App(clock=FakeClock())
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.press("1", "3")
            self.assertEqual(app.moves_done, 1)
            self.assertEqual(app.state[2], [1])
            self.assertEqual(app.last_legal_move, (0, 2))

    async def test_click_move(self):
        app = HanoiV2App(clock=FakeClock())
        async with app.run_test(size=(100, 40)) as pilot:
            # 柱 0 中心在棋盘 x=12；柱 2 中心 x=68（几何同 v1）
            await pilot.click("BoardWidget", offset=(COL_W // 2, 2))
            self.assertEqual(app.selected, 0)
            await pilot.click("BoardWidget", offset=(2 * (COL_W + GAP) + COL_W // 2, 2))
            self.assertEqual(app.moves_done, 1)
            self.assertEqual(app.state[2], [1])

    async def test_empty_source_rejected(self):
        app = HanoiV2App(clock=FakeClock())
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.press("2")
            self.assertIn("该柱为空", app.message)

    async def test_illegal_move_rejected(self):
        app = HanoiV2App(clock=FakeClock())
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.press("1", "2")       # 盘 1: 0 -> 1
            await pilot.press("1", "2")       # 盘 2 压盘 1，非法
            self.assertIn("非法移动", app.message)
            self.assertEqual(app.moves_done, 1)
            self.assertEqual(app.state[1][-1], 1)


class TestWin(TempDataTestCase, unittest.IsolatedAsyncioTestCase):
    async def test_win_saves_record_and_gating(self):
        app = HanoiV2App(clock=FakeClock())
        async with app.run_test(size=(100, 40)) as pilot:
            app.clock.advance(9.0)
            for src, dst in game.generate_optimal_moves(5):
                await pilot.press(str(src + 1), str(dst + 1))
            self.assertIsInstance(app.screen, NoticeScreen)
            records = storage.load_records()
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["level"], 5)
            self.assertEqual(records[0]["moves"], 31)
            self.assertEqual(records[0]["duration_sec"], 9.0)
            self.assertTrue(storage.passed(5))
            self.assertFalse(app.passed_10)          # 通关 5 层不解锁 10 层内容
            banner = str(app.query_one("#banner").render())
            self.assertNotIn("🏆", banner)
            self.assertNotIn("解锁", banner)


class TestGating(TempDataTestCase, unittest.IsolatedAsyncioTestCase):
    async def test_locked(self):
        app = HanoiV2App(clock=FakeClock())
        async with app.run_test(size=(100, 40)) as pilot:
            self.assertEqual(app.level_choices(), list(range(5, 11)))
            banner = str(app.query_one("#banner").render())
            self.assertEqual(banner.strip(), "")
            await pilot.press("h")
            body = str(app.screen.query_one("#help-body").render())
            self.assertIn("5~10", body)
            self.assertNotIn("5~20", body)

    async def test_unlocked_after_10(self):
        storage.register_clear(10)
        app = HanoiV2App(clock=FakeClock())
        async with app.run_test(size=(100, 40)) as pilot:
            self.assertTrue(app.passed_10)
            self.assertEqual(app.level_choices(), list(range(5, 21)))
            banner = str(app.query_one("#banner").render())
            self.assertIn("解锁", banner)
            await pilot.press("h")
            body = str(app.screen.query_one("#help-body").render())
            self.assertIn("5~20", body)


class TestModes(TempDataTestCase, unittest.IsolatedAsyncioTestCase):
    async def test_auto_finishes_without_record(self):
        app = HanoiV2App(clock=FakeClock())
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.press("m")            # → 自动
            self.assertEqual(app.mode, MODE_AUTO)
            await pilot.press("s")
            self.assertTrue(app.auto_running)
            self.assertEqual(len(app.plan), 31)
            for _ in range(31):
                app._auto_step()
                await pilot.pause()
            self.assertFalse(app.auto_running)
            self.assertIsInstance(app.screen, NoticeScreen)
            self.assertTrue(game.is_solved(app.state, 5))
            self.assertEqual(storage.load_records(), [])

    async def test_pause_toggle(self):
        app = HanoiV2App(clock=FakeClock())
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.press("m", "s")
            self.assertFalse(app.auto_paused)
            await pilot.press("p")
            self.assertTrue(app.auto_paused)
            await pilot.press("p")
            self.assertFalse(app.auto_paused)

    async def test_guess_steps_and_no_record(self):
        app = HanoiV2App(clock=FakeClock())
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.press("m", "m")       # → 推断
            self.assertEqual(app.mode, MODE_GUESS)
            await pilot.press("s")
            await pilot.press(*(["n"] * 31))
            self.assertEqual(app.plan_index, 31)
            self.assertIsInstance(app.screen, NoticeScreen)
            self.assertTrue(game.is_solved(app.state, 5))
            self.assertEqual(storage.load_records(), [])
            await pilot.press("n")            # 完成后无效
            self.assertEqual(app.plan_index, 31)

    async def test_interval_clamped(self):
        app = HanoiV2App(clock=FakeClock())
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.press("m")            # 自动模式才可调
            for _ in range(60):
                await pilot.press("-")
            self.assertEqual(app.interval, 0.1)
            for _ in range(60):
                await pilot.press("+")
            self.assertEqual(app.interval, 5.0)

    async def test_level_picker(self):
        app = HanoiV2App(clock=FakeClock())
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.press("l")
            await pilot.pause()
            await pilot.click("#level-6")
            await pilot.pause()
            self.assertEqual(app.n, 6)
            self.assertEqual(app.moves_done, 0)
            self.assertEqual(app.state, game.initial_state(6))

    async def test_records_modal(self):
        storage.add_record(7, 65, 127, 42.5)
        app = HanoiV2App(clock=FakeClock())
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.press("r")
            self.assertIsInstance(app.screen, RecordsScreen)
            table = app.screen.query_one("#records-table")
            self.assertEqual(table.row_count, 1)
            await pilot.press("escape")
            self.assertNotIsInstance(app.screen, RecordsScreen)


class TestBoardRender(TempDataTestCase, unittest.IsolatedAsyncioTestCase):
    async def test_board_contains_pegs_and_disks(self):
        app = HanoiV2App(clock=FakeClock())
        async with app.run_test(size=(100, 40)) as pilot:
            text = str(app.query_one("BoardWidget").render())
            for peg in ("0", "1", "2"):
                self.assertIn(peg, text)
            for disk in ("1", "2", "3", "4", "5"):
                self.assertIn(disk, text)


if __name__ == "__main__":
    unittest.main()
