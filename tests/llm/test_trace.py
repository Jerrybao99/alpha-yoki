"""锐评追踪单测：UTF-8 JSONL 只追加、按日分文件、线程并发写入不丢行。"""

from __future__ import annotations

import datetime as dt
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from src.llm.trace import JsonlReviewTracer


def _tracer(root: Path) -> JsonlReviewTracer:
    return JsonlReviewTracer(root, today=lambda: dt.date(2026, 9, 15))


def test_path_is_daily_jsonl_under_root(tmp_path: Path) -> None:
    tracer = _tracer(tmp_path / "monitor")
    assert tracer.path == tmp_path / "monitor" / "review-260915.jsonl"


def test_record_appends_utf8_json_lines_with_timestamp(tmp_path: Path) -> None:
    tracer = _tracer(tmp_path)
    tracer.record(code="000807", status="rejected", violations=["latin"], attempt=1)
    tracer.record(code="000807", status="retry", violations=[], attempt=2)

    lines = tracer.path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first, second = (json.loads(line) for line in lines)
    assert first["code"] == "000807" and first["status"] == "rejected"
    assert first["violations"] == ["latin"]
    assert second["attempt"] == 2
    assert "ts" in first and first["ts"].startswith("2026-")
    assert "\\u" not in lines[0]


def test_record_never_rewrites_existing_lines(tmp_path: Path) -> None:
    tracer = _tracer(tmp_path)
    tracer.record(code="a", status="success")
    before = tracer.path.read_text(encoding="utf-8")
    tracer.record(code="b", status="fallback")
    after = tracer.path.read_text(encoding="utf-8")
    assert after.startswith(before)
    assert len(after.splitlines()) == 2


def test_concurrent_records_are_all_persisted(tmp_path: Path) -> None:
    tracer = _tracer(tmp_path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: tracer.record(code=f"{i:06d}", status="success"), range(40)))
    lines = tracer.path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 40
    assert {json.loads(line)["code"] for line in lines} == {f"{i:06d}" for i in range(40)}
