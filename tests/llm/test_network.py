"""双 Provider 真实连通性测试；默认由 CI 跳过。"""

from __future__ import annotations

import json

import pytest

from src.config import get_settings
from src.llm.client import LLMClient
from src.llm.credentials import has_api_key


@pytest.mark.network
@pytest.mark.parametrize("provider", ["deepseek", "glm"])
def test_real_json_mode_without_reasoning(provider: str) -> None:
    """锐评子系统的调用形态：思考链关闭 + json_object，两家都必须返回可解析对象。"""
    settings = get_settings()
    if not has_api_key(provider, settings=settings):
        pytest.skip(f"未配置 {provider} API Key")

    client = LLMClient(provider=provider, settings=settings)
    response = client.chat_completion(
        system='你只输出一个 json 对象，形如 {"answer": "..."}。',
        user="用中文一句话介绍贵州茅台，放在 answer 字段。请输出 json。",
        temperature=0.0,
        max_tokens=200,
        reasoning=False,
        json_mode=True,
    )
    payload = json.loads(response.content)
    assert isinstance(payload, dict) and payload.get("answer")


@pytest.mark.network
def test_real_glm_chat_completion() -> None:
    settings = get_settings()
    if not has_api_key("glm", settings=settings):
        pytest.skip("未配置 GLM_API_KEY")

    client = LLMClient(provider="glm", settings=settings)
    response = client.chat_completion(
        system="你是一个简洁的中文助手。",
        user="只回复：连接成功",
        temperature=0.0,
        max_tokens=32,
        reasoning=False,
    )
    assert response.content.strip()
    assert response.model
