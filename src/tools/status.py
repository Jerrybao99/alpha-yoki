"""status：产物新鲜度。--check 供定时任务：过期或缺失退出 4。"""

from __future__ import annotations

import argparse
import datetime as _dt
from typing import Any

from pydantic import BaseModel, ConfigDict

from src.config import Settings, get_settings
from src.data.store import Freshness, Kind, freshness
from src.tools import EXIT_DATA, EXIT_OK, envelope


class StatusParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check: bool = False


def _item(info: Freshness) -> dict[str, Any]:
    return {
        "kind": info.kind.value,
        "path": str(info.path) if info.path else None,
        "stamp": info.stamp,
        "period": info.period,
        "expected_period": info.expected_period,
        "is_stale": info.is_stale,
        "reason": info.reason,
    }


def run_status(
    params: StatusParams,
    settings: Settings | None = None,
    *,
    today: _dt.date | None = None,
) -> tuple[int, dict[str, Any]]:
    resolved = settings or get_settings()
    today = today or _dt.date.today()
    items = [_item(freshness(kind, today, settings=resolved)) for kind in Kind]
    stale = any(item["is_stale"] for item in items)
    payload = envelope(ok=not (params.check and stale), command="status", data={"items": items})
    if params.check and stale:
        payload["error"] = "stale_or_missing"
        return EXIT_DATA, payload
    return EXIT_OK, payload


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("status", help="检查采集/评分/报告新鲜度")
    parser.add_argument("--check", action="store_true", help="过期或缺失时以退出码 4 结束")
    parser.set_defaults(handler="status")
