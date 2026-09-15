"""collect / scores / screen：采集、评分与本地筛选。"""

from __future__ import annotations

import argparse
import datetime as _dt
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict

from scripts.full_scores import SCORING_HEADERS, _write_scoring_csv, _write_veto_csv, run_scores
from src.config import Settings, get_settings
from src.data.collect import CollectionPipeline, expected_latest_period
from src.data.contract import ALL_OUTPUT_COLUMNS
from src.data.output import write_features_csv
from src.data.provider import TushareFetcher, TushareTokenError
from src.data.store import Kind, freshness, latest, load_features_prefer_raw, raw_path, write_raw_csv
from src.reports.reporting import load_score_rows_prefer_raw
from src.tools import EXIT_CONFIG, EXIT_DATA, EXIT_OK, ToolError, envelope

PipelineFactory = Callable[..., CollectionPipeline]


class CollectParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    update: bool = False
    force: bool = False
    codes: list[str] = []
    period: str | None = None


class ScoresParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codes: list[str] = []
    date: str | None = None


class ScreenParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    industry: str | None = None
    rating: str | None = None


def _stamp(today: _dt.date | None = None) -> str:
    return (today or _dt.date.today()).strftime("%y%m%d")


def _codes(raw: list[str]) -> list[str]:
    out: list[str] = []
    for item in raw:
        out.extend(part.strip() for part in item.split(",") if part.strip())
    return out


def run_collect(
    params: CollectParams,
    settings: Settings | None = None,
    *,
    pipeline_factory: PipelineFactory | None = None,
    today: _dt.date | None = None,
) -> tuple[int, dict[str, Any]]:
    resolved = settings or get_settings()
    day = today or _dt.date.today()
    codes = _codes(params.codes)
    if params.update and not params.force and not codes:
        info = freshness(Kind.COLLECT, day, settings=resolved)
        if not info.is_stale:
            return EXIT_OK, envelope(
                ok=True,
                command="collect",
                data={"skipped": True, "reason": "fresh", "period": info.period},
            )
    period = params.period or expected_latest_period(day)
    try:
        fetcher = TushareFetcher(resolved)
    except TushareTokenError as exc:
        raise ToolError(str(exc), EXIT_CONFIG) from exc
    factory = pipeline_factory or CollectionPipeline
    pipe = factory(fetcher, settings=resolved)
    try:
        if codes:
            result = pipe.run(period=period, codes=codes)
        else:
            result = pipe.run_batch(period=period)
    finally:
        pipe.close()
    out_dir = resolved.data_path("fin") / "full_collect"
    stamp = _stamp(day)
    human_name = f"{stamp}-单股.csv" if codes else f"{stamp}.csv"
    human = out_dir / human_name
    write_features_csv(result.successes, human)
    if not codes:
        write_raw_csv(
            [feat.model_dump() for feat in result.successes],
            raw_path(out_dir, stamp),
            ALL_OUTPUT_COLUMNS,
        )
    data = {
        "skipped": False,
        "period": period,
        "path": str(human),
        "success_count": result.success_count,
        "failure_count": result.failure_count,
    }
    return EXIT_OK, envelope(ok=True, command="collect", data=data)


def run_market_scores(params: ScoresParams, settings: Settings | None = None) -> tuple[int, dict[str, Any]]:
    resolved = settings or get_settings()
    collect_path = latest(Kind.COLLECT, settings=resolved)
    if collect_path is None:
        raise ToolError("无采集数据，请先运行 collect", EXIT_DATA)
    features = load_features_prefer_raw(collect_path)
    codes = _codes(params.codes)
    if codes:
        wanted = set(codes)
        features = [feat for feat in features if feat.ts_code in wanted]
    results, vetoes = run_scores(features)
    stamp = params.date or collect_path.stem
    out_dir = resolved.data_path("fin") / "full_scores"
    human = out_dir / f"{stamp}.csv"
    _write_scoring_csv(human, results, ALL_OUTPUT_COLUMNS)
    write_raw_csv(results, raw_path(out_dir, stamp), list(ALL_OUTPUT_COLUMNS) + list(SCORING_HEADERS))
    if vetoes:
        _write_veto_csv(out_dir / f"{stamp}-否决.csv", vetoes)
    return EXIT_OK, envelope(
        ok=True,
        command="scores",
        data={"path": str(human), "passed": len(results), "vetoed": len(vetoes)},
    )


def run_screen(params: ScreenParams, settings: Settings | None = None) -> tuple[int, dict[str, Any]]:
    resolved = settings or get_settings()
    path = latest(Kind.SCORES, settings=resolved)
    if path is None:
        raise ToolError("无评分数据，请先运行 scores", EXIT_DATA)
    rows = load_score_rows_prefer_raw(path)
    industry = (params.industry or "").strip()
    rating = (params.rating or "").strip()
    matched: list[dict[str, Any]] = []
    for row in rows:
        if industry and industry not in str(row.get("industry") or ""):
            continue
        if rating and rating not in str(row.get("评级") or ""):
            continue
        matched.append(row)
    return EXIT_OK, envelope(ok=True, command="screen", data={"count": len(matched), "items": matched})


def register(subparsers: argparse._SubParsersAction) -> None:
    collect = subparsers.add_parser("collect", help="采集财务特征（含股东户数）")
    collect.add_argument("--update", action="store_true", help="仅在过期或缺失时采集")
    collect.add_argument("--force", action="store_true", help="忽略新鲜度强制采集")
    collect.add_argument("--codes", nargs="+", default=[], metavar="TS_CODE", help="只采指定 ts_code")
    collect.add_argument("--period", default=None, metavar="YYYYMMDD", help="报告期，默认按披露日推算")
    collect.set_defaults(handler="collect")

    scores = subparsers.add_parser("scores", help="对最新采集 raw 评分")
    scores.add_argument("--codes", nargs="+", default=[], metavar="TS_CODE", help="只评指定 ts_code")
    scores.add_argument("--date", default=None, metavar="YYMMDD", help="产物日期戳，默认沿用采集文件名")
    scores.set_defaults(handler="scores")

    screen = subparsers.add_parser("screen", help="按行业/评级筛选最新评分")
    screen.add_argument("--industry", default=None, help="行业关键词，子串匹配")
    screen.add_argument("--rating", default=None, help="评级关键词，子串匹配")
    screen.set_defaults(handler="screen")
