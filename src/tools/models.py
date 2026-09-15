"""models / models use：目录、当前偏好、切换并记住。"""

from __future__ import annotations

import argparse
from typing import Any

from src.config import Settings, get_settings
from src.llm.catalog import (
    MODEL_CATALOG_UPDATED,
    PROVIDER_API_URLS,
    PROVIDER_DISPLAY_NAMES,
    PROVIDER_DOCS_URLS,
    list_models,
)
from src.llm.credentials import (
    SUPPORTED_PROVIDERS,
    CredentialError,
    normalize_provider,
)
from src.llm.preferences import load_preferences, preferences_path, save_preferences
from src.tools import EXIT_DATA, EXIT_OK, ToolError, envelope


def _format_token_limit(value: int) -> str:
    if value == 1_000_000:
        return "1M"
    if value % 1024 == 0:
        return f"{value // 1024}K"
    if value % 1000 == 0:
        return f"{value // 1000}K"
    return str(value)


def _preference(settings: Settings) -> tuple[str, str] | None:
    return load_preferences(preferences_path(settings=settings))


def _preference_label(settings: Settings) -> str:
    saved = _preference(settings)
    if saved is None:
        return "当前偏好：未选择（models use 或 report --provider）"
    return f"当前偏好：{saved[0]} / {saved[1]}"


def run_models(provider: str | None, *, settings: Settings | None = None, quiet: bool = False) -> int:
    """打印当前偏好、模型目录、实际配置端点和默认型号。"""
    resolved = settings or get_settings()
    providers = (normalize_provider(provider),) if provider else SUPPORTED_PROVIDERS
    if not quiet:
        print(_preference_label(resolved))
        print(f"模型目录核验日期：{MODEL_CATALOG_UPDATED}")
    for selected in providers:
        display_name = PROVIDER_DISPLAY_NAMES[selected]
        base_url = getattr(resolved, f"{selected}_base_url")
        default_model = getattr(resolved, f"{selected}_model")
        if not quiet:
            print(f"\n{display_name}")
            print(f"  当前 OpenAI Chat Base URL: {base_url}")
            for protocol, url in PROVIDER_API_URLS[selected].items():
                print(f"  {protocol}: {url}")
            print(f"  默认模型: {default_model}")
            print(f"  官方文档: {PROVIDER_DOCS_URLS[selected]}")
        for model in list_models(selected):
            context = _format_token_limit(model.context_window)
            max_output = _format_token_limit(model.max_output_tokens)
            modalities = "/".join(model.input_modalities)
            thinking = "强制" if model.thinking_required else "可选"
            efforts = "/".join(model.reasoning_efforts) or "模型自动"
            if not quiet:
                print(f"  - {model.model_id}: {model.summary}")
                print(
                    f"    上下文: {context} | 最大输出: {max_output} | "
                    f"输入: {modalities} | 思考: {thinking} | 推理强度: {efforts}"
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
    saved = _preference(resolved)
    preference = None if saved is None else {"provider": saved[0], "model": saved[1]}
    return envelope(
        ok=True,
        command="models",
        data={"updated": MODEL_CATALOG_UPDATED, "preference": preference, "providers": catalog},
    )


def resolve_use_model(explicit: str | None, provider: str, settings: Settings) -> str:
    if explicit is not None:
        chosen = explicit.strip()
        if not chosen:
            raise ToolError("模型 ID 不能为空", EXIT_DATA)
        return chosen
    return str(getattr(settings, f"{provider}_model")).strip()


def run_models_use(
    provider: str,
    model: str | None,
    *,
    settings: Settings | None = None,
) -> tuple[int, dict[str, Any]]:
    """写入偏好，不调用 LLM。"""
    resolved = settings or get_settings()
    try:
        selected = normalize_provider(provider)
        chosen = resolve_use_model(model, selected, resolved)
        save_preferences(preferences_path(settings=resolved), selected, chosen)
    except CredentialError as exc:
        raise ToolError(str(exc), EXIT_DATA) from exc
    message = f"已切换为 {selected} / {chosen}"
    return EXIT_OK, envelope(
        ok=True,
        command="models",
        data={"provider": selected, "model": chosen, "message": message},
    )


def register(subparsers: argparse._SubParsersAction) -> None:
    models = subparsers.add_parser("models", help="查看或切换 LLM Provider / 型号")
    models.add_argument("--provider", choices=SUPPORTED_PROVIDERS, default=None, help="只列出指定 Provider")
    action = models.add_subparsers(dest="models_action", metavar="<动作>")
    use = action.add_parser("use", help="切换并记住 Provider / 型号，供之后的 report 使用")
    use.add_argument("use_provider", choices=SUPPORTED_PROVIDERS, metavar="PROVIDER")
    use.add_argument(
        "use_model", nargs="?", default=None, metavar="MODEL", help="型号，省略则用该 Provider 的 .env 默认"
    )
    use.add_argument("--model", dest="use_model_flag", default=None, help="型号（覆盖位置参数）")
    models.set_defaults(
        handler="models",
        models_action="list",
        use_provider=None,
        use_model=None,
        use_model_flag=None,
    )
