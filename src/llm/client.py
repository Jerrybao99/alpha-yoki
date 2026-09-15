"""DeepSeek / GLM 的 OpenAI 兼容客户端。"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from openai import OpenAI

from src.config import Settings, get_settings
from src.llm.catalog import find_model
from src.llm.credentials import CredentialError, get_stored_api_key, normalize_provider


class ProviderName(StrEnum):
    DEEPSEEK = "deepseek"
    GLM = "glm"


@dataclass(frozen=True)
class ProviderSpec:
    name: ProviderName
    model: str
    base_url: str
    api_key: str = field(repr=False)


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str
    input_tokens: int
    output_tokens: int


def build_provider_spec(
    provider: str | ProviderName | None = None,
    *,
    model: str | None = None,
    api_key: str | None = None,
    settings: Settings | None = None,
) -> ProviderSpec:
    """根据配置构造 ProviderSpec；本函数不触发交互输入。"""
    resolved_settings = settings or get_settings()
    selected = normalize_provider(str(provider or resolved_settings.llm_provider))
    provider_name = ProviderName(selected)

    configured_model = getattr(resolved_settings, f"{selected}_model")
    configured_base_url = getattr(resolved_settings, f"{selected}_base_url")
    resolved_key = (api_key or "").strip() or get_stored_api_key(
        selected, settings=resolved_settings
    )
    if not resolved_key:
        raise CredentialError(
            f"缺少 {selected} API Key；请通过 CLI 交互输入或配置环境变量。"
        )

    return ProviderSpec(
        name=provider_name,
        model=(model or configured_model).strip(),
        base_url=str(configured_base_url).strip(),
        api_key=resolved_key,
    )


class LLMClient:
    """统一的 DeepSeek / GLM Chat Completions 客户端。"""

    def __init__(
        self,
        model: str | None = None,
        *,
        provider: str | ProviderName | None = None,
        api_key: str | None = None,
        settings: Settings | None = None,
        client_factory: Callable[..., Any] = OpenAI,
    ) -> None:
        self.spec = build_provider_spec(
            provider,
            model=model,
            api_key=api_key,
            settings=settings,
        )
        self._provider = self.spec.name
        self._model = self.spec.model
        self._client = client_factory(
            api_key=self.spec.api_key,
            base_url=self.spec.base_url,
        )

    def _params(
        self,
        system: str,
        user: str,
        *,
        temperature: float,
        max_tokens: int,
        stream: bool,
        reasoning: bool,
        json_mode: bool = False,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if json_mode:
            params["response_format"] = {"type": "json_object"}
        model_spec = find_model(self._provider.value, self._model)
        thinking_required = bool(model_spec and model_spec.thinking_required)
        if reasoning or thinking_required:
            params["extra_body"] = {"thinking": {"type": "enabled"}}
            if thinking_required and not reasoning:
                params["reasoning_effort"] = "low"
            elif model_spec and model_spec.default_reasoning_effort:
                params["reasoning_effort"] = model_spec.default_reasoning_effort
            elif self._provider is ProviderName.DEEPSEEK:
                params["reasoning_effort"] = "high"
        else:
            params["extra_body"] = {"thinking": {"type": "disabled"}}
        return params

    def chat_completion(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 256,
        reasoning: bool = True,
        reasoning_fallback: bool = False,
        json_mode: bool = False,
    ) -> LLMResponse:
        """执行非流式补全并归一化文本与 token 统计。

        思考链（reasoning_content）默认不冒充正文；仅 ``reasoning_fallback=True`` 时
        在 content 为空的情况下回退取用，供调试类场景显式选择。
        ``json_mode=True`` 启用 OpenAI 兼容的 ``response_format=json_object``，
        调用方需在提示词中包含 "json" 字样（DeepSeek / GLM 官方要求）。
        """
        resp = self._client.chat.completions.create(
            **self._params(
                system,
                user,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
                reasoning=reasoning,
                json_mode=json_mode,
            )
        )
        choice = resp.choices[0].message
        content = choice.content or ""
        if not content and reasoning_fallback:
            content = getattr(choice, "reasoning_content", "") or ""
        usage = getattr(resp, "usage", None)
        return LLMResponse(
            content=content,
            model=str(resp.model),
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )

    def stream_completion(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 512,
        reasoning: bool = True,
        reasoning_fallback: bool = False,
    ) -> Iterator[str]:
        """执行流式补全，只产出非空正文片段；思考链片段仅在显式开启时产出。"""
        stream = self._client.chat.completions.create(
            **self._params(
                system,
                user,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                reasoning=reasoning,
            )
        )
        for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta is None:
                continue
            text = delta.content or ""
            if not text and reasoning_fallback:
                text = getattr(delta, "reasoning_content", "") or ""
            if text:
                yield text
