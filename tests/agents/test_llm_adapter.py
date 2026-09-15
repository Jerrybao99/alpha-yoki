"""LLM 适配层单测。mock 测试验证调用参数正确性与响应解析；
network 测试真实调用 DeepSeek 并断言返回非空。CI 通过 ``-m 'not network'`` 跳过 network。
"""

from __future__ import annotations

import pytest

from src.agents.llm_adapter import LLMClient, LLMResponse
from src.llm.credentials import has_api_key

# ===== mock 测试 =====


def test_llm_response_dataclass():
    r = LLMResponse(
        content="你好", model="deepseek-v4-pro", input_tokens=10, output_tokens=5
    )
    assert r.content == "你好"
    assert r.model == "deepseek-v4-pro"
    assert r.input_tokens == 10
    assert r.output_tokens == 5
    assert isinstance(r, LLMResponse)


def test_llm_response_is_frozen():
    r = LLMResponse(content="test", model="x", input_tokens=0, output_tokens=0)
    with pytest.raises(Exception):
        r.content = "modified"  # type: ignore[misc]


def test_llm_client_importable():
    client = LLMClient(model="test-model", api_key="test-key")
    assert client._model == "test-model"


def test_llm_client_default_model():
    from src.config import Settings

    client = LLMClient(api_key="test-key", settings=Settings(_env_file=None))
    assert client._model == "deepseek-flash"


def test_chat_completion_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    """mock OpenAI 客户端，验证 chat_completion 参数构造与响应解析。"""
    last_kw: dict = {}

    class _FakeChoice:
        class _Msg:
            content = "mock response"

        def __init__(self):
            self.message = self._Msg()
            self.index = 0

    class _FakeUsage:
        prompt_tokens = 5
        completion_tokens = 10
        total_tokens = 15

    class _FakeCompletions:
        def create(self, **kw):
            last_kw.update(kw)
            return type(
                "_F",
                (),
                {
                    "choices": [_FakeChoice()],
                    "model": "mock-model",
                    "usage": _FakeUsage(),
                },
            )()

    class _FakeChat:
        def __init__(self):
            self.completions = _FakeCompletions()

    class _FakeOpenAI:
        def __init__(self):
            self.chat = _FakeChat()

    client = LLMClient(model="test-model", api_key="test-key")
    monkeypatch.setattr(client, "_client", _FakeOpenAI())
    resp = client.chat_completion(
        system="你是助手", user="你好", temperature=0.5, max_tokens=128
    )
    assert resp.content == "mock response"
    assert resp.model == "mock-model"
    assert resp.input_tokens == 5
    assert resp.output_tokens == 10
    assert last_kw["model"] == "test-model"
    assert last_kw["messages"] == [
        {"role": "system", "content": "你是助手"},
        {"role": "user", "content": "你好"},
    ]
    assert last_kw["temperature"] == 0.5
    assert last_kw["max_tokens"] == 128
    assert last_kw["stream"] is False


def _reasoning_only_openai():
    """构造 content 为空、仅有 reasoning_content 的假客户端。"""
    from types import SimpleNamespace

    message = SimpleNamespace(content="", reasoning_content="thinking...")
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=message, index=0)],
        model="mock-model",
        usage=SimpleNamespace(prompt_tokens=3, completion_tokens=8, total_tokens=11),
    )
    completions = SimpleNamespace(create=lambda **kw: response)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


def test_chat_completion_never_uses_reasoning_as_content_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """content 为空时默认返回空串，思考链绝不冒充正文。"""
    client = LLMClient(model="test-model", api_key="test-key")
    monkeypatch.setattr(client, "_client", _reasoning_only_openai())
    resp = client.chat_completion(system="", user="", max_tokens=64)
    assert resp.content == ""
    assert resp.input_tokens == 3


def test_chat_completion_reasoning_fallback_is_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """显式 reasoning_fallback=True 才允许回退取 reasoning_content。"""
    client = LLMClient(model="test-model", api_key="test-key")
    monkeypatch.setattr(client, "_client", _reasoning_only_openai())
    resp = client.chat_completion(
        system="", user="", max_tokens=64, reasoning_fallback=True
    )
    assert resp.content == "thinking..."


