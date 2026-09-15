"""default_tools：报告 / 摘要只读已有 TopN Markdown 并落盘；锐评才调用 run_report。"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config import Settings
from src.reports.reporting import OUTPUT_HEADERS_CN, TOP_N
from src.tools import EXIT_OK, ToolError
from src.wechat.actions import default_tools


def _settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, data_dir=str(tmp_path), llm_provider="deepseek")


def test_report_without_file(tmp_path: Path) -> None:
    reply = default_tools(_settings(tmp_path))["report"]()
    assert "无报告" in reply


def test_report_writes_markdown_and_returns_full_text(tmp_path: Path) -> None:
    report_dir = tmp_path / "fin" / "full_report"
    report_dir.mkdir(parents=True)
    csv_path = report_dir / "260915.csv"
    csv_path.write_text(
        "股票代码,股票名称,公司类型,行业分类,核心亮点,成长性,稳健性,回报性,综合分,评级,操作建议,风险提示,点评\n"
        "000807,云铝股份,现金牛,周期资源,营收同比+20.3%,8,10,10,9.5,皇冠明珠,重仓买入,价格波动,盯住周期\n",
        encoding="utf-8-sig",
    )
    reply = default_tools(_settings(tmp_path))["report"]()
    md_path = report_dir / "260915.md"
    assert md_path.exists()
    assert reply.startswith(f"# 荐股 Top{TOP_N} · 260915")
    assert "云铝股份" in reply
    assert "营收同比+20.3%" in reply
    assert md_path.read_text(encoding="utf-8") == reply


def test_report_keeps_top_n_and_writes_markdown(tmp_path: Path) -> None:
    report_dir = tmp_path / "fin" / "full_report"
    report_dir.mkdir(parents=True)
    header = ",".join(OUTPUT_HEADERS_CN)
    lines = [header]
    for index in range(1, TOP_N + 6):
        lines.append(
            f"{index:06d},公司{index},现金牛,大消费,亮点{index},8,9,10,8.5,皇冠明珠,重仓买入,风险{index},点评{index}"
        )
    (report_dir / "260915.csv").write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    reply = default_tools(_settings(tmp_path))["report"]()
    md_path = report_dir / "260915.md"
    assert md_path.exists()
    assert f"## {TOP_N}. 公司{TOP_N}（{TOP_N:06d}）" in reply
    assert f"公司{TOP_N + 1}" not in reply
    assert md_path.read_text(encoding="utf-8") == reply


def test_generate_calls_report_then_reads_markdown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, object] = {}

    def fake_report(provider: str, model: str | None, **kwargs: object) -> int:
        called["provider"] = provider
        called["quiet"] = kwargs.get("quiet")
        return EXIT_OK

    monkeypatch.setattr("src.wechat.actions.run_report", fake_report)
    tools = default_tools(_settings(tmp_path))
    assert "无报告" in tools["generate"]()
    assert called == {"provider": "deepseek", "quiet": True}


def test_update_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.wechat.actions.run_collect",
        lambda params, settings: (EXIT_OK, {"data": {"skipped": True, "period": "20241231"}}),
    )
    assert "仍新鲜" in default_tools(_settings(tmp_path))["update"]()


def test_scores_tool_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_params: object, _settings: object) -> tuple[int, dict]:
        raise ToolError("无采集数据，请先运行 collect", 4)

    monkeypatch.setattr("src.wechat.actions.run_market_scores", boom)
    assert "无采集数据" in default_tools(_settings(tmp_path))["scores"]()
