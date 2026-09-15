"""微信指令对应的本地工具：只读查产物，写操作走现有 CLI 函数。"""

from __future__ import annotations

from collections.abc import Callable

from src.config import Settings
from src.data.store import Kind, latest, load_features_prefer_raw
from src.llm.preferences import load_preferences, preferences_path
from src.reports.reporting import TOP_N, load_score_rows_prefer_raw, load_scoring_rows, write_recommend_markdown
from src.tools import EXIT_OK, ToolError
from src.tools.holdings import HoldingsParams, run_holdings
from src.tools.market import CollectParams, ScoresParams, ScreenParams, run_collect, run_market_scores, run_screen
from src.tools.report import run_report
from src.tools.status import StatusParams, run_status

ToolMap = dict[str, Callable[..., str]]


def default_tools(settings: Settings) -> ToolMap:
    def _status() -> str:
        _code, payload = run_status(StatusParams(check=False), settings)
        items = (payload.get("data") or {}).get("items") or []
        lines = [f"{item['kind']}: {item['reason']}" for item in items]
        return "新鲜度\n" + "\n".join(lines) if lines else "无状态"

    def _report() -> str:
        path = latest(Kind.REPORT, settings=settings)
        if path is None:
            return "无报告，请先在本机运行 alpha-jerry report"
        rows = load_scoring_rows(path)[:TOP_N]
        if not rows:
            return f"报告已生成：{path.name}"
        md_path = write_recommend_markdown(rows, path.with_suffix(".md"), stamp=path.stem)
        return md_path.read_text(encoding="utf-8")

    def _update() -> str:
        try:
            _code, payload = run_collect(CollectParams(update=True), settings)
        except ToolError as exc:
            return str(exc)
        data = payload.get("data") or {}
        if data.get("skipped"):
            return f"数据仍新鲜（{data.get('period')}），已跳过采集"
        return f"采集完成 成功{data.get('success_count', 0)} 失败{data.get('failure_count', 0)}"

    def _force() -> str:
        try:
            _code, payload = run_collect(CollectParams(force=True), settings)
        except ToolError as exc:
            return str(exc)
        data = payload.get("data") or {}
        return f"全量采集完成 成功{data.get('success_count', 0)} 失败{data.get('failure_count', 0)}"

    def _scores() -> str:
        try:
            _code, payload = run_market_scores(ScoresParams(), settings)
        except ToolError as exc:
            return str(exc)
        data = payload.get("data") or {}
        return f"评分完成 通过{data.get('passed', 0)} 否决{data.get('vetoed', 0)}"

    def _generate() -> str:
        pref = load_preferences(preferences_path(settings=settings))
        provider = pref[0] if pref else settings.llm_provider
        model = pref[1] if pref else None
        try:
            code = run_report(provider, model, settings=settings, save=False, quiet=True)
        except Exception as exc:
            return f"生成报告失败：{type(exc).__name__}"
        if code != EXIT_OK:
            return "生成报告失败，请先在本机配置 API Key 并备好评分数据"
        return _report()

    def _holdings() -> str:
        _code, payload = run_holdings(HoldingsParams(action="list"), settings)
        items = (payload.get("data") or {}).get("items") or []
        if not items:
            return "持仓为空"
        return "持仓：" + "、".join(f"{row.get('ts_code')} {row.get('name', '')}".strip() for row in items)

    def _add(code: str) -> str:
        run_holdings(HoldingsParams(action="add", ts_code=code), settings)
        return f"已加仓 {code}"

    def _remove(code: str) -> str:
        run_holdings(HoldingsParams(action="remove", ts_code=code), settings)
        return f"已减仓 {code}"

    def _query(code: str) -> str:
        path = latest(Kind.COLLECT, settings=settings)
        if path is None:
            return f"无采集数据，无法查询 {code}"
        features = load_features_prefer_raw(path)
        feat = next((item for item in features if item.ts_code == code), None)
        if feat is None:
            return f"未找到 {code}"
        extra = ""
        scores_path = latest(Kind.SCORES, settings=settings)
        if scores_path is not None:
            row = next(
                (item for item in load_score_rows_prefer_raw(scores_path) if item.get("ts_code") == code),
                None,
            )
            if row:
                extra = f" 评级{row.get('评级')}"
        holder = f"{feat.holder_num}户" if feat.holder_num is not None else "股东户数未知"
        return f"{feat.ts_code} {feat.name or ''} {feat.industry or ''} {holder}{extra}".strip()

    def _screen(industry: str, rating: str) -> str:
        try:
            _code, payload = run_screen(
                ScreenParams(industry=industry or None, rating=rating or None),
                settings,
            )
        except ToolError as exc:
            return str(exc)
        items = (payload.get("data") or {}).get("items") or []
        names = [str(row.get("name") or row.get("ts_code") or "") for row in items[:5]]
        head = "、".join(part for part in names if part) or "无匹配"
        return f"筛选到{len(items)}只：{head}"

    return {
        "status": _status,
        "report": _report,
        "update": _update,
        "force": _force,
        "scores": _scores,
        "generate": _generate,
        "holdings": _holdings,
        "add": _add,
        "remove": _remove,
        "query": _query,
        "screen": _screen,
    }
