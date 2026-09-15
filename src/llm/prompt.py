"""锐评 Prompt：一股一调用、受限 JSON 三段输出；只喂事实与规则派生提示，绝不喂评级 / 仓位。"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass

from src.llm.contracts import REVIEW_FIELDS, ReviewDraft, ReviewFacts, Violation
from src.llm.validate import LIMITS

PROMPT_VERSION = "review-v3"

# 给模型的字数目标比校验上限收紧 6 字：实测模型计数常偏多 3-5 字，留足余量才能一次通过。
TARGET_CHARS: dict[str, tuple[int, int]] = {
    field: (minimum + 4, maximum - 6) for field, (minimum, maximum) in LIMITS.items()
}

_NUMBER_DIGITS = 1
_NO_RISK_SENTENCE = "当前财务指标未发现重大风险信号"

SYSTEM_PROMPT = (
    "你是A股研报编辑，只负责把给定事实改写成简洁中文，不做计算、不下评级、不给仓位。\n"
    '只输出一个 json 对象：{"highlight": "...", "risk": "...", "comment": "..."}，不得输出其他内容。\n'
    "硬性规则：\n"
    "1. 数字只能从【可用数字】原样引用并保留一位小数，不得换算、不得估算倍数、不得引入新数字。\n"
    "2. 全文中文；除 ROE、EPS 等缩写外不得出现英文单词。\n"
    "3. 不得提及评级、操作建议或仓位比例。\n"
    "4. 三段不得重复同一个数字，也不得互相改写。\n"
    "5. 禁用词：综合来看、值得关注、总体而言、俱佳、看起来、似乎。\n"
    "6. 字数按含标点与数字的总字符数计，宁短勿长："
    f"highlight {TARGET_CHARS['highlight'][0]}-{TARGET_CHARS['highlight'][1]} 字，"
    f"risk {TARGET_CHARS['risk'][0]}-{TARGET_CHARS['risk'][1]} 字，"
    f"comment {TARGET_CHARS['comment'][0]}-{TARGET_CHARS['comment'][1]} 字。\n"
    "段落要求：\n"
    "- highlight：一句话，按景气度 > 盈利质量 > 股东回报只写 2 个指标，用逗号连接；不要加「景气高企」「量利齐升」这类空话尾巴。\n"
    f"- risk：一句话，把【风险提示】合并成一句，只保留关键数字；没有风险提示时原样写“{_NO_RISK_SENTENCE}”。\n"
    "- comment：一句话，格式固定为「行业+公司类型，重点盯住+【盯住变量】」，不加其他内容。"
)

_EXAMPLE_JSON = (
    '{"highlight": "营收同比+…%，ROE …%", '
    '"risk": "净利同比+…%含低基数效应，负债率…%偏高", '
    '"comment": "大消费护城河，重点盯住毛利率与品牌溢价能否维持"}'
)

_FENCE = re.compile(r"```(?:json)?", re.IGNORECASE)


def render_user_prompt(
    facts: ReviewFacts,
    feedback: Sequence[Violation] = (),
    previous: ReviewDraft | None = None,
) -> str:
    numbers = "；".join(metric.render(_NUMBER_DIGITS) for metric in facts.metrics) or "无"
    lines = [
        f"【标的】{facts.name}（{facts.code}）｜{facts.industry}｜{facts.company_type}",
        f"【可用数字】{numbers}",
    ]
    if facts.flags:
        lines.append("【风险提示】")
        lines.extend(f"- {flag.note}" for flag in facts.flags)
    else:
        lines.append("【风险提示】无")
    lines.append(f"【盯住变量】{facts.watch_variable}")
    lines.append(f"【示例 json】{_EXAMPLE_JSON}")

    if feedback:
        if previous is not None:
            lines.append(
                "【上一次输出】"
                + json.dumps(
                    {field: previous.get(field) for field in REVIEW_FIELDS},
                    ensure_ascii=False,
                )
            )
        lines.append("【上一次输出的问题】")
        lines.extend(f"- {violation.message}" for violation in feedback)
        lines.append("请修正以上问题后重新输出 json：")
    else:
        lines.append("请输出 json：")
    return "\n".join(lines)


def parse_draft(text: str) -> ReviewDraft | None:
    """宽松解析：剥掉代码围栏与前后废话，只认第一个 { 到最后一个 } 之间的对象。"""
    stripped = _FENCE.sub("", text or "").strip()
    start, end = stripped.find("{"), stripped.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    values = {field: "" if payload.get(field) is None else str(payload.get(field)).strip() for field in REVIEW_FIELDS}
    return ReviewDraft(**values)


@dataclass(frozen=True)
class PromptSpec:
    """版本化的提示词规格；version 进入缓存指纹，改词必须升版本。"""

    version: str = PROMPT_VERSION
    system: str = SYSTEM_PROMPT

    def render(
        self,
        facts: ReviewFacts,
        feedback: Sequence[Violation] = (),
        previous: ReviewDraft | None = None,
    ) -> str:
        return render_user_prompt(facts, feedback, previous)

    def parse(self, text: str) -> ReviewDraft | None:
        return parse_draft(text)


DEFAULT_PROMPT = PromptSpec()
