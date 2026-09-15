"""双 Provider 客户端单测。"""

from __future__ import annotations

from types import SimpleNamespace

from src.config import Settings
from src.llm.client import LLMClient, ProviderName, build_provider_spec


def _settings(**overrides) -> Settings:
    values = {
        "llm_provider": "deepseek",
        "deepseek_api_key": "",
        "deepseek_model": "deepseek-flash",
        "deepseek_base_url": "https://api.deepseek.com",
        "glm_api_key": "",
        "glm_model": "glm-5.3-flash",
        "glm_base_url": "https://open.bigmodel.cn/api/paas/v4/",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


class _Completions:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs["stream"]:
            return [
                SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content="chunk"))]
                )
            ]
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="response"))],
            model=kwargs["model"],
            usage=SimpleNamespace(prompt_tokens=4, completion_tokens=6),
        )


class _ClientFactory:
    def __init__(self) -> None:
        self.init_kwargs: dict = {}
        self.completions = _Completions()

    def __call__(self, **kwargs):
        self.init_kwargs = kwargs
        return SimpleNamespace(
            chat=SimpleNamespace(completions=self.completions),
        )


def test_deepseek_provider_defaults() -> None:
    spec = build_provider_spec(
        "deepseek",
        api_key="deepseek-secret",
        settings=_settings(),
    )
    assert spec.name is ProviderName.DEEPSEEK
    assert spec.model == "deepseek-flash"
    assert spec.base_url == "https://api.deepseek.com"
    assert "deepseek-secret" not in repr(spec)


def test_glm_provider_defaults_and_model_override() -> None:
    spec = build_provider_spec(
        "glm",
        model="glm-custom",
        api_key="glm-secret",
        settings=_settings(),
    )
    assert spec.name is ProviderName.GLM
    assert spec.model == "glm-custom"
    assert spec.base_url == "https://open.bigmodel.cn/api/paas/v4/"


def test_configured_default_provider_is_used() -> None:
    spec = build_provider_spec(
        api_key="glm-secret",
        settings=_settings(llm_provider="glm"),
    )
    assert spec.name is ProviderName.GLM


def test_deepseek_request_uses_provider_specific_reasoning_params() -> None:
    factory = _ClientFactory()
    client = LLMClient(
        provider="deepseek",
        api_key="secret",
        settings=_settings(),
        client_factory=factory,
    )
    response = client.chat_completion("system", "user")
    call = factory.completions.calls[0]
    assert call["reasoning_effort"] == "high"
    assert call["extra_body"] == {"thinking": {"type": "enabled"}}
    assert response.content == "response"
    assert response.input_tokens == 4
    assert response.output_tokens == 6


def test_glm_5_3_flash_uses_required_thinking_params() -> None:
    factory = _ClientFactory()
    client = LLMClient(
        provider="glm",
        api_key="secret",
        settings=_settings(),
        client_factory=factory,
    )
    client.chat_completion("system", "user")
    call = factory.completions.calls[0]
    assert call["reasoning_effort"] == "max"
    assert call["extra_body"] == {"thinking": {"type": "enabled"}}
    assert factory.init_kwargs["base_url"] == "https://open.bigmodel.cn/api/paas/v4/"


def test_required_thinking_model_maps_disabled_to_low_effort() -> None:
    factory = _ClientFactory()
    client = LLMClient(
        provider="glm",
        api_key="secret",
        settings=_settings(),
        client_factory=factory,
    )
    client.chat_completion("system", "user", reasoning=False)
    call = factory.completions.calls[0]
    assert call["extra_body"] == {"thinking": {"type": "enabled"}}
    assert call["reasoning_effort"] == "low"


def test_optional_thinking_model_can_disable_reasoning() -> None:
    factory = _ClientFactory()
    client = LLMClient(
        provider="glm",
        api_key="secret",
        settings=_settings(glm_model="glm-5-turbo"),
        client_factory=factory,
    )
    client.chat_completion("system", "user", reasoning=False)
    call = factory.completions.calls[0]
    assert call["extra_body"] == {"thinking": {"type": "disabled"}}
    assert "reasoning_effort" not in call


def test_deepseek_non_thinking_request_explicitly_disables_thinking() -> None:
    factory = _ClientFactory()
    client = LLMClient(
        provider="deepseek",
        api_key="secret",
        settings=_settings(),
        client_factory=factory,
    )
    client.chat_completion("system", "user", reasoning=False)
    call = factory.completions.calls[0]
    assert call["extra_body"] == {"thinking": {"type": "disabled"}}
    assert "reasoning_effort" not in call


def test_json_mode_sets_response_format_only_when_requested() -> None:
    factory = _ClientFactory()
    client = LLMClient(
        provider="deepseek",
        api_key="secret",
        settings=_settings(),
        client_factory=factory,
    )
    client.chat_completion("system", "user", reasoning=False)
    client.chat_completion("system", "user", reasoning=False, json_mode=True)
    plain, structured = factory.completions.calls
    assert "response_format" not in plain
    assert structured["response_format"] == {"type": "json_object"}


def test_stream_completion_normalizes_chunks() -> None:
    factory = _ClientFactory()
    client = LLMClient(
        provider="glm",
        api_key="secret",
        settings=_settings(),
        client_factory=factory,
    )
    assert list(client.stream_completion("system", "user")) == ["chunk"]
