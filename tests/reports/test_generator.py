"""Top20 生成编排单测：一股一调用、三列由 ReviewResult 填充、Provider 失效仍产出 13 列。"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from src.config import Settings
from src.llm.client import LLMResponse
from src.llm.contracts import ReviewStatus
from src.llm.validate import LIMITS
from src.reports.generator import build_top20, select_top
from src.reports.reporting import OUTPUT_HEADERS_CN, write_recommend_csv

_HEADER = (
    "股票代码,股票名称,行业分类,成长性,稳健性,资金回报,综合分,评级,"
    "营业收入同比增长率,归属母公司股东的净利润同比增长率,销售毛利率,"
    "资产负债率,流动比率,净资产收益率\n"
)
_MOUTAI = "600519.SH,贵州茅台,大消费,8,8,8,8.0,⭐ 优秀白马,20.00%,18.00%,90.00%,20.00%,3.00倍,18.00%\n"
_BANK = "600000.SH,浦发银行,证券金融,6,8,8,7.4,⭐ 优秀白马,5.00%,4.00%,,92.00%,,10.00%\n"

GOOD_MOUTAI = json.dumps(
    {
        "highlight": "营收同比+20.0%，毛利率90.0%，扩张与溢价并存",
        "risk": "当前财务指标未发现重大风险信号",
        "comment": "大消费千里马，重点盯住增速能否延续",
    },
    ensure_ascii=False,
)


class _FakeClient:
    def __init__(self, content: str | Exception = GOOD_MOUTAI) -> None:
        self.spec = SimpleNamespace(name="deepseek", model="fake-model")
        self.calls: list[dict] = []
        self._content = content

    def chat_completion(self, **kwargs) -> LLMResponse:
        self.calls.append(kwargs)
        if isinstance(self._content, Exception):
            raise self._content
        return LLMResponse(content=self._content, model="fake-model", input_tokens=10, output_tokens=5)


def _settings(tmp_path: Path, **overrides) -> Settings:
    values = {"data_dir": str(tmp_path / "data"), "review_max_retries": 0}
    values.update(overrides)
    return Settings(_env_file=None, **values)


def _scoring_csv(tmp_path: Path, *rows: str) -> Path:
    path = tmp_path / "260915.csv"
    path.write_text(_HEADER + "".join(rows), encoding="utf-8-sig")
    return path


def test_select_top_orders_by_composite_and_skips_unscored(tmp_path: Path) -> None:
    csv_path = _scoring_csv(
        tmp_path,
        _BANK,
        _MOUTAI,
        "000001.SZ,无分股,大消费,,,,,,1.00%,1.00%,1.00%,1.00%,1.00倍,1.00%\n",
    )
    top = select_top(csv_path)
    assert [c.features.name for c in top] == ["贵州茅台", "浦发银行"]
    assert top[0].composite == 8.0


def test_select_top_prefers_raw_over_human(tmp_path: Path) -> None:
    """同日 raw 存在时按 raw 综合分排序，忽略人读 CSV。"""
    from src.data.store import raw_path, write_raw_csv

    csv_path = _scoring_csv(tmp_path, _BANK, _MOUTAI)
    write_raw_csv(
        [
            {
                "ts_code": "600000.SH",
                "name": "浦发银行",
                "industry": "证券金融",
                "综合分": 6.0,
                "成长性": 6,
                "稳健性": 8,
                "资金回报": 8,
                "评级": "⭐ 优秀白马",
            },
            {
                "ts_code": "600519.SH",
                "name": "贵州茅台",
                "industry": "大消费",
                "综合分": 9.0,
                "成长性": 9,
                "稳健性": 8,
                "资金回报": 8,
                "评级": "👑 皇冠明珠",
            },
        ],
        raw_path(csv_path.parent, csv_path.stem),
        ("ts_code", "name", "industry", "综合分", "成长性", "稳健性", "资金回报", "评级"),
    )
    top = select_top(csv_path)
    assert top[0].features.name == "贵州茅台"
    assert top[0].composite == 9.0


def test_build_top20_one_call_per_stock_fills_three_columns(tmp_path: Path) -> None:
    client = _FakeClient()
    result = build_top20(
        _scoring_csv(tmp_path, _MOUTAI),
        client=client,  # type: ignore[arg-type]
        settings=_settings(tmp_path),
    )
    assert len(result.rows) == 1
    assert client.calls == [client.calls[0]] and len(client.calls) == 1
    assert client.calls[0]["json_mode"] is True
    assert client.calls[0]["reasoning"] is False

    row = result.rows[0]
    assert list(row) == OUTPUT_HEADERS_CN
    assert row["股票代码"] == "600519"
    assert row["公司类型"].endswith("千里马")
    assert row["操作建议"] == "分批建仓（5-10%）"
    assert row["核心亮点"] == "营收同比+20.0%，毛利率90.0%，扩张与溢价并存"
    assert row["风险提示"] == "当前财务指标未发现重大风险信号"
    assert row["点评"] == "大消费千里马，重点盯住增速能否延续"
    assert result.statuses == [ReviewStatus.SUCCESS.value]


def test_build_top20_degrades_to_rule_fallback_when_provider_fails(
    tmp_path: Path,
) -> None:
    client = _FakeClient(RuntimeError("network down"))
    result = build_top20(
        _scoring_csv(tmp_path, _MOUTAI, _BANK),
        client=client,  # type: ignore[arg-type]
        settings=_settings(tmp_path),
    )
    assert result.statuses == [ReviewStatus.FALLBACK.value] * 2
    for row in result.rows:
        for column, field in (
            ("核心亮点", "highlight"),
            ("风险提示", "risk"),
            ("点评", "comment"),
        ):
            assert row[column]
            assert len(row[column]) <= LIMITS[field][1]
    bank = result.rows[1]
    assert "资产负债率92.0%偏高" in bank["风险提示"]
    assert "成长性评分6分为短板" in bank["风险提示"]

    out = write_recommend_csv(result, tmp_path / "out.csv")
    header = out.read_text(encoding="utf-8-sig").splitlines()[0]
    assert header.count('"') == len(OUTPUT_HEADERS_CN) * 2


def test_build_top20_writes_cache_and_trace_under_data_dir(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    client = _FakeClient()
    build_top20(_scoring_csv(tmp_path, _MOUTAI), client=client, settings=settings)  # type: ignore[arg-type]

    cache_files = list((tmp_path / "data" / "cache" / "review").glob("*.json"))
    trace_files = list((tmp_path / "data" / "monitor").glob("review-*.jsonl"))
    assert len(cache_files) == 1
    assert len(trace_files) == 1
    record = json.loads(trace_files[0].read_text(encoding="utf-8").splitlines()[0])
    assert record["status"] == "success" and record["code"] == "600519"

    second = _FakeClient()
    result = build_top20(_scoring_csv(tmp_path, _MOUTAI), client=second, settings=settings)  # type: ignore[arg-type]
    assert second.calls == []
    assert result.statuses == [ReviewStatus.CACHE_HIT.value]


def test_build_top20_can_disable_cache(tmp_path: Path) -> None:
    settings = _settings(tmp_path, review_cache_enabled=False)
    build_top20(_scoring_csv(tmp_path, _MOUTAI), client=_FakeClient(), settings=settings)  # type: ignore[arg-type]
    assert not (tmp_path / "data" / "cache" / "review").exists()


def test_build_top20_prints_status_summary(tmp_path: Path, capsys) -> None:
    build_top20(
        _scoring_csv(tmp_path, _MOUTAI),
        client=_FakeClient(),  # type: ignore[arg-type]
        settings=_settings(tmp_path),
    )
    output = capsys.readouterr().out
    assert "[ 1/1] 贵州茅台 | success" in output
    assert "锐评状态：success=1" in output
