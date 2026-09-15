"""股东户数：stk_holdernumber 分页合并，按 ts_code 取最新 end_date。接口失败不中断财务采集。"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from src.data.contract import StockFeatures

logger = logging.getLogger(__name__)

HOLDER_PAGE_LIMIT = 3000


class HolderApi(Protocol):
    def _call_paginated(self, interface_key: str, page_size: int, **params: Any) -> list[dict]: ...

    def _call(self, interface_key: str, fields: tuple[str, ...] | None = None, **params: Any) -> list[dict]: ...


def holder_page_size(vip_page_size: int) -> int:
    """stk_holdernumber 单次上限 3000。"""
    return min(HOLDER_PAGE_LIMIT, vip_page_size)


def _as_holder_num(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def pick_latest_holder_nums(records: list[dict[str, Any]]) -> dict[str, int]:
    """同一 ts_code 保留 end_date 最大的一条。"""
    best: dict[str, tuple[str, int]] = {}
    for row in records:
        ts_code = str(row.get("ts_code") or "")
        if not ts_code:
            continue
        num = _as_holder_num(row.get("holder_num"))
        if num is None:
            continue
        end_date = str(row.get("end_date") or "")
        prev = best.get(ts_code)
        if prev is None or end_date >= prev[0]:
            best[ts_code] = (end_date, num)
    return {ts_code: num for ts_code, (_end, num) in best.items()}


def fetch_holder_numbers(fetcher: HolderApi, period: str, page_size: int) -> dict[str, int]:
    """全市场按报告期截止日期分页拉取，合并为 ts_code → 户数。"""
    records = fetcher._call_paginated(
        "stk_holdernumber",
        holder_page_size(page_size),
        enddate=period,
    )
    return pick_latest_holder_nums(records)


def fetch_holder_number(fetcher: HolderApi, ts_code: str, period: str | None) -> int | None:
    """单股户数；指定期用 enddate，否则取 end_date 最大记录。"""
    params: dict[str, Any] = {"ts_code": ts_code}
    if period:
        params["enddate"] = period
    records = fetcher._call("stk_holdernumber", **params)
    return pick_latest_holder_nums(records).get(ts_code)


def merge_holder_numbers(features_map: dict[str, StockFeatures], holders: dict[str, int]) -> None:
    """就地写入已知户数，未知股保持 None。"""
    for ts_code, features in features_map.items():
        if ts_code in holders:
            features.holder_num = holders[ts_code]


def attach_holders_batch(
    fetcher: HolderApi,
    features_map: dict[str, StockFeatures],
    period: str,
    vip_page_size: int,
) -> None:
    """批量回填；接口失败只记 warning。"""
    try:
        holders = fetch_holder_numbers(fetcher, period, holder_page_size(vip_page_size))
        merge_holder_numbers(features_map, holders)
    except Exception as exc:  # noqa: BLE001
        logger.warning("股东户数批量采集失败，继续财务结果: %s", exc)


def attach_holder_one(fetcher: HolderApi, features: StockFeatures, ts_code: str, period: str | None) -> None:
    """单股回填；接口失败只记 warning。"""
    try:
        features.holder_num = fetch_holder_number(fetcher, ts_code, period)
    except Exception as exc:  # noqa: BLE001
        logger.warning("股东户数采集失败 %s: %s", ts_code, exc)
