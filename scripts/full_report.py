"""荐股 Top20 报告生成脚本：LLM 编排 + 输出。
纯逻辑（解析/构建上下文/清洗/CSV）见 src/reports/reporting.py。
用法：uv run python scripts/full_report.py
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from scripts.full_scores import _find_latest
from src.agents.llm_adapter import LLMClient
from src.data.contract import StockFeatures
from src.reports.evaluation import classify_company_type, get_advice
from src.reports.reporting import (
    _CMT_FIELDS,
    _HL_FIELDS,
    _RISK_FIELDS,
    Top20Result,
    build_llm_context,
    clean_llm_output,
    clean_ts_code,
    load_scoring_rows,
    make_features,
    parse_back,
    write_recommend_csv,
)

_SYSTEM_PROMPTS = {
    "highlight": (
        "你是A股基本面分析师，只输出结论，不解释方法。"
        "提炼核心亮点的优先级：景气度（营收/净利增速）高于盈利质量（毛利率/现金流），高于股东回报（ROE）。"
        "千里马注重增速与爆发力，现金牛注重现金流与稳定性，护城河注重品牌溢价与竞争壁垒。"
        "输出2-4句连贯中文。有数据优先用数据，无数据时直接说评分结论，禁止用空话填充。"
        "严禁：推理过程、分析步骤、规则引用、自问自答、角色声明。"
    ),
    "risk": (
        "你是A股风控分析师，只输出结论，不解释方法。"
        "输出2-4句风险分析中文，直接说结论。有具体数据时引用（如'负债率68%偏高'）；"
        "无显著风险时只写'当前财务指标未发现重大风险信号'；评分低分项如实点名，能附数据就附。"
        "严禁：推理过程、语气词（'看起来''但可能''但要注意''似乎'）、角色声明、自问自答。"
    ),
    "comment": (
        "你是A股投资顾问，只输出结论。"
        "一句定性（如'消费白马，适合中长线配置'），一句说明核心驱动力，一句仓位建议。"
        "输出3-5句连贯中文，严禁编号、格式标记、元描述。"
    ),
}

_HL_FEWSHOT = (
    "【输出示例】\n"
    "好：营收同比+38%高速扩张，ROE 22%股东回报优秀，毛利率58%品牌护城河稳固。\n"
    "差：该股表现不错，值得关注。\n"
)

_RISK_FEWSHOT = (
    "【输出示例】\n"
    "好：负债率68%偏高，流动比率0.9倍偿债压力较大，营收增速放缓至5%。\n"
    "差：需要关注该股的风险。\n"
)

_CMT_FEWSHOT = (
    "【输出示例】\n"
    "好：消费白马，高确定性标的，适合中长线配置。核心驱动为营收稳健增长+高毛利护城河，"
    "当前估值合理，可分批建仓，目标仓位5-10%。\n"
    "差：建议关注这只股票。\n"
)


def _generate_single(
    client: LLMClient,
    system: str,
    prompt: str,
    max_tokens: int,
    max_chars: int,
    key: str = "highlight",
) -> str:
    """调 LLM 生成一段文案。含 few-shot 示例 + 质量检测 + 重试。"""
    resp = client.chat_completion(
        system=system,
        user=prompt,
        temperature=0.3,
        max_tokens=max_tokens,
        reasoning=True,
    )
    cleaned = clean_llm_output(resp.content, max_chars)

    if not cleaned or len(cleaned) < 3:
        resp = client.chat_completion(
            system=system,
            user=prompt,
            temperature=0.6,
            max_tokens=max_tokens,
            reasoning=True,
        )
        cleaned = clean_llm_output(resp.content, max_chars)

    if not cleaned or len(cleaned) < 2:
        raw = resp.content.strip()
        cleaned = raw[:max_chars] if raw else ""
    return cleaned


def _build_highlight_prompt(
    ctx: str,
    company_type: str,
    growth,
    stability,
    return_score,
) -> str:
    parts = [
        "根据以下财务数据，提炼该股的核心亮点。",
        "",
        f"【公司类型】{company_type}",
        "",
        "【财务数据】",
        ctx,
        "",
        _HL_FEWSHOT,
        "直接输出结论：",
    ]
    return "\n".join(parts)


def _build_risk_prompt(
    ctx: str,
    company_type: str,
    growth,
    stability,
    return_score,
) -> str:
    parts = [
        "根据以下财务数据，指出该股的主要风险点。",
        "",
        "【数据】",
        ctx,
        "",
        _RISK_FEWSHOT,
        "直接输出结论：",
    ]
    return "\n".join(parts)


def _build_comment_prompt(
    ctx: str,
    company_type: str,
    rating: str,
    advice: str,
    growth,
    stability,
    return_score,
) -> str:
    parts = [
        "根据以下财务数据和评级，给出一段投资点评。",
        "",
        f"【评级】{rating} | 【操作建议】{advice} | 【公司类型】{company_type}",
        "",
        "【财务数据】",
        ctx,
        "",
        _CMT_FEWSHOT,
        "直接输出结论：",
    ]
    return "\n".join(parts)


def build_top20(csv_path: Path) -> Top20Result:
    """读取评分 CSV → 降序 Top20 → LLM 生成文案 → 导出荐股表。"""
    client = LLMClient()
    raw_rows = load_scoring_rows(csv_path)

    parsed_rows: list[tuple[dict, StockFeatures, float]] = []
    for raw in raw_rows:
        p = parse_back(raw)
        composite = p.get("综合分")
        if composite is None:
            continue
        try:
            feat = make_features(p)
        except Exception:
            continue
        parsed_rows.append((p, feat, float(composite)))

    parsed_rows.sort(key=lambda x: x[2], reverse=True)
    top20 = parsed_rows[:20]

    result = Top20Result()

    _HL_TOKENS, _HL_CHARS = 300, 120
    _RISK_TOKENS, _RISK_CHARS = 300, 120
    _CMT_TOKENS, _CMT_CHARS = 500, 180

    tasks: list[tuple[int, str, str, LLMClient, str, int, int]] = []

    for i, (parsed, feat, composite) in enumerate(top20):
        growth = parsed.get("成长性")
        stability = parsed.get("稳健性")
        return_score = parsed.get("资金回报")
        rating = parsed.get("评级")
        rating_str = str(rating) if rating else ""
        company = classify_company_type(feat)
        advice = get_advice(rating_str)

        ctx_hl = build_llm_context(
            parsed,
            growth,
            stability,
            return_score,
            composite,
            rating_str,
            company.type_label,
            field_set=_HL_FIELDS,
        )
        ctx_risk = build_llm_context(
            parsed,
            growth,
            stability,
            return_score,
            composite,
            rating_str,
            company.type_label,
            field_set=_RISK_FIELDS,
        )
        ctx_comment = build_llm_context(
            parsed,
            growth,
            stability,
            return_score,
            composite,
            rating_str,
            company.type_label,
            field_set=_CMT_FIELDS,
        )

        prompt_hl = _build_highlight_prompt(
            ctx_hl, company.type_label, growth, stability, return_score
        )
        prompt_risk = _build_risk_prompt(
            ctx_risk, company.type_label, growth, stability, return_score
        )
        prompt_comment = _build_comment_prompt(
            ctx_comment,
            company.type_label,
            rating_str,
            f"{advice.advice}（{advice.position}）",
            growth,
            stability,
            return_score,
        )

        tasks.append(
            (
                i,
                "highlight",
                _SYSTEM_PROMPTS["highlight"],
                client,
                prompt_hl,
                _HL_TOKENS,
                _HL_CHARS,
            )
        )
        tasks.append(
            (
                i,
                "risk",
                _SYSTEM_PROMPTS["risk"],
                client,
                prompt_risk,
                _RISK_TOKENS,
                _RISK_CHARS,
            )
        )
        tasks.append(
            (
                i,
                "comment",
                _SYSTEM_PROMPTS["comment"],
                client,
                prompt_comment,
                _CMT_TOKENS,
                _CMT_CHARS,
            )
        )

        result.rows.append(
            {
                "股票代码": clean_ts_code(str(parsed.get("ts_code", ""))),
                "股票名称": str(parsed.get("name", "")),
                "公司类型": company.type_label,
                "行业分类": str(parsed.get("industry", "")),
                "核心亮点": "",
                "成长性": str(int(growth)) if growth else "",
                "稳健性": str(int(stability)) if stability else "",
                "回报性": str(int(return_score)) if return_score else "",
                "综合分": str(composite),
                "评级": rating_str,
                "操作建议": f"{advice.advice}（{advice.position}）",
                "风险提示": "",
                "点评": "",
            }
        )

    _LLM_WORKERS = 6
    executor = ThreadPoolExecutor(max_workers=_LLM_WORKERS)
    futures = {
        executor.submit(
            _generate_single, client, system, prompt, max_tokens, max_chars, key
        ): (idx, key)
        for idx, key, system, client, prompt, max_tokens, max_chars in tasks
    }
    executor.shutdown(wait=True)

    for fut in futures:
        idx, key = futures[fut]
        try:
            text = fut.result()
        except Exception:
            text = ""
        key_cn = {"highlight": "核心亮点", "risk": "风险提示", "comment": "点评"}[key]
        result.rows[idx][key_cn] = text

    for i, (parsed, _, _) in enumerate(top20):
        r = result.rows[i]
        name = r["股票名称"]
        rating_display = (
            r["评级"].encode("ascii", errors="replace").decode("ascii")
            if r["评级"]
            else "-"
        )
        hl = r["核心亮点"][:60] if r["核心亮点"] else "(空)"
        print(f"  [{i + 1:>2}/20] {name} | {rating_display} | {hl}")

    return result


def main() -> None:
    """脚本入口：自动取最新评分 CSV 生成荐股 Top20。"""
    from src.config import get_settings

    settings = get_settings()
    scoring_dir = settings.data_path("fin") / "full_scores"
    csv_path = _find_latest(scoring_dir)
    if csv_path is None:
        raise SystemExit("无评分 CSV，请先运行 full_scores.py")

    stamp = csv_path.stem
    out_dir = settings.data_path("fin") / "full_report"
    result = build_top20(csv_path)
    out_path = write_recommend_csv(result, out_dir / f"{stamp}.csv")
    print(f"荐股 Top20 产出：{out_path}")


if __name__ == "__main__":
    main()
