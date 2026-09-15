"""微信文本指令 → CLI 工具；群聊与非白名单直接丢弃。"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from src.config import Settings
from src.data.store import Kind, latest, load_features_prefer_raw
from src.reports.reporting import load_score_rows_prefer_raw
from src.tools.holdings import HoldingsParams, run_holdings
from src.tools.market import CollectParams, run_collect
from src.tools.status import StatusParams, run_status

HELP_TEXT = "可用指令：帮助 / 状态 / 报告 / 更新 / 持仓 / 加仓 600519 / 减仓 600519 / 查 600519"

_CODED = re.compile(r"^(加仓|减仓|查)\s+(\S+)$")
_NAMED = {
    "帮助": "help",
    "help": "help",
    "状态": "status",
    "报告": "report",
    "更新": "update",
    "持仓": "holdings",
}
_CODED_NAME = {"加仓": "add", "减仓": "remove", "查": "query"}

ToolMap = dict[str, Callable[..., str]]


@dataclass(frozen=True)
class Command:
    name: str
    code: str = ""


@dataclass(frozen=True)
class Incoming:
    sender: str
    text: str
    group_id: str
    context_token: str
    typing_ticket: str = ""


def normalize_ts_code(raw: str) -> str:
    code = raw.strip().upper()
    if "." in code:
        return code
    if code.startswith("6"):
        return f"{code}.SH"
    if code.startswith(("0", "3")):
        return f"{code}.SZ"
    if code.startswith(("4", "8")):
        return f"{code}.BJ"
    return code


def parse_command(text: str) -> Command:
    stripped = text.strip()
    coded = _CODED.match(stripped)
    if coded:
        return Command(name=_CODED_NAME[coded.group(1)], code=normalize_ts_code(coded.group(2)))
    name = _NAMED.get(stripped, "unknown")
    return Command(name=name)


def split_message(text: str, max_chars: int) -> list[str]:
    if max_chars <= 0 or not text:
        return [text]
    return [text[index : index + max_chars] for index in range(0, len(text), max_chars)]


def is_allowed(sender: str, settings: Settings, owner_id: str) -> bool:
    raw = settings.wechat_allowed_users.strip()
    if not raw:
        return bool(owner_id) and sender == owner_id
    allowed = {part.strip() for part in raw.split(",") if part.strip()}
    return sender in allowed


def handle_incoming(
    incoming: Incoming,
    settings: Settings,
    *,
    owner_id: str,
    tools: ToolMap | None = None,
) -> str | None:
    if incoming.group_id:
        return None
    if not is_allowed(incoming.sender, settings, owner_id):
        return None
    command = parse_command(incoming.text)
    resolved = tools or default_tools(settings)
    if command.name == "help":
        return HELP_TEXT
    if command.name == "unknown":
        return "未知指令，回复「帮助」查看用法"
    handler = resolved.get(command.name)
    if handler is None:
        return HELP_TEXT
    if command.code:
        return handler(command.code)
    return handler()


def default_tools(settings: Settings) -> ToolMap:
    def _status() -> str:
        _code, payload = run_status(StatusParams(check=False), settings)
        items = (payload.get("data") or {}).get("items") or []
        lines = [f"{item['kind']}: {item['reason']}" for item in items]
        return "新鲜度\n" + "\n".join(lines) if lines else "无状态"

    def _report() -> str:
        path = latest(Kind.REPORT, settings=settings)
        if path is None:
            return "无报告，请先运行 alpha-jerry report"
        rows = load_score_rows_prefer_raw(path)[:5]
        if not rows:
            return f"报告已生成：{path.name}"
        names = [str(row.get("name") or row.get("ts_code") or "") for row in rows]
        return "最新报告前五：" + "、".join(part for part in names if part)

    def _update() -> str:
        _code, payload = run_collect(CollectParams(update=True), settings)
        data = payload.get("data") or {}
        if data.get("skipped"):
            return f"数据仍新鲜（{data.get('period')}），已跳过采集"
        return f"采集完成 成功{data.get('success_count', 0)} 失败{data.get('failure_count', 0)}"

    def _holdings() -> str:
        _code, payload = run_holdings(HoldingsParams(action="list"), settings)
        items = (payload.get("data") or {}).get("items") or []
        if not items:
            return "持仓为空"
        return "持仓：" + "、".join(f"{row.get('ts_code')} {row.get('name', '')}".strip() for row in items)

    def _add(code: str) -> str:
        run_holdings(HoldingsParams(action="add", ts_code=code), settings)
        return f"已加仓 {code}"

    def _remove(code: str) -> str:
        run_holdings(HoldingsParams(action="remove", ts_code=code), settings)
        return f"已减仓 {code}"

    def _query(code: str) -> str:
        path = latest(Kind.COLLECT, settings=settings)
        if path is None:
            return f"无采集数据，无法查询 {code}"
        features = load_features_prefer_raw(path)
        feat = next((item for item in features if item.ts_code == code), None)
        if feat is None:
            return f"未找到 {code}"
        extra = ""
        scores_path = latest(Kind.SCORES, settings=settings)
        if scores_path is not None:
            row = next(
                (item for item in load_score_rows_prefer_raw(scores_path) if item.get("ts_code") == code),
                None,
            )
            if row:
                extra = f" 评级{row.get('评级')}"
        holder = f"{feat.holder_num}户" if feat.holder_num is not None else "股东户数未知"
        return f"{feat.ts_code} {feat.name or ''} {feat.industry or ''} {holder}{extra}".strip()

    return {
        "status": _status,
        "report": _report,
        "update": _update,
        "holdings": _holdings,
        "add": _add,
        "remove": _remove,
        "query": _query,
    }
