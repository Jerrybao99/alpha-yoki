"""LLM 适配层：统一 chat_completion / stream_completion 接口，默认接入 DeepSeek。
通过 OpenAI 兼容接口调用，业务代码不直接依赖具体 SDK，换模型只改适配层一行配置。
一行代码发 prompt，自动开最高深度思考，返回结果或流式输出
"""

from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI

from src.config import get_settings


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str
    input_tokens: int
    output_tokens: int


class LLMClient:
    """DeepSeek LLM 客户端，OpenAI 兼容接口。"""

    def __init__(self, model: str | None = None) -> None:
        settings = get_settings()
        self._client = OpenAI(
            api_key=settings.deepseek_api_key or "sk-placeholder",
            base_url=settings.deepseek_base_url,
        )
        self._model = model or settings.deepseek_model

    def chat_completion(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 256,
        reasoning: bool = True,
    ) -> LLMResponse:
        """单次对话补全，返回 LLMResponse。reasoning=True 时启用最高深度思考模式。"""
        params: dict = dict(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
        )
        if reasoning:
            params["reasoning_effort"] = "high"
            params["extra_body"] = {"thinking": {"type": "enabled"}}
        resp = self._client.chat.completions.create(**params)
        choice = resp.choices[0].message
        content = choice.content or ""
        # DeepSeek V4 Pro 等推理模型可能 content 为空，实际内容在 reasoning_content
        if not content:
            content = getattr(choice, "reasoning_content", "") or ""
        return LLMResponse(
            content=content,
            model=resp.model,
            input_tokens=resp.usage.prompt_tokens if resp.usage else 0,
            output_tokens=resp.usage.completion_tokens if resp.usage else 0,
        )

    def stream_completion(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 512,
        reasoning: bool = True,
    ):
        """流式对话补全，返回 chunk 迭代器。reasoning=True 时启用深度思考模式。"""
        params: dict = dict(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        if reasoning:
            params["reasoning_effort"] = "high"
            params["extra_body"] = {"thinking": {"type": "enabled"}}
        stream = self._client.chat.completions.create(**params)
        for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta:
                text = delta.content or ""
                if not text:
                    text = getattr(delta, "reasoning_content", "") or ""
                if text:
                    yield text
