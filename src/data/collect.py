"""采集编排：Cache（文件缓存 + TTL 过期）、Failure / CollectionResult 结果模型、
CollectionPipeline（逐股 run + 批量 run_batch，含线程池、SW 行业分类回填、失败落盘）、
expected_latest_period 报告期推算（按法定披露截止日）。"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.config import Settings, get_settings
from src.data.contract import StockFeatures, StockInfo
from src.data.output import to_output_row
from src.data.provider import BaseFetcher

logger = logging.getLogger(__name__)


class Cache:
    """本地文件缓存。disabled 时 get 永远返回 None、set 不写盘。

    ttl_seconds 仅对 ``period=None``（"最新"）缓存条目生效：超时即视为未命中，
    重新采集以获取新报告期；显式 period 的历史数据不可变，不受 TTL 约束。
    """

    def __init__(self, cache_dir: Path, enabled: bool = True, ttl_seconds: float | None = None) -> None:
        self.cache_dir = cache_dir
        self.enabled = enabled
        self.ttl_seconds = ttl_seconds
        if enabled:
            cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def key_for(ts_code: str, period: str | None) -> str:
        """缓存键：``features_{ts_code}_{period}``。period 为 None 记 ``latest``。"""
        return f"collect_fin_features_{ts_code}_{period or 'latest'}".replace("/", "_")

    def _path(self, ts_code: str, period: str | None) -> Path:
        return self.cache_dir / f"{self.key_for(ts_code, period)}.json"

    def get(self, ts_code: str, period: str | None) -> StockFeatures | None:
        """命中返回 StockFeatures，未命中/损坏/过期返回 None。"""
        if not self.enabled:
            return None
        path = self._path(ts_code, period)
        if not path.exists():
            return None
        if period is None and self.ttl_seconds is not None:
            age = time.time() - path.stat().st_mtime
            if age > self.ttl_seconds:
                return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        return StockFeatures(**data)

    def set(self, ts_code: str, period: str | None, features: StockFeatures) -> None:
        """写入缓存（disabled 时跳过）。"""
        if not self.enabled:
            return
        self._path(ts_code, period).write_text(
            json.dumps(features.model_dump(), ensure_ascii=False),
            encoding="utf-8",
        )


@dataclass
class Failure:
    """单股采集失败记录（审计可追溯）。"""

    ts_code: str
    name: str
    error: str


@dataclass
class CollectionResult:
    """采集结果：成功特征列表 + 失败清单 + 命中缓存数。"""

    successes: list[StockFeatures] = field(default_factory=list)
    failures: list[Failure] = field(default_factory=list)
    cached_hits: int = 0
    total: int = 0

    @property
    def success_count(self) -> int:
        return len(self.successes)

    @property
    def failure_count(self) -> int:
        return len(self.failures)


class CollectionPipeline:
    """采集编排器。executor 可注入便于单测（用顺序执行器避免真实线程）。"""

    def __init__(
        self,
        fetcher: BaseFetcher,
        settings: Settings | None = None,
        cache: Cache | None = None,
        executor: Any = None,
    ) -> None:
        self.fetcher = fetcher
        self.settings = settings or get_settings()
        self.cache = (
            cache
            if cache is not None
            else Cache(
                self.settings.data_root / "cache" / "fin",
                ttl_seconds=self.settings.cache_ttl_hours * 3600 if self.settings.cache_ttl_hours > 0 else None,
            )
        )
        self._owns_executor = executor is None
        self._executor = executor or ThreadPoolExecutor(max_workers=max(1, self.settings.concurrency))

    def run(self, period: str | None = None, codes: list[str] | None = None) -> CollectionResult:
        """执行采集。codes 非空时只采指定股票（冒烟测试用）。"""
        stocks = self.fetcher.fetch_stock_list()
        if codes:
            wanted = set(codes)
            stocks = [s for s in stocks if s.ts_code in wanted]
        if hasattr(self.fetcher, "_enrich_with_sw_category"):
            self.fetcher._enrich_with_sw_category(stocks)  # type: ignore[union-attr]
        result = CollectionResult(total=len(stocks))
        name_map = {s.ts_code: s.name for s in stocks}
        info_map = {s.ts_code: s for s in stocks}

        futures = {self._executor.submit(self._fetch_one, s.ts_code, period): s.ts_code for s in stocks}
        for fut in futures:
            ts_code = futures[fut]
            try:
                features, hit = fut.result()
            except Exception as exc:  # noqa: BLE001
                logger.warning("采集失败 %s: %s", ts_code, exc)
                result.failures.append(Failure(ts_code, name_map.get(ts_code, ""), str(exc)))
                continue
            if hit:
                result.cached_hits += 1
            if features is not None:
                self._enrich_with_stock_info(features, info_map.get(ts_code))
                result.successes.append(features)
            else:
                result.failures.append(Failure(ts_code, name_map.get(ts_code, ""), "无数据"))
        return result

    @staticmethod
    def _enrich_with_stock_info(features: StockFeatures, info: StockInfo | None) -> None:
        """回填 stock_basic 字段（symbol/name/industry）。"""
        if info is None:
            return
        if not features.symbol:
            features.symbol = info.symbol
        if not features.name:
            features.name = info.name
        if not features.industry:
            features.industry = info.industry

    def _fetch_one(self, ts_code: str, period: str | None) -> tuple[StockFeatures | None, bool]:
        """采集单股：先查缓存，未命中再调接口并回写缓存。"""
        cached = self.cache.get(ts_code, period)
        if cached is not None:
            return cached, True
        features = self.fetcher.fetch_financials(ts_code, period)
        if features is None:
            return None, False
        self.cache.set(ts_code, period, features)
        return features, False

    def run_batch(self, period: str | None = None) -> CollectionResult:
        """批量采集全市场财务数据。

        用 ``fetch_financials_batch`` 一次调完 4 个 VIP 接口（O(1) 而非 O(n)），
        end_date 锁定 income 报告期，其余接口不覆盖。回填 stock_basic 字段与
        SW 行业分类后返回 CollectionResult。
        """
        fetcher: Any = self.fetcher

        if period is None:
            period = expected_latest_period(_dt.date.today())
            logger.info("未指定报告期，自动推算：%s", period)

        stable_period: str = period

        stocks = fetcher.fetch_stock_list()
        if hasattr(fetcher, "_enrich_with_sw_category"):
            fetcher._enrich_with_sw_category(stocks)
        info_map = {s.ts_code: s for s in stocks}

        logger.info("全量批量采集开始：%d 只股票 period=%s", len(stocks), stable_period)
        try:
            features_map = fetcher.fetch_financials_batch(stable_period)
        except NotImplementedError as exc:
            raise RuntimeError("当前 Fetcher 不支持批量采集，请用 CollectionPipeline.run() 逐股模式") from exc

        result = CollectionResult(total=len(stocks))
        for s in stocks:
            feat = features_map.get(s.ts_code)
            if feat is None:
                result.failures.append(Failure(s.ts_code, s.name, "批次结果中无此股"))
                continue
            self._enrich_with_stock_info(feat, info_map.get(s.ts_code))
            result.successes.append(feat)

        logger.info(
            "全量批量采集完成：成功 %d 失败 %d（%d 只来自股票清单）",
            result.success_count,
            result.failure_count,
            len(stocks),
        )
        return result

    def to_rows(self, result: CollectionResult) -> list[dict[str, Any]]:
        """把成功特征标准化为输出行（OUTPUT_COLUMNS 字段顺序 + 百分比格式化）。"""
        return [to_output_row(f) for f in result.successes]

    def write_failures(
        self,
        failures: list[Failure],
        date: _dt.date | None = None,
        *,
        out_dir: Path | None = None,
    ) -> Path:
        """失败清单落盘（审计可追溯）。"""
        date = date or _dt.date.today()
        base = out_dir or self.settings.data_path("fin")
        out = base / f"{date.strftime('%y%m%d')}-失败.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.writer(fh, lineterminator="\n")
            writer.writerow(["ts_code", "name", "error"])
            for f in failures:
                writer.writerow([f.ts_code, f.name, f.error])
        return out

    def close(self) -> None:
        if self._owns_executor:
            self._executor.shutdown(wait=False)

    def __enter__(self) -> CollectionPipeline:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


# ===== 报告期推算 =====
_DEADLINES: dict[str, _dt.date] = {
    "0331": _dt.date(2000, 4, 30),
    "0630": _dt.date(2000, 8, 31),
    "0930": _dt.date(2000, 10, 31),
    "1231": _dt.date(2001, 4, 30),
}


def _deadline(period: str) -> _dt.date:
    y = int(period[:4])
    md = period[4:]
    base = _DEADLINES[md]
    if md == "1231":
        return base.replace(year=y + 1)
    return base.replace(year=y)


def expected_latest_period(today: _dt.date) -> str:
    """返回今天理应已披露的最新报告期（YYYYMMDD）。"""
    candidates: list[str] = []
    for y in (today.year, today.year - 1):
        for md in _DEADLINES:
            p = f"{y}{md}"
            if _deadline(p) <= today:
                candidates.append(p)
    return max(candidates) if candidates else f"{today.year - 1}0930"
