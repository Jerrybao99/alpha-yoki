"""微信文本 → 结构化指令。先匹配锐评 / 强制采集，再匹配报告 / 更新。"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Command:
    name: str
    code: str = ""
    industry: str = ""
    rating: str = ""
    needs_confirm: bool = False
    trigger: str = ""
    summary: str = ""


YES = frozenset({"确认", "是", "对"})
NO = frozenset({"取消", "不", "否"})

_GENERATE = ("锐评", "重新生成")
_FORCE = ("全量采集", "强制重采", "强制采集")
_UPDATE = ("更新", "刷新", "补数据")
_SCORES = ("评分", "打分")
_REPORT = ("报告", "简报", "日报", "摘要")
_STATUS = ("状态", "新鲜度")
_HOLD = ("持仓",)
_HELP = ("帮助", "怎么用")

_ADD = re.compile(r"^(?:请|帮我)?(?:加仓|买入)\s*(\S+)$")
_REMOVE = re.compile(r"^(?:请|帮我)?(?:减仓|删除|移除)\s*(\S+)$")
_QUERY = re.compile(r"^(?:请|帮我)?(?:查|看看)\s*(\S+)$")
_ADD_BARE = re.compile(r"^(?:请|帮我)?(?:加仓|买入)$")
_REMOVE_BARE = re.compile(r"^(?:请|帮我)?(?:减仓|删除|移除)$")
_CODE_CORE = re.compile(r"^\d{6}(?:\.(?:SH|SZ|BJ))?$", re.I)


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


def _looks_like_code(token: str) -> bool:
    return bool(_CODE_CORE.match(token.strip()))


def _first(text: str, phrases: tuple[str, ...]) -> str | None:
    for phrase in phrases:
        if phrase in text:
            return phrase
    return None


def parse_command(text: str) -> Command:
    stripped = text.strip()
    added = _ADD.search(stripped)
    if added:
        code = normalize_ts_code(added.group(1))
        return Command(
            name="add",
            code=code,
            needs_confirm=True,
            trigger="加仓",
            summary=f"把 {code} 加入持仓",
        )
    if _ADD_BARE.fullmatch(stripped):
        return Command(name="hint", summary="加仓需要股票代码，例如：加仓 600519")

    removed = _REMOVE.search(stripped)
    if removed:
        code = normalize_ts_code(removed.group(1))
        return Command(
            name="remove",
            code=code,
            needs_confirm=True,
            trigger="减仓",
            summary=f"从持仓移除 {code}",
        )
    if _REMOVE_BARE.fullmatch(stripped):
        return Command(name="hint", summary="减仓需要股票代码，例如：减仓 600519")

    queried = _QUERY.search(stripped)
    if queried:
        token = queried.group(1)
        if stripped.startswith("查") or _looks_like_code(token):
            return Command(name="query", code=normalize_ts_code(token))

    hit = _first(stripped, _GENERATE)
    if hit:
        return Command(
            name="generate",
            needs_confirm=True,
            trigger=hit,
            summary="重新生成锐评（会调用 LLM）",
        )
    hit = _first(stripped, _FORCE)
    if hit:
        return Command(
            name="force",
            needs_confirm=True,
            trigger=hit,
            summary="强制全量采集，耗时较长",
        )
    hit = _first(stripped, _SCORES)
    if hit:
        return Command(
            name="scores",
            needs_confirm=True,
            trigger=hit,
            summary="对最新采集结果重新评分",
        )
    hit = _first(stripped, _UPDATE)
    if hit:
        return Command(
            name="update",
            needs_confirm=True,
            trigger=hit,
            summary="检查并补采过期数据",
        )
    if "筛选" in stripped:
        rest = stripped.split("筛选", 1)[1].strip()
        if not rest:
            return Command(name="hint", summary="筛选需要行业或评级，例如：筛选 白酒")
        parts = rest.split()
        return Command(name="screen", industry=parts[0], rating=parts[1] if len(parts) > 1 else "")
    if _first(stripped, _REPORT):
        return Command(name="report")
    if _first(stripped, _STATUS):
        return Command(name="status")
    if _first(stripped, _HOLD):
        return Command(name="holdings")
    if _first(stripped, _HELP) or stripped.lower() == "help":
        return Command(name="help")
    return Command(name="unknown")
