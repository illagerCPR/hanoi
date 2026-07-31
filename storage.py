# -*- coding: utf-8 -*-
"""数据持久化：挑战记录与通关进度，均存储为 data/ 下的 JSON 文件。"""

import json
import os
from datetime import datetime
from typing import Dict, List

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("HANOI_DATA_DIR") or os.path.join(BASE_DIR, "data")
PROGRESS_FILE = os.path.join(DATA_DIR, "progress.json")
RECORDS_FILE = os.path.join(DATA_DIR, "records.json")

DEFAULT_PROGRESS: Dict[str, int] = {"max_cleared": 0}


def _ensure_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def _read_json(path: str, default) -> dict:
    _ensure_dir()
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def _write_json(path: str, data) -> None:
    _ensure_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_progress() -> Dict[str, int]:
    data = _read_json(PROGRESS_FILE, DEFAULT_PROGRESS)
    if not isinstance(data, dict) or "max_cleared" not in data:
        data = dict(DEFAULT_PROGRESS)
    return data


def save_progress(progress: Dict[str, int]) -> None:
    _write_json(PROGRESS_FILE, progress)


def max_cleared() -> int:
    """已通过的最高层数。"""
    return int(load_progress().get("max_cleared", 0))


def passed(level: int) -> bool:
    """是否已通过指定层数。"""
    return max_cleared() >= level


def register_clear(level: int) -> Dict[str, bool]:
    """记录一次通关，返回 {level_new_record, passed_10, passed_20}。"""
    progress = load_progress()
    old = int(progress.get("max_cleared", 0))
    if level > old:
        progress["max_cleared"] = level
        save_progress(progress)
    return {
        "level_new_record": level > old,
        "passed_10": max(level, old) >= 10,
        "passed_20": max(level, old) >= 20,
    }


def load_records() -> List[dict]:
    data = _read_json(RECORDS_FILE, [])
    return data if isinstance(data, list) else []


def add_record(level: int, moves: int, best: int, duration_sec: float) -> dict:
    """追加一条挑战记录，返回记录本身。"""
    record = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "level": level,
        "moves": moves,
        "best": best,
        "duration_sec": round(duration_sec, 1),
    }
    records = load_records()
    records.append(record)
    _write_json(RECORDS_FILE, records)
    return record
