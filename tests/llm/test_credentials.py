"""系统钥匙串凭据解析单测。"""

from __future__ import annotations

from io import StringIO

import pytest
from keyring.errors import KeyringError

from src.config import Settings
from src.llm.credentials import (
    SERVICE_NAME,
    CredentialError,
    get_stored_api_key,
    has_api_key,
    normalize_provider,
    resolve_api_key,
)


class _FakeKeyring:
    def __init__(self, values: dict[tuple[str, str], str] | None = None) -> None:
        self.values = values or {}
        self.get_calls = 0
        self.set_calls: list[tuple[str, str, str]] = []
        self.fail_get = False
        self.fail_set = False

    def get_password(self, service: str, username: str) -> str | None:
        self.get_calls += 1
        if self.fail_get:
            raise KeyringError("backend unavailable")
        return self.values.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        if self.fail_set:
            raise KeyringError("write failed")
        self.set_calls.append((service, username, password))
        self.values[(service, username)] = password


def _settings(**overrides: str) -> Settings:
    values = {
        "deepseek_api_key": "",
        "glm_api_key": "",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_environment_key_has_priority() -> None:
    backend = _FakeKeyring({(SERVICE_NAME, "deepseek_api_key"): "stored"})
    key = resolve_api_key(
        "deepseek",
        settings=_settings(deepseek_api_key="environment"),
        backend=backend,
        interactive=False,
    )
    assert key == "environment"
    assert backend.get_calls == 0


def test_keyring_is_used_when_environment_is_empty() -> None:
    backend = _FakeKeyring({(SERVICE_NAME, "glm_api_key"): "stored-glm"})
    assert (
        get_stored_api_key("glm", settings=_settings(), backend=backend) == "stored-glm"
    )
    assert has_api_key("glm", settings=_settings(), backend=backend)


def test_interactive_prompt_saves_to_keyring_without_leaking_secret() -> None:
    backend = _FakeKeyring()
    output = StringIO()
    key = resolve_api_key(
        "glm",
        settings=_settings(),
        backend=backend,
        interactive=True,
        secret_prompt=lambda _prompt: "prompt-secret",
        answer_prompt=lambda _prompt: "",
        output=output,
    )
    assert key == "prompt-secret"
    assert backend.set_calls == [(SERVICE_NAME, "glm_api_key", "prompt-secret")]
    assert "prompt-secret" not in output.getvalue()
    assert "已保存" in output.getvalue()


def test_interactive_prompt_can_skip_save() -> None:
    backend = _FakeKeyring()
    key = resolve_api_key(
        "deepseek",
        settings=_settings(),
        backend=backend,
        interactive=True,
        secret_prompt=lambda _prompt: "one-shot",
        answer_prompt=lambda _prompt: "n",
    )
    assert key == "one-shot"
    assert backend.set_calls == []


def test_unavailable_keyring_uses_key_for_current_run() -> None:
    backend = _FakeKeyring()
    backend.fail_get = True
    output = StringIO()
    key = resolve_api_key(
        "glm",
        settings=_settings(),
        backend=backend,
        interactive=True,
        secret_prompt=lambda _prompt: "temporary",
        output=output,
    )
    assert key == "temporary"
    assert "仅用于本次运行" in output.getvalue()
    assert "temporary" not in output.getvalue()


def test_noninteractive_missing_key_fails_fast() -> None:
    with pytest.raises(CredentialError, match="GLM_API_KEY"):
        resolve_api_key(
            "glm",
            settings=_settings(),
            backend=_FakeKeyring(),
            interactive=False,
        )


def test_empty_interactive_key_is_rejected() -> None:
    with pytest.raises(CredentialError, match="不能为空"):
        resolve_api_key(
            "deepseek",
            settings=_settings(),
            backend=_FakeKeyring(),
            interactive=True,
            secret_prompt=lambda _prompt: " ",
        )


def test_invalid_provider_is_rejected() -> None:
    with pytest.raises(CredentialError, match="不支持"):
        normalize_provider("other")
