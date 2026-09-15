"""微信指令路由：白名单、群聊忽略、工具映射、长文分片。"""

from __future__ import annotations

from src.config import Settings
from src.wechat.router import (
    Incoming,
    handle_incoming,
    normalize_ts_code,
    parse_command,
    split_message,
)


def _settings(**overrides: object) -> Settings:
    values = {"wechat_allowed_users": "", "wechat_max_message_chars": 8}
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_parse_commands() -> None:
    assert parse_command("帮助").name == "help"
    assert parse_command("状态").name == "status"
    assert parse_command("报告").name == "report"
    assert parse_command("更新").name == "update"
    assert parse_command("持仓").name == "holdings"
    assert parse_command("加仓 600519").code == "600519.SH"
    assert parse_command("减仓 600519.SH").name == "remove"
    assert parse_command("查 600519").name == "query"


def test_normalize_ts_code() -> None:
    assert normalize_ts_code("600519") == "600519.SH"
    assert normalize_ts_code("000001") == "000001.SZ"


def test_ignore_group_and_non_whitelist() -> None:
    settings = _settings(wechat_allowed_users="owner")
    tools = {
        "status": lambda: "status-ok",
        "report": lambda: "report-ok",
        "update": lambda: "update-ok",
        "holdings": lambda: "hold-ok",
        "add": lambda code: f"add:{code}",
        "remove": lambda code: f"remove:{code}",
        "query": lambda code: f"query:{code}",
    }
    grouped = Incoming(sender="owner", text="帮助", group_id="g1", context_token="c")
    assert handle_incoming(grouped, settings, owner_id="owner", tools=tools) is None
    stranger = Incoming(sender="other", text="帮助", group_id="", context_token="c")
    assert handle_incoming(stranger, settings, owner_id="owner", tools=tools) is None


def test_route_calls_tools() -> None:
    calls: list[str] = []
    tools = {
        "status": lambda: calls.append("status") or "状态摘要",
        "report": lambda: calls.append("report") or "报告摘要",
        "update": lambda: calls.append("update") or "已更新",
        "holdings": lambda: calls.append("holdings") or "空仓",
        "add": lambda code: calls.append(f"add:{code}") or "已加仓",
        "remove": lambda code: calls.append(f"remove:{code}") or "已减仓",
        "query": lambda code: calls.append(f"query:{code}") or "茅台",
    }
    settings = _settings()
    owner = "me"
    mapping = [
        ("状态", "状态摘要"),
        ("报告", "报告摘要"),
        ("更新", "已更新"),
        ("持仓", "空仓"),
        ("加仓 600519", "已加仓"),
        ("减仓 600519", "已减仓"),
        ("查 600519", "茅台"),
    ]
    for text, expected in mapping:
        incoming = Incoming(sender=owner, text=text, group_id="", context_token="c")
        assert handle_incoming(incoming, settings, owner_id=owner, tools=tools) == expected
    assert calls == [
        "status",
        "report",
        "update",
        "holdings",
        "add:600519.SH",
        "remove:600519.SH",
        "query:600519.SH",
    ]


def test_help_and_split_by_limit() -> None:
    settings = _settings()
    incoming = Incoming(sender="me", text="帮助", group_id="", context_token="c")
    reply = handle_incoming(incoming, settings, owner_id="me", tools={})
    assert reply is not None
    assert "状态" in reply
    chunks = split_message("abcdefghij", 4)
    assert chunks == ["abcd", "efgh", "ij"]
    assert all(len(chunk) <= 4 for chunk in chunks)
