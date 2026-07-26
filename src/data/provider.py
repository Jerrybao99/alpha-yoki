"""数据获取：BaseFetcher 抽象、TushareInterface 接口注册表（20 个，vip 优先）、
RateLimiter 滑动窗口限流、TushareFetcher（逐股 fetch_financials + 批量 fetch_financials_batch）、
申万二级行业→五大类映射（~130 个行业，自动剥离罗马数字后缀）。"""

from __future__ import annotations

import csv
import logging
import math
import time
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tushare as ts

from src.config import Settings, get_settings
from src.data.contract import (
    STOCK_BASIC_FIELDS,
    StockFeatures,
    StockInfo,
)


@dataclass(frozen=True)
class TushareInterface:
    """Tushare 接口描述。

    Attributes:
        api_name: 常规接口名（2000 积分可调，按 ts_code 逐股取）。
        vip_api_name: vip 高级接口名（5000 积分，按 period 批量取全市场；无 vip 则同 api_name）。
        doc_url: 接口文档 URL。
        min_points: 最低积分要求。
        description: 接口中文描述。
    """

    api_name: str
    vip_api_name: str
    doc_url: str
    min_points: int
    description: str


_DOC = "https://tushare.pro/document/2?doc_id="

# ===== 5000 积分可调用接口注册表（优先 vip）=====
# key 为业务别名，与 REQUIREMENT_ALIGNMENT.endpoint 对齐。
TUSHARE_INTERFACES: dict[str, TushareInterface] = {
    "stock_basic": TushareInterface(
        "stock_basic", "stock_basic", _DOC + "25", 2000, "股票列表（基础信息）"
    ),
    "income": TushareInterface(
        "income", "income_vip", _DOC + "33", 2000, "利润表（vip 按报告期取全市场）"
    ),
    "balancesheet": TushareInterface(
        "balancesheet",
        "balancesheet_vip",
        _DOC + "36",
        2000,
        "资产负债表（vip 按报告期取全市场）",
    ),
    "cashflow": TushareInterface(
        "cashflow",
        "cashflow_vip",
        _DOC + "44",
        2000,
        "现金流量表（vip 按报告期取全市场）",
    ),
    "fina_indicator": TushareInterface(
        "fina_indicator",
        "fina_indicator_vip",
        _DOC + "79",
        2000,
        "财务指标数据（vip 按报告期取全市场）",
    ),
    "daily_basic": TushareInterface(
        "daily_basic",
        "daily_basic",
        _DOC + "32",
        2000,
        "每日指标（5000 积分无总量限制）",
    ),
    "fina_audit": TushareInterface(
        "fina_audit", "fina_audit", _DOC + "80", 2000, "财务审计意见"
    ),
    "pledge_stat": TushareInterface(
        "pledge_stat", "pledge_stat", _DOC + "110", 2000, "股权质押统计数据"
    ),
    "top10_holders": TushareInterface(
        "top10_holders", "top10_holders", _DOC + "61", 2000, "前十大股东"
    ),
    "top10_floatholders": TushareInterface(
        "top10_floatholders", "top10_floatholders", _DOC + "62", 2000, "前十大流通股东"
    ),
    "forecast": TushareInterface(
        "forecast",
        "forecast_vip",
        _DOC + "45",
        2000,
        "业绩预告（vip 按报告期取全市场）",
    ),
    "express": TushareInterface(
        "express", "express_vip", _DOC + "46", 2000, "业绩快报（vip 按报告期取全市场）"
    ),
    "fina_mainbz": TushareInterface(
        "fina_mainbz",
        "fina_mainbz_vip",
        _DOC + "81",
        2000,
        "主营业务构成（vip 按报告期取全市场）",
    ),
    "disclosure_date": TushareInterface(
        "disclosure_date", "disclosure_date", _DOC + "162", 2000, "财报披露日期表"
    ),
    "trade_cal": TushareInterface(
        "trade_cal", "trade_cal", _DOC + "26", 2000, "交易日历"
    ),
    "stk_holdernumber": TushareInterface(
        "stk_holdernumber", "stk_holdernumber", _DOC + "166", 600, "股东人数"
    ),
    "stk_holdertrade": TushareInterface(
        "stk_holdertrade", "stk_holdertrade", _DOC + "175", 2000, "股东增减持"
    ),
    "share_float": TushareInterface(
        "share_float", "share_float", _DOC + "160", 120, "限售股解禁"
    ),
    "repurchase": TushareInterface(
        "repurchase", "repurchase", _DOC + "124", 2000, "股票回购"
    ),
    "index_member_all": TushareInterface(
        "index_member_all",
        "index_member_all",
        _DOC + "335",
        2000,
        "申万行业成分（分级）",
    ),
    # ===== 公募基金 / ETF（doc_id 见 Tushare ETF 专题）=====
    "fund_basic": TushareInterface(
        "fund_basic", "fund_basic", _DOC + "384", 2000, "基金/ETF 列表（基本信息）"
    ),
    "fund_daily": TushareInterface(
        "fund_daily", "fund_daily", _DOC + "127", 5000, "ETF 日线行情（逐股）"
    ),
    "fund_nav": TushareInterface(
        "fund_nav", "fund_nav", _DOC + "119", 2000, "基金净值"
    ),
    "fund_share": TushareInterface(
        "fund_share", "fund_share", _DOC + "384", 2000, "基金份额"
    ),
    "fund_portfolio": TushareInterface(
        "fund_portfolio", "fund_portfolio", _DOC + "121", 2000, "基金持仓"
    ),
    "fund_div": TushareInterface("fund_div", "fund_div", _DOC + "120", 400, "基金分红"),
    "fund_adj": TushareInterface(
        "fund_adj", "fund_adj", _DOC + "384", 2000, "ETF 复权因子"
    ),
}


