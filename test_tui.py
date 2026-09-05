# -*- coding: utf-8 -*-
"""TUI 单元测试：布局几何、帧缓冲、状态机、解锁保密。运行: python -m unittest"""

import os
import shutil
import tempfile
import unittest

import game
import storage
import tui


class FakeClock:
    def __init__(self, start=1000.0):
        self.t = start

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


def make_app():
    term = tui.FakeTerminal()
    app = tui.TuiApp(term, clock=FakeClock())
    app.flush()
    return app, term


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


class TestDisplayWidth(unittest.TestCase):
    def test_ascii_and_cjk(self):
        self.assertEqual(tui.display_width("ab"), 2)
        self.assertEqual(tui.display_width("汉诺塔"), 6)
        self.assertEqual(tui.display_width("汉a"), 3)

    def test_pad(self):
        self.assertEqual(len(tui._pad("汉", 6)), 5)   # 2 显示宽 + 4 空格 = 5 字符
        self.assertEqual(tui.display_width(tui._pad("汉", 6)), 6)


class TestGeometry(unittest.TestCase):
    def test_disk_width_in_bounds(self):
        for n in range(1, 21):
            for disk in range(1, n + 1):
                w = tui.disk_width(disk, n)
                self.assertGreaterEqual(w, 8)
                self.assertLessEqual(w, tui.COL_W - 2)

    def test_disk_color_in_palette(self):
        for n in (5, 10, 20):
            for disk in range(1, n + 1):
                code = tui.disk_color_code(disk, n)
                self.assertGreaterEqual(code, 16)
                self.assertLessEqual(code, 231)


class TestScreen(unittest.TestCase):
    def test_put_and_plain_render(self):
        s = tui.Screen(20, 5)
        s.put(1, 2, "abc", fg=1)
        lines = s.render(color=False)
        self.assertEqual(lines[1][2:5], "abc")
        self.assertEqual(lines[1][0:2], "  ")

    def test_put_clips_out_of_bounds(self):
        s = tui.Screen(10, 3)
        s.put(0, 8, "0123456789")     # 右侧越界被截断
        s.put(5, 0, "x")              # 行越界被忽略
        self.assertEqual(s.render(color=False)[0][8:], "01")

    def test_put_center(self):
        s = tui.Screen(11, 3)
        s.put_center(0, "汉塔")       # 显示宽 4 → 起始列 3
        cells = [c[0] for c in s.grid[0]]
        self.assertEqual(cells[3:7], ["汉", "", "塔", ""])   # 全角占 2 格


class TestChallengeFlow(TempDataTestCase):
    def test_legal_move(self):
        app, _ = make_app()
        app.handle_key("1")           # 选中柱 0
        self.assertEqual(app.selected, 0)
        app.handle_key("3")           # 移到柱 2
        self.assertIsNone(app.selected)
        self.assertEqual(app.moves_done, 1)
        self.assertEqual(app.state[2], [1])
        self.assertEqual(app.last_legal_move, (0, 2))

    def test_empty_source_rejected(self):
        app, _ = make_app()
        app.handle_key("2")
        self.assertIn("该柱为空", app.message)
        self.assertIsNone(app.selected)

    def test_illegal_move_rejected(self):
        app, _ = make_app()
        app.handle_key("1")
        app.handle_key("2")           # 盘 1: 0 -> 1
        self.assertEqual(app.moves_done, 1)
        app.handle_key("1")
        app.handle_key("2")           # 盘 2 压盘 1，非法
        self.assertIn("非法移动", app.message)
        self.assertEqual(app.moves_done, 1)
        self.assertEqual(app.state[1][-1], 1)

    def test_reselect_same_peg_cancels(self):
        app, _ = make_app()
        app.handle_key("1")
        app.handle_key("1")
        self.assertIsNone(app.selected)


