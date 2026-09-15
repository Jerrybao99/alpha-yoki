"""锐评追踪：UTF-8 JSONL 只追加不更新，按日落到 data/monitor/review-YYMMDD.jsonl。
记录 Provider / 模型 / 尝试次数 / 状态 / 违规码 / token；绝不写入密钥或提示词全文。
"""

from __future__ import annotations

import datetime as dt
import json
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any


class JsonlReviewTracer:
    def __init__(self, root: Path, *, today: Callable[[], dt.date] | None = None) -> None:
        self._root = Path(root)
        self._today = today or dt.date.today
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._root / f"review-{self._today().strftime('%y%m%d')}.jsonl"

    def record(self, **fields: Any) -> None:
        entry = {"ts": dt.datetime.now().isoformat(timespec="seconds"), **fields}
        line = json.dumps(entry, ensure_ascii=False, default=str) + "\n"
        with self._lock:
            self._root.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(line)