def get_vip_api_name(key: str) -> str:
    """获取接口的 vip 高级接口名（无 vip 则返回常规接口名）。"""
    return TUSHARE_INTERFACES[key].vip_api_name


def get_doc_url(key: str) -> str:
    """获取接口的文档 URL。"""
    return TUSHARE_INTERFACES[key].doc_url


class BaseFetcher(ABC):
    """数据源适配器抽象基类。

    约束：
    - 业务代码只依赖本抽象，禁止直接 import 具体数据源 SDK（FR-DATA-01）。
    - 实现类负责限流 / 重试 / 缓存（FR-DATA-06/07），本接口只声明能力。
    - 主键统一用 ts_code（如 "600000.SH"），与 Tushare 接口一致。
    """

    @abstractmethod
    def fetch_stock_list(self) -> list[StockInfo]:
        """读取全部 A 股上市公司清单（FR-DATA-02，来源 stock_basic）。

        返回每只股票的 ts_code、code(=symbol)、name、industry。
        """

    @abstractmethod
    def fetch_financials(
        self, ts_code: str, period: str | None = None
    ) -> StockFeatures | None:
        """按 §8.1 需求采集单股财务数据（FR-DATA-03）。

        实现需聚合 income / balancesheet / cashflow / fina_indicator / daily_basic
        多个接口的真实字段，按 OUTPUT_COLUMNS 输出；§8.1 中的计算型需求
        （股东权益比/主营利润率等）不在此采集，留给评分纯函数计算。
        period=None 表示取最新报告期（FR-DATA-04）。

        Args:
            ts_code: Tushare 股票代码，如 "600000.SH"。
            period: 财报所属期间，如 "20251231"；None 取最新报告期。

        Returns:
            该股票的特征数据（字段名即 Tushare 真实字段名，数据为真实值）。
        """

    def fetch_financials_batch(self, period: str) -> dict[str, StockFeatures]:
        """批量采集全市场财务数据（可选覆写，VIP O(1) 接口）。
        基类默认抛 NotImplementedError，子类如有批量能力可覆写。
        """
        raise NotImplementedError


# 指数退避基数（秒）：1, 2, 4
BACKOFF_BASE_SECONDS = 1.0
DEFAULT_MAX_RETRIES = 3
RATE_WINDOW_SECONDS = 60.0


class TushareTokenError(RuntimeError):
    """TUSHARE_TOKEN 缺失或无效。"""


class TushareApiError(RuntimeError):
    """Tushare 接口调用失败（重试耗尽）。"""


