"""全量 A 股批量采集脚本。

用法：
  uv run python scripts/full_collect.py                         # 默认批量模式，最新报告期
  uv run python scripts/full_collect.py --period 20260331        # 指定报告期
  uv run python scripts/full_collect.py --mode per-stock         # 降级为逐股模式（慢）
  uv run python scripts/full_collect.py --resume                 # 断点续采（跳过已有股）

批量模式（默认）：VIP 接口 O(1) 拿全市场，4 次 API 调用，中配 < 5 分钟。
逐股模式：thread pool 逐股采集，20000+ 次调用，~40-100 分钟。
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import time
from pathlib import Path

from src.config import Settings, get_settings
from src.data.collect import CollectionPipeline, expected_latest_period
from src.data.contract import ALL_OUTPUT_COLUMNS
from src.data.output import (
    FIELD_CN,
    format_value,
    write_data_source_csv,
    write_features_csv,
)
from src.data.provider import TushareFetcher, TushareTokenError


def _read_existing_ts_codes(csv_path: Path) -> set[str]:
    """从已有 CSV 读取已完成的 ts_code 集合（用于断点续采）。"""
    if not csv_path.exists():
        return set()
    try:
        text = csv_path.read_text(encoding="utf-8-sig").lstrip("\ufeff").rstrip("\n")
    except OSError:
        return set()
    lines = text.split("\n")
    if len(lines) < 2:
        return set()
    headers = lines[0].split(",")
    try:
        ts_idx = headers.index("ts_code")
    except ValueError:
        return set()
    codes: set[str] = set()
    for line in lines[1:]:
        if not line.strip():
            continue
        cells = line.split(",")
        if len(cells) > ts_idx and cells[ts_idx].strip():
            codes.add(cells[ts_idx].strip())
    return codes


def _append_csv_rows(
    path: Path,
    features: list,
    headers: list[str],
    columns: tuple[str, ...],
    write_header: bool,
) -> int:
    """流式追加写 CSV 行，返回写入行数。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if write_header else "a"
    with path.open(mode, newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        if write_header:
            writer.writerow(headers)
        for feat in features:
            dumped = feat.model_dump() if hasattr(feat, "model_dump") else feat
            writer.writerow([format_value(c, dumped.get(c)) for c in columns])
    return len(features)


def main() -> None:
    parser = argparse.ArgumentParser(description="全量 A 股批量采集并落地 CSV")
    parser.add_argument(
        "--period",
        default=None,
        help="报告期 YYYYMMDD（默认自动推算最新）",
    )
    parser.add_argument(
        "--mode",
        choices=("batch", "per-stock"),
        default="batch",
        help="采集模式：batch=VIP批量O(1) / per-stock=逐股线程池O(n)（默认 batch）",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="断点续采：跳过 CSV 中已有的股票",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="输出目录（默认 data/fin/）",
    )
    args = parser.parse_args()

    settings = get_settings()

    period: str = args.period or expected_latest_period(_dt.date.today())
    date = _dt.date.today()
    stamp = date.strftime("%y%m%d")

    out_dir = Path(args.out_dir) if args.out_dir else settings.data_path("fin") / "full_collect"
    feat_path = out_dir / f"{stamp}.csv"
    src_path = out_dir / f"{stamp}-数据来源.csv"

    # 断点续采检查
    resume_codes: set[str] = set()
    if args.resume:
        resume_codes = _read_existing_ts_codes(feat_path)
        if resume_codes:
            print(f"断点续采：已有 {len(resume_codes)} 只股票，将跳过")

    # 连接 Tushare
    try:
        fetcher = TushareFetcher(settings)
    except TushareTokenError as exc:
        raise SystemExit(f"采集失败：{exc}（请在 .env 填入 TUSHARE_TOKEN）") from exc

    t_start = time.monotonic()

    # 全量采集前确保 SW 行业缓存已就绪（避免 run_batch 内按需查询拖慢）
    sw_cache = settings.data_root / "ref" / "sw_industry.csv"
    if not sw_cache.exists():
        print("SW 行业缓存不存在，正在生成（~11 分钟）...")
        fetcher.build_sw_cache()
        print("SW 行业缓存已生成")
    else:
        print(f"SW 行业缓存已存在：{sw_cache}")

    if args.mode == "batch":
        _run_batch(settings, fetcher, period, date, stamp, out_dir, feat_path, src_path)
    else:
        _run_per_stock(
            settings,
            fetcher,
            period,
            date,
            stamp,
            out_dir,
            feat_path,
            src_path,
            resume_codes,
        )

    elapsed = time.monotonic() - t_start
    print(f"总耗时：{elapsed:.1f} 秒")
    print(f"特征数据：{feat_path}")
    print(f"数据来源：{src_path}")


def _run_batch(
    settings: Settings,
    fetcher: TushareFetcher,
    period: str,
    date: _dt.date,
    stamp: str,
    out_dir: Path,
    feat_path: Path,
    src_path: Path,
) -> None:
    """批量模式：O(1) VIP 调用 + 流式写盘。"""
    print(f"模式：批量（VIP O(1)），报告期：{period}")

    pipe = CollectionPipeline(fetcher, settings=settings)
    try:
        result = pipe.run_batch(period=period)
    finally:
        pipe.close()

    # 流式写特征 CSV（分批 flush）
    headers = [FIELD_CN.get(c, c) for c in ALL_OUTPUT_COLUMNS]
    batch_size = settings.batch_size
    successes = result.successes
    total = len(successes)
    written = 0
    for i in range(0, total, batch_size):
        chunk = successes[i : i + batch_size]
        _append_csv_rows(feat_path, chunk, headers, ALL_OUTPUT_COLUMNS, write_header=(i == 0))
        written += len(chunk)
        pct = written * 100 // total if total else 0
        print(f"  写盘进度：{written}/{total} ({pct}%)")

    # 数据来源 CSV
    write_data_source_csv(src_path)

    # 失败清单
    if result.failures:
        fail_path = pipe.write_failures(result.failures, date=date, out_dir=out_dir)
        print(f"失败 {len(result.failures)} 股 → {fail_path}")

    print(f"批量采集完成：成功 {result.success_count} 股，失败 {result.failure_count} 股")


def _run_per_stock(
    settings: Settings,
    fetcher: TushareFetcher,
    period: str,
    date: _dt.date,
    stamp: str,
    out_dir: Path,
    feat_path: Path,
    src_path: Path,
    resume_codes: set[str],
) -> None:
    """逐股模式：线程池逐股采集，与 smoke_collect 同逻辑但覆盖全量。"""
    print(f"模式：逐股（线程池 O(n)），报告期：{period}")

    stocks = fetcher.fetch_stock_list()
    all_codes = [s.ts_code for s in stocks]
    if resume_codes:
        all_codes = [c for c in all_codes if c not in resume_codes]
        print(f"断点续采：跳过 {len(resume_codes)} 只，剩余 {len(all_codes)} 只")
    print(f"预计 API 调用：{len(all_codes) * 4} 次（每只 4 个接口）")

    pipe = CollectionPipeline(fetcher, settings=settings)
    try:
        result = pipe.run(period=period, codes=all_codes)
    finally:
        pipe.close()

    # 合并已有数据
    if resume_codes and feat_path.exists():
        pass  # 旧数据已保留在 CSV 中，后续追加新行

    # 写盘：如果断点续采，读取已有 CSV 内容
    if resume_codes and feat_path.exists():
        old_text = feat_path.read_text(encoding="utf-8-sig").rstrip("\n")
        feat_path.write_text(old_text + "\n", encoding="utf-8-sig")  # 保留旧数据
        # 追加新行
        headers = [FIELD_CN.get(c, c) for c in ALL_OUTPUT_COLUMNS]
        _append_csv_rows(feat_path, result.successes, headers, ALL_OUTPUT_COLUMNS, write_header=False)
    else:
        write_features_csv(result.successes, feat_path)

    write_data_source_csv(src_path)

    if result.failures:
        fail_path = pipe.write_failures(result.failures, date=date, out_dir=out_dir)
        print(f"失败 {len(result.failures)} 股 → {fail_path}")

    print(
        f"逐股采集完成：成功 {result.success_count} 股（缓存命中 {result.cached_hits}），失败 {result.failure_count} 股"
    )


if __name__ == "__main__":
    main()
