"""report / models：荐股 Top20 与模型目录。"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from src.config import Settings, get_settings
from src.data.readers import find_latest_csv
from src.llm.catalog import (
    MODEL_CATALOG_UPDATED,
    PROVIDER_API_URLS,
    PROVIDER_DISPLAY_NAMES,
    PROVIDER_DOCS_URLS,
    list_models,
)
from src.llm.client import LLMClient
from src.llm.credentials import (
    SUPPORTED_PROVIDERS,
    CredentialError,
    normalize_provider,
    resolve_api_key,
)
from src.llm.preferences import load_preferences, preferences_path, save_preferences
from src.llm.review import build_fallback_client
from src.reports.generator import build_top20
from src.reports.reporting import write_recommend_csv
from src.tools import EXIT_CONFIG, EXIT_DATA, EXIT_OK, EXIT_UPSTREAM, envelope


def select_provider() -> str:
    """在交互终端选择 Provider。"""
    print("请选择 LLM Provider：")
    print("  1) DeepSeek")
    print("  2) GLM")
    choices = {"1": "deepseek", "deepseek": "deepseek", "2": "glm", "glm": "glm"}
    while True:
        try:
            answer = input("请输入 1 或 2: ").strip().lower()
        except (EOFError, KeyboardInterrupt) as exc:
            raise CredentialError("已取消 Provider 选择") from exc
        selected = choices.get(answer)
        if selected:
            return selected
        print("输入无效，请输入 1 或 2。", file=sys.stderr)


def select_model(provider: str, default_model: str) -> str:
    """在交互终端选择具体模型，并允许输入未来模型 ID。"""
    models = list_models(provider)
    print(f"请选择 {PROVIDER_DISPLAY_NAMES[provider]} 模型：")
    for index, model in enumerate(models, start=1):
        context = _format_token_limit(model.context_window)
        max_output = _format_token_limit(model.max_output_tokens)
        print(f"  {index}) {model.model_id} [{context}/{max_output}] - {model.summary}")
    print("  c) 自定义模型 ID")
    while True:
        try:
            answer = input(f"请输入编号（回车使用 {default_model}）: ").strip().lower()
        except (EOFError, KeyboardInterrupt) as exc:
            raise CredentialError("已取消模型选择") from exc
        if not answer:
            return default_model
        if answer in {"c", "custom"}:
            try:
                custom = input("请输入模型 ID: ").strip()
            except (EOFError, KeyboardInterrupt) as exc:
                raise CredentialError("已取消模型选择") from exc
            if custom:
                return custom
            print("模型 ID 不能为空。", file=sys.stderr)
            continue
        if answer.isdigit():
            index = int(answer) - 1
            if 0 <= index < len(models):
                return models[index].model_id
        print("输入无效，请输入模型编号或 c。", file=sys.stderr)


def _format_token_limit(value: int) -> str:
    if value == 1_000_000:
        return "1M"
    if value % 1024 == 0:
        return f"{value // 1024}K"
    if value % 1000 == 0:
        return f"{value // 1000}K"
    return str(value)


def _fallback_label(fallback_client: object | None) -> str:
    if fallback_client is None:
        return "Fallback: 规则模板（未配置备用 Provider 密钥或已禁用切换）"
    spec = fallback_client.spec  # type: ignore[attr-defined]
    return f"Fallback: {spec.name.value} / {spec.model}"


def _say(quiet: bool, *args: object, **kwargs: Any) -> None:
    if not quiet:
        print(*args, **kwargs)


def run_models(provider: str | None, *, settings: Settings | None = None, quiet: bool = False) -> int:
    """打印模型目录、实际配置端点和默认型号。"""
    resolved_settings = settings or get_settings()
    providers = (normalize_provider(provider),) if provider else SUPPORTED_PROVIDERS
    _say(quiet, f"模型目录核验日期：{MODEL_CATALOG_UPDATED}")
    for selected in providers:
        display_name = PROVIDER_DISPLAY_NAMES[selected]
        base_url = getattr(resolved_settings, f"{selected}_base_url")
        default_model = getattr(resolved_settings, f"{selected}_model")
        _say(quiet, f"\n{display_name}")
        _say(quiet, f"  当前 OpenAI Chat Base URL: {base_url}")
        for protocol, url in PROVIDER_API_URLS[selected].items():
            _say(quiet, f"  {protocol}: {url}")
        _say(quiet, f"  默认模型: {default_model}")
        _say(quiet, f"  官方文档: {PROVIDER_DOCS_URLS[selected]}")
        for model in list_models(selected):
            context = _format_token_limit(model.context_window)
            max_output = _format_token_limit(model.max_output_tokens)
            modalities = "/".join(model.input_modalities)
            thinking = "强制" if model.thinking_required else "可选"
            efforts = "/".join(model.reasoning_efforts) or "模型自动"
            _say(quiet, f"  - {model.model_id}: {model.summary}")
            _say(
                quiet,
                f"    上下文: {context} | 最大输出: {max_output} | "
                f"输入: {modalities} | 思考: {thinking} | 推理强度: {efforts}",
            )
    return EXIT_OK


def models_payload(provider: str | None, settings: Settings | None = None) -> dict[str, Any]:
    resolved = settings or get_settings()
    providers = (normalize_provider(provider),) if provider else SUPPORTED_PROVIDERS
    catalog = []
    for selected in providers:
        catalog.append(
            {
                "provider": selected,
                "base_url": getattr(resolved, f"{selected}_base_url"),
                "default_model": getattr(resolved, f"{selected}_model"),
                "models": [model.model_id for model in list_models(selected)],
            }
        )
    return envelope(ok=True, command="models", data={"updated": MODEL_CATALOG_UPDATED, "providers": catalog})


def run_report(
    provider: str | None,
    model: str | None,
    *,
    settings: Settings | None = None,
    save: bool = True,
    quiet: bool = False,
) -> int:
    """执行 report 子命令并返回稳定退出码。"""
    resolved_settings = settings or get_settings()
    scoring_dir = resolved_settings.data_path("fin") / "full_scores"
    csv_path = find_latest_csv(scoring_dir)
    if csv_path is None:
        _say(quiet, "无评分 CSV，请先运行 full_scores.py", file=sys.stderr)
        return EXIT_DATA

    interactive = sys.stdin.isatty()
    preference_file = preferences_path(settings=resolved_settings)
    saved_preference = load_preferences(preference_file) if provider is None else None

    if provider is None:
        if saved_preference is not None:
            selected_provider, selected_model = saved_preference
            _say(quiet, f"已应用上次选择：{selected_provider} / {selected_model}")
        elif interactive:
            try:
                selected_provider = select_provider()
            except CredentialError as exc:
                _say(quiet, str(exc), file=sys.stderr)
                return EXIT_CONFIG
        else:
            _say(
                quiet,
                "非交互终端必须显式指定 --provider deepseek 或 --provider glm，或先在交互终端保存一次模型选择",
                file=sys.stderr,
            )
            return EXIT_CONFIG
    else:
        try:
            selected_provider = normalize_provider(provider)
        except CredentialError as exc:
            _say(quiet, str(exc), file=sys.stderr)
            return EXIT_CONFIG

    configured_model = str(getattr(resolved_settings, f"{selected_provider}_model")).strip()
    if model is not None:
        selected_model = model.strip()
    elif provider is None and saved_preference is not None:
        pass
    elif interactive:
        try:
            selected_model = select_model(selected_provider, configured_model)
        except CredentialError as exc:
            _say(quiet, str(exc), file=sys.stderr)
            return EXIT_CONFIG
    else:
        selected_model = configured_model

    try:
        api_key = resolve_api_key(selected_provider, settings=resolved_settings)
        client = LLMClient(
            provider=selected_provider,
            model=selected_model,
            api_key=api_key,
            settings=resolved_settings,
        )
        fallback_client = build_fallback_client(
            selected_provider,
            resolved_settings.review_fallback_provider,
            settings=resolved_settings,
        )
    except CredentialError as exc:
        _say(quiet, str(exc), file=sys.stderr)
        return EXIT_CONFIG

    _say(quiet, f"Provider: {client.spec.name.value}")
    _say(quiet, f"Model: {client.spec.model}")
    _say(quiet, _fallback_label(fallback_client))

    if save:
        try:
            save_preferences(preference_file, selected_provider, selected_model)
        except CredentialError as exc:
            _say(quiet, str(exc), file=sys.stderr)

    try:
        result = build_top20(
            csv_path,
            client=client,
            fallback_client=fallback_client,
            settings=resolved_settings,
        )
    except Exception as exc:
        _say(quiet, f"LLM 报告生成失败（{type(exc).__name__}）", file=sys.stderr)
        return EXIT_UPSTREAM

    out_dir = resolved_settings.data_path("fin") / "full_report"
    try:
        out_path = write_recommend_csv(result, out_dir / f"{csv_path.stem}.csv")
    except OSError as exc:
        _say(quiet, f"报告写盘失败：{exc}", file=sys.stderr)
        return EXIT_DATA
    _say(quiet, f"荐股 Top20 产出：{out_path}")
    return EXIT_OK


def register(subparsers: argparse._SubParsersAction) -> None:
    report = subparsers.add_parser("report", help="生成荐股 Top20 报告")
    report.add_argument("--provider", choices=SUPPORTED_PROVIDERS, default=None, help="deepseek 或 glm")
    report.add_argument("--model", default=None, help="模型 ID，缺省走偏好或 .env")
    report.add_argument("--no-save", dest="save", action="store_false", help="本次不覆盖已记忆的模型选择")
    report.set_defaults(handler="report", save=True)

    models = subparsers.add_parser("models", help="查看已核验的模型与 API 端点")
    models.add_argument("--provider", choices=SUPPORTED_PROVIDERS, default=None, help="只列出指定 Provider")
    models.set_defaults(handler="models")