class TestChallengeWin(TempDataTestCase):
    def test_win_saves_record_and_unlocks(self):
        app, _ = make_app()
        app.clock.advance(7.0)
        for src, dst in game.generate_optimal_moves(5):
            app.handle_key(str(src + 1))
            app.handle_key(str(dst + 1))
        app.flush()
        self.assertEqual(app.overlay, "win")
        records = storage.load_records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["level"], 5)
        self.assertEqual(records[0]["moves"], 31)
        self.assertEqual(records[0]["best"], 31)
        self.assertEqual(records[0]["duration_sec"], 7.0)
        self.assertTrue(storage.passed(5))
        # 未通 10 层，横幅与更高层数不得出现
        self.assertFalse(app.passed_10)
        frame = "\n".join(app.screen.render(color=False))
        self.assertNotIn("🏆", frame)
        self.assertNotIn("解锁", frame)


class TestGating(TempDataTestCase):
    def test_locked_no_hidden_info(self):
        app, _ = make_app()
        self.assertEqual(app._level_choices(), list(range(5, 11)))
        help_text = "\n".join(app._help_body())
        self.assertIn("5~10", help_text)
        self.assertNotIn("5~20", help_text)
        frame = "\n".join(app.screen.render(color=False))
        self.assertNotIn("🏆", frame)
        self.assertNotIn("🎉", frame)
        self.assertNotIn("解锁", frame)

    def test_unlocked_after_10(self):
        storage.register_clear(10)
        app, _ = make_app()
        self.assertTrue(app.passed_10)
        self.assertEqual(app._level_choices(), list(range(5, 21)))
        help_text = "\n".join(app._help_body())
        self.assertIn("5~20", help_text)
        frame = "\n".join(app.screen.render(color=False))
        self.assertIn("解锁", frame)
        self.assertIn("🎉", frame)


class TestAutoMode(TempDataTestCase):
    def test_auto_finishes_without_record(self):
        app, _ = make_app()
        app.handle_key("m")
        self.assertEqual(app.mode, tui.MODE_AUTO)
        app.handle_key("s")
        self.assertTrue(app.auto_running)
        self.assertEqual(len(app.plan), 31)
        for _ in range(100):
            if not app.auto_running:
                break
            app.clock.advance(1.0)
            app.on_timeout()
        app.flush()
        self.assertFalse(app.auto_running)
        self.assertEqual(app.overlay, "demo")
        self.assertTrue(game.is_solved(app.state, 5))
        self.assertEqual(storage.load_records(), [])


class TestGuessMode(TempDataTestCase):
    def test_guess_steps_and_no_record(self):
        app, _ = make_app()
        app.handle_key("m")
        app.handle_key("m")
        self.assertEqual(app.mode, tui.MODE_GUESS)
        app.handle_key("s")
        self.assertEqual(len(app.plan), 31)
        for _ in range(31):
            app.handle_key("n")
        self.assertEqual(app.overlay, "demo")
        self.assertTrue(game.is_solved(app.state, 5))
        self.assertEqual(storage.load_records(), [])
        # 计划走完后 N 不再产生效果
        app.handle_key("n")
        self.assertEqual(app.plan_index, 31)


class TestInterval(unittest.TestCase):
    def test_clamped(self):
        app, _ = make_app()
        app.handle_key("m")           # 自动模式才可调
        for _ in range(60):
            app.handle_key("-")
        self.assertEqual(app.interval, 0.1)
        for _ in range(60):
            app.handle_key("+")
        self.assertEqual(app.interval, 5.0)


class TestLoadProgressCopy(TempDataTestCase):
    """回归：load_progress 必须返回副本，否则 register_clear 会污染默认值，
    导致同进程后续"文件缺失→默认值"的读取看到幻影解锁状态。"""

    def test_load_progress_returns_copy(self):
        first = storage.load_progress()
        first["max_cleared"] = 99
        self.assertEqual(storage.load_progress().get("max_cleared", 0), 0)
        storage.register_clear(5)
        self.assertFalse(storage.passed(10))
        self.assertTrue(storage.passed(5))


class TestSelftest(TempDataTestCase):
    def test_selftest_passes(self):
        self.assertTrue(tui.selftest())


if __name__ == "__main__":
    unittest.main()
