"""微信指令路由：白名单、只读直出、改数据确认、长文分片。"""

from __future__ import annotations

from src.config import Settings
from src.wechat.pending import MemoryPending
from src.wechat.router import Incoming, handle_incoming, parse_command, split_message


def _settings(**overrides: object) -> Settings:
    values = {"wechat_allowed_users": "", "wechat_max_message_chars": 8}
    values.update(overrides)
    return Settings(_env_file=None, **values)


def _tools(calls: list[str]) -> dict:
    return {
        "status": lambda: calls.append("status") or "状态摘要",
        "report": lambda: calls.append("report") or "报告摘要",
        "holdings": lambda: calls.append("holdings") or "空仓",
        "query": lambda code: calls.append(f"query:{code}") or "茅台",
        "screen": lambda industry, rating: calls.append(f"screen:{industry}:{rating}") or "筛到1只",
        "update": lambda: calls.append("update") or "已更新",
        "force": lambda: calls.append("force") or "已全量采集",
        "scores": lambda: calls.append("scores") or "已评分",
        "generate": lambda: calls.append("generate") or "已出报告",
        "add": lambda code: calls.append(f"add:{code}") or "已加仓",
        "remove": lambda code: calls.append(f"remove:{code}") or "已减仓",
    }


def test_parse_legacy_exact_commands() -> None:
    assert parse_command("帮助").name == "help"
    assert parse_command("状态").name == "status"
    assert parse_command("报告").name == "report"
    assert parse_command("更新").name == "update"
    assert parse_command("持仓").name == "holdings"
    assert parse_command("加仓 600519").code == "600519.SH"
    assert parse_command("减仓 600519.SH").name == "remove"
    assert parse_command("查 600519").name == "query"


def test_ignore_group_and_non_whitelist() -> None:
    settings = _settings(wechat_allowed_users="owner")
    tools = _tools([])
    grouped = Incoming(sender="owner", text="帮助", group_id="g1", context_token="c")
    assert handle_incoming(grouped, settings, owner_id="owner", tools=tools) is None
    stranger = Incoming(sender="other", text="帮助", group_id="", context_token="c")
    assert handle_incoming(stranger, settings, owner_id="owner", tools=tools) is None


def test_readonly_runs_immediately() -> None:
    calls: list[str] = []
    settings = _settings()
    pending = MemoryPending()
    mapping = [
        ("状态", "状态摘要"),
        ("给我一份报告", "报告摘要"),
        ("报告", "报告摘要"),
        ("持仓", "空仓"),
        ("查 600519", "茅台"),
        ("筛选 白酒", "筛到1只"),
    ]
    for text, expected in mapping:
        incoming = Incoming(sender="me", text=text, group_id="", context_token="c")
        assert handle_incoming(incoming, settings, owner_id="me", tools=_tools(calls), pending=pending) == expected
    assert calls == [
        "status",
        "report",
        "report",
        "holdings",
        "query:600519.SH",
        "screen:白酒:",
    ]


def test_mutating_asks_then_runs_on_confirm() -> None:
    calls: list[str] = []
    tools = _tools(calls)
    settings = _settings()
    pending = MemoryPending()
    owner = Incoming(sender="me", text="更新", group_id="", context_token="c")
    prompt = handle_incoming(owner, settings, owner_id="me", tools=tools, pending=pending)
    assert prompt is not None and "确认" in prompt and "更新" in prompt
    assert calls == []
    yes = Incoming(sender="me", text="确认", group_id="", context_token="c")
    assert handle_incoming(yes, settings, owner_id="me", tools=tools, pending=pending) == "已更新"
    assert calls == ["update"]


def test_generate_confirms_separately_from_report() -> None:
    calls: list[str] = []
    tools = _tools(calls)
    settings = _settings()
    pending = MemoryPending()
    first = Incoming(sender="me", text="锐评", group_id="", context_token="c")
    prompt = handle_incoming(first, settings, owner_id="me", tools=tools, pending=pending)
    assert prompt is not None and "LLM" in prompt
    assert calls == []
    yes = Incoming(sender="me", text="是", group_id="", context_token="c")
    assert handle_incoming(yes, settings, owner_id="me", tools=tools, pending=pending) == "已出报告"
    assert calls == ["generate"]


def test_cancel_and_replace_pending() -> None:
    calls: list[str] = []
    tools = _tools(calls)
    settings = _settings()
    pending = MemoryPending()
    handle_incoming(
        Incoming(sender="me", text="全量采集", group_id="", context_token="c"),
        settings,
        owner_id="me",
        tools=tools,
        pending=pending,
    )
    cancel = handle_incoming(
        Incoming(sender="me", text="取消", group_id="", context_token="c"),
        settings,
        owner_id="me",
        tools=tools,
        pending=pending,
    )
    assert cancel == "已取消"
    assert calls == []
    handle_incoming(
        Incoming(sender="me", text="加仓 600519", group_id="", context_token="c"),
        settings,
        owner_id="me",
        tools=tools,
        pending=pending,
    )
    status = handle_incoming(
        Incoming(sender="me", text="状态", group_id="", context_token="c"),
        settings,
        owner_id="me",
        tools=tools,
        pending=pending,
    )
    assert status == "状态摘要"
    assert pending.get("me") is None
    assert calls == ["status"]


def test_help_and_split_by_limit() -> None:
    settings = _settings()
    incoming = Incoming(sender="me", text="帮助", group_id="", context_token="c")
    reply = handle_incoming(incoming, settings, owner_id="me", tools={})
    assert reply is not None
    assert "报告" in reply
    assert "锐评" in reply
    assert "600519" in reply
    chunks = split_message("abcdefghij", 4)
    assert chunks == ["abcd", "efgh", "ij"]
    assert all(len(chunk) <= 4 for chunk in chunks)
