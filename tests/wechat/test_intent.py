"""微信自然语言意图：关键词命中、代码归一、报告与锐评拆分。"""

from __future__ import annotations

from src.wechat.intent import normalize_ts_code, parse_command


def test_readonly_keywords() -> None:
    assert parse_command("帮助").name == "help"
    assert parse_command("怎么用").name == "help"
    assert parse_command("状态").name == "status"
    assert parse_command("看看新鲜度").name == "status"
    assert parse_command("持仓").name == "holdings"
    assert parse_command("查 600519").name == "query"
    assert parse_command("查 600519").code == "600519.SH"
    assert parse_command("看看000001").code == "000001.SZ"
    assert parse_command("筛选 白酒").name == "screen"
    assert parse_command("筛选 白酒").industry == "白酒"
    assert parse_command("筛选 白酒 买入").rating == "买入"


def test_report_is_not_generate() -> None:
    for text in ("报告", "给我一份报告", "出报告", "简报", "日报", "发下摘要"):
        cmd = parse_command(text)
        assert cmd.name == "report"
        assert cmd.needs_confirm is False


def test_generate_is_review_only() -> None:
    for text in ("锐评", "重新生成"):
        cmd = parse_command(text)
        assert cmd.name == "generate"
        assert cmd.needs_confirm is True


def test_mutating_needs_confirm() -> None:
    assert parse_command("更新").needs_confirm is True
    assert parse_command("刷新数据").name == "update"
    assert parse_command("全量采集").name == "force"
    assert parse_command("强制重采").name == "force"
    assert parse_command("评分").name == "scores"
    assert parse_command("打分").name == "scores"
    add = parse_command("买入 600519")
    assert add.name == "add" and add.needs_confirm
    remove = parse_command("删除 600519.SH")
    assert remove.name == "remove" and remove.code == "600519.SH"


def test_add_without_code_is_hint() -> None:
    cmd = parse_command("加仓")
    assert cmd.name == "hint"
    assert "600519" in cmd.summary


def test_normalize_ts_code() -> None:
    assert normalize_ts_code("600519") == "600519.SH"
    assert normalize_ts_code("000001") == "000001.SZ"
    assert normalize_ts_code("430047") == "430047.BJ"
