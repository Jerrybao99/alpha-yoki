"""本地持仓基线：data/hold/holdings.csv 增删查。"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from src.config import Settings, get_settings
from src.tools import EXIT_DATA, EXIT_OK, ToolError, envelope

HOLDINGS_COLUMNS = ("ts_code", "name")


class HoldingsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str
    ts_code: str = ""
    name: str = ""


def holdings_path(settings: Settings) -> Path:
    return settings.data_path("hold") / "holdings.csv"


def load_holdings(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    content = path.read_text(encoding="utf-8").lstrip("\ufeff")
    return [dict(row) for row in csv.DictReader(content.splitlines())]


def save_holdings(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(HOLDINGS_COLUMNS), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def run_holdings(params: HoldingsParams, settings: Settings | None = None) -> tuple[int, dict[str, Any]]:
    resolved = settings or get_settings()
    path = holdings_path(resolved)
    rows = load_holdings(path)
    action = params.action
    if action == "list":
        return EXIT_OK, envelope(ok=True, command="holdings", data={"items": rows})
    code = params.ts_code.strip()
    if not code:
        raise ToolError("持仓操作需要股票代码", EXIT_DATA)
    if action == "add":
        existing = next((row for row in rows if row["ts_code"] == code), None)
        if existing is None:
            rows.append({"ts_code": code, "name": params.name})
            save_holdings(path, rows)
        elif params.name and existing.get("name") != params.name:
            existing["name"] = params.name
            save_holdings(path, rows)
        return EXIT_OK, envelope(ok=True, command="holdings", data={"items": rows})
    if action == "remove":
        kept = [row for row in rows if row["ts_code"] != code]
        if len(kept) == len(rows):
            raise ToolError(f"持仓中不存在 {code}", EXIT_DATA)
        save_holdings(path, kept)
        return EXIT_OK, envelope(ok=True, command="holdings", data={"items": kept})
    raise ToolError(f"未知持仓动作：{action}", EXIT_DATA)


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("holdings", help="本地持仓增删查")
    action = parser.add_subparsers(dest="holdings_action", required=True)
    add = action.add_parser("add", help="加入持仓")
    add.add_argument("ts_code", help="股票代码，如 600519.SH")
    add.add_argument("--name", default="", help="可选名称")
    action.add_parser("list", help="列出持仓")
    remove = action.add_parser("remove", help="移除持仓")
    remove.add_argument("ts_code", help="股票代码")
    parser.set_defaults(handler="holdings")