def test_stream_completion_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    """mock OpenAI 流式响应，验证 stream_completion 逐块输出和参数。"""
    last_kw: dict = {}

    class _FakeDelta:
        content = "mock"

    class _FakeChoice:
        delta = _FakeDelta()

    class _FakeDeltaReasoning:
        content = ""
        reasoning_content = "think"

    class _FakeChoiceReasoning:
        delta = _FakeDeltaReasoning()

    class _FakeStream:
        def __iter__(self):
            yield type("_F", (), {"choices": [_FakeChoice()]})()
            yield type("_F", (), {"choices": [_FakeChoiceReasoning()]})()

    class _FakeCompletions:
        def create(self, **kw):
            last_kw.update(kw)
            return _FakeStream()

    class _FakeChat:
        def __init__(self):
            self.completions = _FakeCompletions()

    class _FakeOpenAI:
        def __init__(self):
            self.chat = _FakeChat()

    client = LLMClient(model="test-model", api_key="test-key")
    monkeypatch.setattr(client, "_client", _FakeOpenAI())
    chunks = list(
        client.stream_completion(
            system="你是助手", user="你好", temperature=0.7, max_tokens=512
        )
    )
    assert chunks == ["mock"]
    assert last_kw["model"] == "test-model"
    assert last_kw["stream"] is True

    with_reasoning = list(
        client.stream_completion(
            system="你是助手",
            user="你好",
            temperature=0.7,
            max_tokens=512,
            reasoning_fallback=True,
        )
    )
    assert with_reasoning == ["mock", "think"]


# ===== network 测试 =====


@pytest.mark.network
def test_real_chat_completion() -> None:
    """真实调用 DeepSeek，断言返回非空、token 计数有效。

    ``uv run pytest -m network tests/test_llm_adapter.py::test_real_chat_completion``
    """
    from src.config import get_settings

    settings = get_settings()
    if not has_api_key("deepseek", settings=settings):
        pytest.skip("未配置 DEEPSEEK_API_KEY")

    client = LLMClient(provider="deepseek", settings=settings)
    resp = client.chat_completion(
        system="你是一个股票分析助手，用简短中文回答。",
        user="一句话介绍贵州茅台。",
        temperature=0.3,
        max_tokens=128,
    )
    assert resp.content, "LLM 返回内容为空"
    assert resp.model, "模型名为空"
    assert resp.input_tokens > 0, "输入 token 应为正数"
    assert resp.output_tokens > 0, "输出 token 应为正数"


@pytest.mark.network
def test_real_stream_completion() -> None:
    """真实流式调用 DeepSeek，断言逐块累积后非空。

    ``uv run pytest -m network tests/test_llm_adapter.py::test_real_stream_completion``
    """
    from src.config import get_settings

    settings = get_settings()
    if not has_api_key("deepseek", settings=settings):
        pytest.skip("未配置 DEEPSEEK_API_KEY")

    client = LLMClient(provider="deepseek", settings=settings)
    chunks: list[str] = []
    for chunk in client.stream_completion(
        system="你是一个股票分析助手，用简短中文回答。",
        user="一句话介绍比亚迪。",
        temperature=0.3,
        max_tokens=128,
    ):
        chunks.append(chunk)

    result = "".join(chunks)
    assert result, "流式返回内容为空"


@pytest.mark.network
def test_chat_completion_with_low_temperature() -> None:
    """低温调用校验输出稳定。"""
    from src.config import get_settings

    settings = get_settings()
    if not has_api_key("deepseek", settings=settings):
        pytest.skip("未配置 DEEPSEEK_API_KEY")

    client = LLMClient(provider="deepseek", settings=settings)
    resp1 = client.chat_completion(
        system="你是数学助手，只输出数字。",
        user="1+1等于几？",
        temperature=0.0,
        max_tokens=10,
        reasoning=False,
    )
    resp2 = client.chat_completion(
        system="你是数学助手，只输出数字。",
        user="1+1等于几？",
        temperature=0.0,
        max_tokens=10,
        reasoning=False,
    )
    assert resp1.content.strip(), "第 1 次调用为空"
    assert resp2.content.strip(), "第 2 次调用为空"
