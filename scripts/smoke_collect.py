"""随机 N 股冒烟采集脚本。随机选股真实采集（最新报告期），落地两张 CSV 到 data/test/。
用法：uv run python scripts/smoke_collect.py --sample 5。
"""

from __future__ import annotations

import argparse
import datetime as _dt
import random
from pathlib import Path

from src.config import Settings, get_settings
from src.data.collect import CollectionPipeline
from src.data.provider import BaseFetcher, TushareFetcher, TushareTokenError
from src.data.reports import write_data_source_csv, write_features_csv


def run_smoke(
    fetcher: BaseFetcher,
    settings: Settings,
    sample: int,
    out_dir: Path,
    date: _dt.date | None = None,
    *,
    seed: int = 42,
) -> tuple[Path, Path, int, int]:
    """执行冒烟采集。返回 (特征csv路径, 数据来源csv路径, 成功数, 失败数)。

    供脚本 main() 与集成测试复用；测试可注入 mock fetcher 与 tmp 目录。
    """
    date = date or _dt.date.today()
    stamp = date.strftime("%y%m%d")
    out_dir.mkdir(parents=True, exist_ok=True)

    stocks = fetcher.fetch_stock_list()
    if not stocks:
        raise RuntimeError("股票清单为空，无法采样")
    k = min(sample, len(stocks))
    rng = random.Random(seed)
    picked = rng.sample(stocks, k)
    codes = [s.ts_code for s in picked]
    print(f"随机抽取 {k} 股：{codes}")

    pipe = CollectionPipeline(fetcher, settings=settings)
    try:
        result = pipe.run(codes=codes)
    finally:
        pipe.close()

    feat_path = write_features_csv(result.successes, out_dir / f"{stamp}.csv")
    src_path = write_data_source_csv(out_dir / f"{stamp}-数据来源.csv")
    if result.failures:
        print(f"失败 {len(result.failures)} 股：{[f.ts_code for f in result.failures]}")
    return feat_path, src_path, result.success_count, result.failure_count


def main() -> None:
    parser = argparse.ArgumentParser(description="随机 N 股冒烟采集并落地 CSV")
    parser.add_argument(
        "--sample", type=int, default=5, help="随机采样股票数（默认 5）"
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="随机种子（默认 42，便于复现）"
    )
    args = parser.parse_args()

    settings = get_settings()
    try:
        fetcher = TushareFetcher(settings)
    except TushareTokenError as exc:
        raise SystemExit(f"采集失败：{exc}（请在 .env 填入 TUSHARE_TOKEN）") from exc

    out_dir = settings.data_root / "test"
    feat_path, src_path, ok, fail = run_smoke(
        fetcher, settings, args.sample, out_dir, seed=args.seed
    )
    print(f"成功 {ok} 股，失败 {fail} 股")
    print(f"特征数据：{feat_path}")
    print(f"数据来源：{src_path}")


if __name__ == "__main__":
    main()