class RateLimiter:
    """滑动窗口限流器：每 ``window`` 秒最多 ``limit`` 次调用，超额则阻塞到窗口腾位。

    clock/sleep 可注入，便于单测（FR-DATA-06）。
    """

    def __init__(
        self,
        limit: int,
        *,
        window: float = RATE_WINDOW_SECONDS,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.limit = max(1, limit)
        self.window = window
        self._sleep = sleep
        self._clock = clock
        self._stamps: deque[float] = deque()

    def acquire(self) -> None:
        """获取一个调用名额，必要时 sleep 等待。"""
        now = self._clock()
        self._evict(now)
        if len(self._stamps) >= self.limit:
            wait = self.window - (now - self._stamps[0])
            if wait > 0:
                self._sleep(wait)
                now = self._clock()  # sleep 后重新取时间
                self._evict(now)
        self._stamps.append(now)

    def _evict(self, now: float) -> None:
        while self._stamps and now - self._stamps[0] >= self.window:
            self._stamps.popleft()


class TushareFetcher(BaseFetcher):
    """Tushare 适配器：限流 + 指数退避重试 + vip 接口优先。"""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        pro: Any | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        self.settings = settings or get_settings()
        self._max_retries = max(0, max_retries)
        self._sleep = sleep
        self._clock = clock
        self._limiter = RateLimiter(
            self.settings.tushare_rate_limit, sleep=sleep, clock=clock
        )
        # pro 由外部注入（测试）或由 token 初始化（生产）；token 检查仅在真初始化时生效。
        if pro is not None:
            self._pro = pro
        else:
            token = self.settings.tushare_token.strip()
            if not token:
                raise TushareTokenError(
                    "未配置 TUSHARE_TOKEN，请在 .env 填入（注册见 https://tushare.pro ）。"
                )
            ts.set_token(token)
            self._pro = ts.pro_api()

    # ===== 核心调用：限流 + 指数退避重试 =====
    def _call(
        self, interface_key: str, fields: tuple[str, ...] | None = None, **params: Any
    ) -> list[dict]:
        """调用某接口，返回记录列表。vip 接口自动取 vip_api_name。
        fields 为空时调取接口全部字段（默认列）。"""
        api_name = get_vip_api_name(interface_key)
        if fields:
            return self._call_raw(api_name, fields=",".join(fields), **params)
        return self._call_raw(api_name, **params)

    def _call_raw(self, api_name: str, **params: Any) -> list[dict]:
        """底层调用 Tushare API，限流 + 指数退避重试。"""
        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            self._limiter.acquire()
            try:
                df = self._pro.query(api_name, **params)
            except Exception as exc:
                last_exc = exc
                if attempt < self._max_retries:
                    self._sleep(BACKOFF_BASE_SECONDS * (2**attempt))
                    continue
                raise TushareApiError(
                    f"Tushare 调用失败（重试 {self._max_retries} 次仍报错）: {api_name} {params}"
                ) from exc
            return df.to_dict("records") if df is not None else []
        raise TushareApiError(f"Tushare 调用失败: {api_name} {params}") from last_exc

    def _call_no_fields(self, interface_key: str, **params: Any) -> list[dict]:
        """调用接口不传 fields（返回全部默认字段），限流 + 退避。"""
        return self._call_raw(get_vip_api_name(interface_key), **params)

    # ===== BaseFetcher 实现 =====
    def fetch_stock_list(self) -> list[StockInfo]:
        """读取全部 A 股上市公司清单，行业字段保留 stock_basic 原始值。
        SW 分类由 ``_enrich_with_sw_category`` 在后续按需调用。
        """
        records = self._call("stock_basic", STOCK_BASIC_FIELDS, list_status="L")
        return [
            StockInfo(
                ts_code=self._str(r.get("ts_code")),
                symbol=self._str(r.get("symbol")),
                name=self._str(r.get("name")),
                industry=self._str(r.get("industry")),
            )
            for r in records
        ]

    def fetch_financials(
        self, ts_code: str, period: str | None = None
    ) -> StockFeatures:
        """按 §8.1 聚合单股财务数据（FR-DATA-03/04），调取各接口全部字段。

        period=None 走 _latest 取各接口最新报告期；period 指定时合并该期所有记录
        （逐股 VIP 可能返回多条，后条非空值覆写前条），确保与 fetch_financials_batch 一致。
        """
        data: dict[str, Any] = {"ts_code": ts_code}
        fin_params: dict[str, Any] = {"ts_code": ts_code}
        explicit_period = period is not None
        if explicit_period:
            fin_params["period"] = period

        _no_end_date = {"end_date"}

        if explicit_period:
            records = self._call("income", **fin_params)
            for r in records:
                self._merge_non_none(data, self._clean_record(r))
        else:
            rec = self._latest(self._call("income", **fin_params), "end_date")
            data.update(self._clean_record(rec))

        for key in ("balancesheet", "cashflow", "fina_indicator"):
            if explicit_period:
                records = self._call(key, **fin_params)
                for r in records:
                    self._merge_non_none(
                        data, self._clean_record(r, exclude=_no_end_date)
                    )
            else:
                rec = self._latest(self._call(key, **fin_params), "end_date")
                data.update(self._clean_record(rec, exclude=_no_end_date))

        return StockFeatures(**{k: v for k, v in data.items()})

    # ===== 辅助 =====
    @staticmethod
    def _latest(records: list[dict] | None, date_field: str) -> dict | None:
        """从记录列表取 date_field 最大（最新）的一条；无日期则取首条。"""
        if not records:
            return None
        dated = [r for r in records if r.get(date_field)]
        if dated:
            return max(dated, key=lambda r: r[date_field])
        return records[0]

    @staticmethod
    def _clean_record(
        rec: dict | None,
        fields: tuple[str, ...] | None = None,
        *,
        exclude: set[str] | None = None,
    ) -> dict[str, Any]:
        """提取字段并把 NaN/None 归一化为 None。fields 为 None 时取 rec 全部字段。

        exclude 中的字段不写入返回字典（用于保护 income 确定的报告期 end_date 不被覆盖）。
        """
        out: dict[str, Any] = {}
        if not rec:
            return out
        exclude = exclude or set()
        keys = fields if fields is not None else tuple(rec.keys())
        for f in keys:
            if f in exclude:
                continue
            if f in rec:
                v = rec[f]
                if isinstance(v, float) and math.isnan(v):
                    v = None
                out[f] = v
        return out

    @staticmethod
    def _str(v: Any) -> str:
        """字符串字段归一化：None/NaN → 空串。"""
        if v is None:
            return ""
        if isinstance(v, float) and math.isnan(v):
            return ""
        return str(v)

    @staticmethod
    def _merge_non_none(target: dict[str, Any], source: dict[str, Any]) -> None:
        """将 source 中非 None 的键值合并到 target（None 值不覆写已有有效数据）。"""
        for k, v in source.items():
            if v is not None:
                target[k] = v

    # ===== 申万行业分类 =====
    _SW_MEMBER_FIELDS: tuple[str, ...] = (
        "ts_code",
        "l1_name",
        "l2_name",
        "l3_name",
        "is_new",
    )

    def _sw_cache_path(self) -> Path:
        return self.settings.data_root / "ref" / "sw_industry.csv"

    @staticmethod
    def _sw_name_to_category(rec: dict, default: str = "未分类") -> str:
        """从 index_member_all 记录中按 l2_name > l1_name > l3_name 优先级取分类。"""
        for key in ("l2_name", "l1_name", "l3_name"):
            name = str(rec.get(key, "")).strip()
            if name:
                cat = sw_l2_to_category(name)
                if cat != "未分类":
                    return cat
                # 对于一级/三级行业名也试映射（部分 SW L1/L3 名和 L2 名重叠）
        return default

    def _fetch_one_sw_category(self, ts_code: str) -> tuple[str, str]:
        """查单股申万行业 → (五大类, 原始l2_name)。不传 fields，获取全部默认字段。"""
        try:
            records = self._call_no_fields(
                "index_member_all", ts_code=ts_code, is_new="Y"
            )
        except TushareApiError:
            return "未分类", ""
        for r in records:
            cat = self._sw_name_to_category(r)
            if cat != "未分类":
                return cat, str(r.get("l2_name", "")).strip()
        # 有记录但都未命中映射：取首条 l2_name 便于诊断
        l2 = str(records[0].get("l2_name", "")).strip() if records else ""
        return "未分类", l2

    def build_sw_cache(self) -> dict[str, str]:
        """构建全量 SW 缓存（首次 ~11 分钟），之后读缓存秒过。"""
        all_codes = self._call("stock_basic", ("ts_code",), list_status="L")
        mapping: dict[str, str] = {}
        l2_names: dict[str, str] = {}
        for r in all_codes:
            ts_code = self._str(r.get("ts_code"))
            if not ts_code:
                continue
            cat, l2 = self._fetch_one_sw_category(ts_code)
            mapping[ts_code] = cat
            l2_names[ts_code] = l2
        self._save_sw_cache(mapping, l2_names=l2_names)
        return mapping

    def _save_sw_cache(
        self, mapping: dict[str, str], *, l2_names: dict[str, str] | None = None
    ) -> None:
        """落盘 sw_industry.csv。l2_names 传入时填写 l2_name 列（便于诊断未分类）。"""
        cache_path = self._sw_cache_path()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with cache_path.open("w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.writer(fh, lineterminator="\n")
            writer.writerow(["ts_code", "l2_name", "category"])
            for ts_code in sorted(mapping):
                l2 = (l2_names or {}).get(ts_code, "")
                writer.writerow([ts_code, l2, mapping[ts_code]])

    @staticmethod
    def load_sw_cache(cache_path: Path) -> dict[str, str] | None:
        """从 CSV 加载申万行业缓存，返回 {ts_code → category}；文件不存在或损坏返回 None。"""
        if not cache_path.exists():
            return None
        try:
            text = cache_path.read_text(encoding="utf-8-sig")
        except OSError:
            return None
        mapping: dict[str, str] = {}
        for row in csv.reader(text.splitlines()):
            if not row or row[0] == "ts_code":
                continue
            if len(row) >= 3 and row[0] and row[2]:
                mapping[row[0].strip()] = row[2].strip()
        return mapping if mapping else None

    def _load_or_build_sw_cache(self) -> dict[str, str]:
        """加载 SW 行业缓存，不存在返回空 dict（按需查询增量填充）。"""
        cache_path = self._sw_cache_path()
        mapping = self.load_sw_cache(cache_path)
        return mapping if mapping is not None else {}

    def _enrich_with_sw_category(self, stocks: list[StockInfo]) -> list[StockInfo]:
        """用申万行业→五大类替换 stock_basic 的 industry。按需查 API，增量写缓存。"""
        sw_map = self._load_or_build_sw_cache()
        modified = False
        for s in stocks:
            if s.ts_code not in sw_map:
                cat, _l2 = self._fetch_one_sw_category(s.ts_code)
                sw_map[s.ts_code] = cat
                modified = True
            cat = sw_map.get(s.ts_code)
            if cat and cat != "未分类":
                s.industry = cat
        if modified:
            self._save_sw_cache(sw_map)
        return stocks

    # ===== 批量采集（O(1) 全市场，ROADMAP Step 1-5）=====

    def _call_paginated(
        self, interface_key: str, page_size: int, **params: Any
    ) -> list[dict]:
        """分页 API 调用：按 offset/limit 循环拉取直到无更多数据。每页走限流+退避。
        不传 fields，调取接口全部字段。
        """
        api_name = get_vip_api_name(interface_key)
        all_records: list[dict] = []
        offset = 0
        while True:
            page = self._call_raw(
                api_name,
                offset=offset,
                limit=page_size,
                **params,
            )
            if not page:
                break
            all_records.extend(page)
            if len(page) < page_size:
                break
            offset += page_size
        return all_records

    def fetch_financials_batch(self, period: str) -> dict[str, StockFeatures]:
        """批量采集全市场财务数据（ROADMAP Step 1-5），调取各接口全部字段。

        调用 4 个 VIP 接口只传 period 不传 ts_code，O(1) 拿全市场，按 ts_code 增量合并。
        end_date 锁定 income 报告期；其余接口 end_date 不覆盖。
        分页自动处理，单接口超限自动 offset 循环。
        """
        page_size = self.settings.vip_page_size
        merged: dict[str, dict[str, Any]] = {}

        logger = logging.getLogger(__name__)
        logger.info("批量采集开始：period=%s page_size=%d", period, page_size)

        # income 作为主接口（确定股票列表与 end_date）
        income_rows = self._call_paginated("income", page_size, period=period)
        for r in income_rows:
            tc = self._str(r.get("ts_code"))
            if tc:
                merged[tc] = self._clean_record(r)
        logger.info("  income: %d 条记录，%d 只股票", len(income_rows), len(merged))

        # 其余三个接口：排除 end_date，仅更新已存在的 ts_code
        _no_end = {"end_date"}
        for key in ("balancesheet", "cashflow", "fina_indicator"):
            rows = self._call_paginated(key, page_size, period=period)
            hits = 0
            for r in rows:
                tc = self._str(r.get("ts_code"))
                if tc and tc in merged:
                    self._merge_non_none(
                        merged[tc], self._clean_record(r, exclude=_no_end)
                    )
                    hits += 1
            logger.info("  %s: %d 条记录，命中 %d 只股票", key, len(rows), hits)

        result: dict[str, StockFeatures] = {}
        for tc, data in merged.items():
            result[tc] = StockFeatures(**{k: v for k, v in data.items()})
        logger.info("批量采集完成：%d 只股票", len(result))
        return result


# 五大类标签
CAT_CYCLICAL = "周期资源"
CAT_CONSUMER = "大消费"
CAT_FINANCIAL = "证券金融"
CAT_TECH = "科技/制造"
CAT_UTILITY = "公用事业/基建"
CAT_UNKNOWN = "未分类"

FIVE_CATEGORIES: tuple[str, ...] = (
    CAT_CYCLICAL,
    CAT_CONSUMER,
    CAT_FINANCIAL,
    CAT_TECH,
    CAT_UTILITY,
)

# 申万二级行业名称 → 五大类
_SW_L2_TO_CATEGORY: dict[str, str] = {
    # ===== 周期资源 =====
    "石油开采": CAT_CYCLICAL,
    "油气开采": CAT_CYCLICAL,
    "石油化工": CAT_CYCLICAL,
    "油服工程": CAT_CYCLICAL,
    "煤炭开采": CAT_CYCLICAL,
    "焦炭": CAT_CYCLICAL,
    "贵金属": CAT_CYCLICAL,
    "工业金属": CAT_CYCLICAL,
    "能源金属": CAT_CYCLICAL,
    "小金属": CAT_CYCLICAL,
    "金属新材料": CAT_CYCLICAL,
    "普钢": CAT_CYCLICAL,
    "特钢": CAT_CYCLICAL,
    "冶钢原料": CAT_CYCLICAL,
    "化学原料": CAT_CYCLICAL,
    "化学制品": CAT_CYCLICAL,
    "农化制品": CAT_CYCLICAL,
    "化学纤维": CAT_CYCLICAL,
    "塑料": CAT_CYCLICAL,
    "橡胶": CAT_CYCLICAL,
    "非金属材料": CAT_CYCLICAL,
    "水泥": CAT_CYCLICAL,
    "玻璃玻纤": CAT_CYCLICAL,
    "装修建材": CAT_CYCLICAL,
    "种植业": CAT_CYCLICAL,
    "渔业": CAT_CYCLICAL,
    "饲料": CAT_CYCLICAL,
    "农产品加工": CAT_CYCLICAL,
    "农业综合": CAT_CYCLICAL,
    "养殖业": CAT_CYCLICAL,
    "动物保健": CAT_CYCLICAL,
    "林业": CAT_CYCLICAL,
    "造纸": CAT_CYCLICAL,
    "炼化及贸易": CAT_CYCLICAL,
    # ===== 大消费 =====
    "白酒": CAT_CONSUMER,
    "非白酒": CAT_CONSUMER,
    "啤酒": CAT_CONSUMER,
    "其他酒类": CAT_CONSUMER,
    "食品加工": CAT_CONSUMER,
    "调味品": CAT_CONSUMER,
    "调味发酵品": CAT_CONSUMER,
    "饮料乳品": CAT_CONSUMER,
    "休闲食品": CAT_CONSUMER,
    "服装家纺": CAT_CONSUMER,
    "饰品": CAT_CONSUMER,
    "纺织制造": CAT_CONSUMER,
    "包装印刷": CAT_CONSUMER,
    "文娱用品": CAT_CONSUMER,
    "家居用品": CAT_CONSUMER,
    "一般零售": CAT_CONSUMER,
    "专业连锁": CAT_CONSUMER,
    "互联网电商": CAT_CONSUMER,
    "旅游零售": CAT_CONSUMER,
    "酒店餐饮": CAT_CONSUMER,
    "旅游及景区": CAT_CONSUMER,
    "教育": CAT_CONSUMER,
    "专业服务": CAT_CONSUMER,
    "体育": CAT_CONSUMER,
    "化妆品": CAT_CONSUMER,
    "个护用品": CAT_CONSUMER,
    "医美": CAT_CONSUMER,
    "医疗美容": CAT_CONSUMER,
    "白色家电": CAT_CONSUMER,
    "黑色家电": CAT_CONSUMER,
    "小家电": CAT_CONSUMER,
    "家电零部件": CAT_CONSUMER,
    "其他家电": CAT_CONSUMER,
    "照明设备": CAT_CONSUMER,
    "厨卫电器": CAT_CONSUMER,
    "化学制药": CAT_CONSUMER,
    "中药": CAT_CONSUMER,
    "生物制品": CAT_CONSUMER,
    "医疗器械": CAT_CONSUMER,
    "医药商业": CAT_CONSUMER,
    "医疗服务": CAT_CONSUMER,
    "房地产开发": CAT_CONSUMER,
    "房地产服务": CAT_CONSUMER,
    "乘用车": CAT_CONSUMER,
    "商用车": CAT_CONSUMER,
    "汽车零部件": CAT_CONSUMER,
    "汽车服务": CAT_CONSUMER,
    "摩托车及其他": CAT_CONSUMER,
    "游戏": CAT_CONSUMER,
    "影视院线": CAT_CONSUMER,
    "广告营销": CAT_CONSUMER,
    "数字媒体": CAT_CONSUMER,
    "出版": CAT_CONSUMER,
    "电视广播": CAT_CONSUMER,
    "贸易": CAT_CONSUMER,
    # ===== 证券金融 =====
    "国有大型银行": CAT_FINANCIAL,
    "股份制银行": CAT_FINANCIAL,
    "城商行": CAT_FINANCIAL,
    "农商行": CAT_FINANCIAL,
    "证券": CAT_FINANCIAL,
    "保险": CAT_FINANCIAL,
    "期货": CAT_FINANCIAL,
    "信托": CAT_FINANCIAL,
    "金融控股": CAT_FINANCIAL,
    "多元金融": CAT_FINANCIAL,
    "租赁": CAT_FINANCIAL,
    "综合": CAT_FINANCIAL,
    # ===== 科技/制造 =====
    "半导体": CAT_TECH,
    "元件": CAT_TECH,
    "光学光电子": CAT_TECH,
    "消费电子": CAT_TECH,
    "电子化学品": CAT_TECH,
    "软件开发": CAT_TECH,
    "IT服务": CAT_TECH,
    "计算机设备": CAT_TECH,
    "通信服务": CAT_TECH,
    "通信设备": CAT_TECH,
    "航空装备": CAT_TECH,
    "航天装备": CAT_TECH,
    "地面兵装": CAT_TECH,
    "航海装备": CAT_TECH,
    "军工电子": CAT_TECH,
    "通用设备": CAT_TECH,
    "专用设备": CAT_TECH,
    "自动化设备": CAT_TECH,
    "轨交设备": CAT_TECH,
    "工程机械": CAT_TECH,
    "光伏设备": CAT_TECH,
    "风电设备": CAT_TECH,
    "电池": CAT_TECH,
    "电网设备": CAT_TECH,
    "其他电源设备": CAT_TECH,
    "电机": CAT_TECH,
    "集成电路": CAT_TECH,
    "其他电子": CAT_TECH,
    "环境治理": CAT_TECH,
    "环保设备": CAT_TECH,
    # ===== 公用事业/基建 =====
    "电力": CAT_UTILITY,
    "燃气": CAT_UTILITY,
    "水务": CAT_UTILITY,
    "航空机场": CAT_UTILITY,
    "铁路公路": CAT_UTILITY,
    "航运港口": CAT_UTILITY,
    "物流": CAT_UTILITY,
    "房屋建设": CAT_UTILITY,
    "装修装饰": CAT_UTILITY,
    "基础建设": CAT_UTILITY,
    "专业工程": CAT_UTILITY,
    "工程咨询": CAT_UTILITY,
    "工程咨询服务": CAT_UTILITY,
    "公交": CAT_UTILITY,
}


def sw_l2_to_category(l2_name: str) -> str:
    """申万二级行业名称 → 五大类标签。未知行业返回 ``未分类``。
    自动处理 SW 行业名中的罗马数字后缀（如 ``中药Ⅱ`` → ``中药``）。
    """
    if not l2_name:
        return CAT_UNKNOWN
    cat = _SW_L2_TO_CATEGORY.get(l2_name)
    if cat:
        return cat
    # 去掉末尾罗马数字 / 数字 / 空格后重试
    cleaned = l2_name.rstrip("ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ0123456789 ")
    if cleaned and cleaned != l2_name:
        cat = _SW_L2_TO_CATEGORY.get(cleaned)
        if cat:
            return cat
    return CAT_UNKNOWN
