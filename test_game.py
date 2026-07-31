# -*- coding: utf-8 -*-
"""单元测试：核心逻辑与持久化。运行: python -m unittest"""

import os
import shutil
import tempfile
import unittest

import cli
import game
import storage


class TestOptimalSteps(unittest.TestCase):
    def test_steps(self):
        for n in range(1, 21):
            self.assertEqual(game.optimal_steps(n), 2 ** n - 1)

    def test_optimal_moves_valid_and_solve(self):
        for n in range(1, 21):
            moves = game.generate_optimal_moves(n)
            self.assertEqual(len(moves), 2 ** n - 1)
            state = game.initial_state(n)
            for src, dst in moves:
                self.assertTrue(game.is_legal(state, src, dst))
                game.apply_move(state, src, dst)
            self.assertTrue(game.is_solved(state, n))


class TestLegal(unittest.TestCase):
    def setUp(self):
        self.state = game.initial_state(3)

    def test_invalid_pegs(self):
        self.assertFalse(game.is_legal(self.state, -1, 1))
        self.assertFalse(game.is_legal(self.state, 0, 3))

    def test_same_peg(self):
        self.assertFalse(game.is_legal(self.state, 0, 0))

    def test_empty_src(self):
        self.assertFalse(game.is_legal(self.state, 1, 2))

    def test_bigger_on_smaller(self):
        game.apply_move(self.state, 0, 1)
        game.apply_move(self.state, 0, 2)
        # 柱1顶为盘1，柱2顶为盘2；1 -> 2 合法，2 -> 1 非法
        self.assertTrue(game.is_legal(self.state, 1, 2))
        self.assertFalse(game.is_legal(self.state, 2, 1))


class TestPlanFromState(unittest.TestCase):
    def test_from_initial(self):
        for n in (5, 7, 10, 12, 20):
            state = game.initial_state(n)
            plan = cli.plan_from_state(state, n)
            self.assertEqual(len(plan), game.optimal_steps(n))
            for src, dst in plan:
                self.assertTrue(game.is_legal(state, src, dst))
                game.apply_move(state, src, dst)
            self.assertTrue(game.is_solved(state, n))

    def test_from_random_walk(self):
        for n in (5, 8):
            state = game.initial_state(n)
            for _ in range(20):
                src = (0, 1, 2)[len(state[0]) % 3]
                src = max((i for i in (0, 1, 2) if state[i]), key=lambda i: len(state[i]))
                dst = (0, 1, 2)[(src + 1) % 3]
                if game.is_legal(state, src, dst):
                    game.apply_move(state, src, dst)
            plan = cli.plan_from_state(state, n)
            self.assertGreater(len(plan), 0)
            for src, dst in plan:
                self.assertTrue(game.is_legal(state, src, dst))
                game.apply_move(state, src, dst)
            self.assertTrue(game.is_solved(state, n))


class TestStorage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old_dir = storage.DATA_DIR
        storage.DATA_DIR = self.tmp
        storage.PROGRESS_FILE = os.path.join(self.tmp, "progress.json")
        storage.RECORDS_FILE = os.path.join(self.tmp, "records.json")

    def tearDown(self):
        storage.DATA_DIR = self.old_dir
        storage.PROGRESS_FILE = os.path.join(self.old_dir, "progress.json")
        storage.RECORDS_FILE = os.path.join(self.old_dir, "records.json")
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_empty_defaults(self):
        self.assertEqual(storage.max_cleared(), 0)
        self.assertFalse(storage.passed(10))
        self.assertEqual(storage.load_records(), [])

    def test_records_roundtrip(self):
        storage.add_record(7, 65, 127, 42.5)
        storage.add_record(8, 200, 255, 99.9)
        records = storage.load_records()
        self.assertEqual(len(records), 2)
        r = records[0]
        self.assertEqual(r["level"], 7)
        self.assertEqual(r["moves"], 65)
        self.assertEqual(r["best"], 127)
        self.assertEqual(r["duration_sec"], 42.5)
        self.assertIn("timestamp", r)

    def test_register_clear(self):
        res = storage.register_clear(10)
        self.assertTrue(res["passed_10"])
        self.assertFalse(res["passed_20"])
        self.assertTrue(storage.passed(10))
        self.assertTrue(storage.passed(9))
        self.assertFalse(storage.passed(11))

        res = storage.register_clear(20)
        self.assertTrue(res["passed_20"])

    def test_max_cleared_keeps_highest(self):
        storage.register_clear(7)
        storage.register_clear(6)
        self.assertEqual(storage.max_cleared(), 7)


if __name__ == "__main__":
    unittest.main()
