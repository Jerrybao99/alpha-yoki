"""申万行业分类缓存生成脚本。

为全部 A 股查询 SW 五大类分类并落盘到 ``data/ref/sw_industry.csv``。
后续全量采集/评分/报告的行业权重匹配即可秒级命中。

用法：uv run python scripts/sw_industry.py
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.config import get_settings
from src.data.provider import TushareFetcher, TushareTokenError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    try:
        fetcher = TushareFetcher(settings)
    except TushareTokenError as exc:
        raise SystemExit(f"失败：{exc}（请在 .env 填入 TUSHARE_TOKEN）") from exc

    codes = [
        r["ts_code"]
        for r in fetcher._call("stock_basic", ("ts_code",), list_status="L")
    ]
    total = len(codes)
    logger.info("%d 只股票，开始查询行业分类（并发=%d）...", total, settings.concurrency)

    t0 = time.monotonic()
    cache: dict[str, str] = {}
    l2_names: dict[str, str] = {}
    workers = max(1, settings.concurrency)
    with ThreadPoolExecutor(max_workers=workers) as exe:
        futures = {exe.submit(fetcher._fetch_one_sw_category, c): c for c in codes}
        for i, fut in enumerate(as_completed(futures), start=1):
            tc = futures[fut]
            try:
                cat, l2 = fut.result()
                cache[tc] = cat
                l2_names[tc] = l2
            except Exception:
                cache[tc] = "未分类"
                l2_names[tc] = ""
            if i % 500 == 0:
                elapsed = time.monotonic() - t0
                logger.info("  进度: %d/%d (%.0fs)", i, total, elapsed)

    fetcher._save_sw_cache(cache, l2_names=l2_names)
    elapsed = time.monotonic() - t0
    classified = sum(1 for v in cache.values() if v != "未分类")
    logger.info(
        "完成: %d/%d 已分类 (%.0fs) → data/ref/sw_industry.csv",
        classified,
        total,
        elapsed,
    )


if __name__ == "__main__":
    main()
