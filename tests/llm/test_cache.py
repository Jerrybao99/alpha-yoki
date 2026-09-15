"""锐评本地缓存单测：指纹稳定性、读写往返、损坏条目视为未命中。"""

from __future__ import annotations

import json
from pathlib import Path

from src.llm.cache import FileReviewCache
from src.llm.contracts import Metric, ReviewFacts, ReviewResult, ReviewStatus


def _facts(**overrides) -> ReviewFacts:
    values = {
        "code": "000807",
        "name": "云铝股份",
        "industry": "周期资源",
        "company_type": "现金牛",
        "rating": "皇冠明珠",
        "advice": "重仓买入",
        "position": "10-20%",
        "composite": 9.5,
        "growth": 8,
        "stability": 10,
        "return_score": 10,
        "metrics": (Metric("or_yoy", "营收同比", 20.30, "%", signed=True),),
        "flags": (),
        "watch_variable": "产品价格周期与盈利弹性",
    }
    values.update(overrides)
    return ReviewFacts(**values)


def _result(**overrides) -> ReviewResult:
    values = {
        "highlight": "营收同比+20.3%，景气上行",
        "risk": "当前财务指标未发现重大风险信号",
        "comment": "周期资源现金牛，重点盯住产品价格周期与盈利弹性",
        "status": ReviewStatus.SUCCESS,
        "provider": "deepseek",
        "model": "deepseek-flash",
        "attempts": 1,
    }
    values.update(overrides)
    return ReviewResult(**values)


def test_key_is_deterministic_sha1_hex(tmp_path: Path) -> None:
    cache = FileReviewCache(tmp_path)
    first = cache.key(_facts(), "review-v1", "deepseek", "deepseek-flash")
    second = cache.key(_facts(), "review-v1", "deepseek", "deepseek-flash")
    assert first == second
    assert len(first) == 40 and int(first, 16) >= 0


def test_key_changes_with_facts_prompt_version_or_model(tmp_path: Path) -> None:
    cache = FileReviewCache(tmp_path)
    base = cache.key(_facts(), "review-v1", "deepseek", "deepseek-flash")
    assert base != cache.key(
        _facts(composite=9.4), "review-v1", "deepseek", "deepseek-flash"
    )
    assert base != cache.key(_facts(), "review-v2", "deepseek", "deepseek-flash")
    assert base != cache.key(_facts(), "review-v1", "glm", "glm-5.3-flash")


def test_put_then_get_roundtrip_as_utf8_json(tmp_path: Path) -> None:
    root = tmp_path / "review"
    cache = FileReviewCache(root)
    key = cache.key(_facts(), "review-v1", "deepseek", "deepseek-flash")
    cache.put(key, _result())

    path = root / f"{key}.json"
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["highlight"] == "营收同比+20.3%，景气上行"
    assert "\\u" not in path.read_text(encoding="utf-8")

    loaded = cache.get(key)
    assert loaded is not None
    assert (loaded.highlight, loaded.risk, loaded.comment) == (
        _result().highlight,
        _result().risk,
        _result().comment,
    )
    assert loaded.provider == "deepseek" and loaded.model == "deepseek-flash"
    assert loaded.status is ReviewStatus.SUCCESS


def test_get_missing_returns_none(tmp_path: Path) -> None:
    assert FileReviewCache(tmp_path).get("0" * 40) is None


def test_corrupt_or_malformed_entries_are_misses(tmp_path: Path) -> None:
    cache = FileReviewCache(tmp_path)
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "list.json").write_text("[1, 2]", encoding="utf-8")
    (tmp_path / "partial.json").write_text(
        '{"highlight": "只有一段"}', encoding="utf-8"
    )
    assert cache.get("bad") is None
    assert cache.get("list") is None
    assert cache.get("partial") is None


def test_root_is_created_lazily_on_put(tmp_path: Path) -> None:
    root = tmp_path / "nested" / "review"
    cache = FileReviewCache(root)
    assert not root.exists()
    cache.put("k", _result())
    assert (root / "k.json").exists()
