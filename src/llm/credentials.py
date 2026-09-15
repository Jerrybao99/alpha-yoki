"""API Key 解析与系统钥匙串持久化。"""

from __future__ import annotations

import getpass
import sys
from collections.abc import Callable
from typing import Any, TextIO

import keyring
from keyring.errors import KeyringError

from src.config import Settings, get_settings

SERVICE_NAME = "alpha-jerry"
SUPPORTED_PROVIDERS: tuple[str, ...] = ("deepseek", "glm")

_SETTINGS_KEY_ATTR = {
    "deepseek": "deepseek_api_key",
    "glm": "glm_api_key",
}


class CredentialError(RuntimeError):
    """Provider 或 API Key 配置无效。"""


def normalize_provider(provider: str) -> str:
    """规范化 Provider 名；不支持时明确失败。"""
    normalized = provider.strip().lower()
    if normalized not in SUPPORTED_PROVIDERS:
        supported = ", ".join(SUPPORTED_PROVIDERS)
        raise CredentialError(f"不支持的 LLM Provider：{provider}；可选值：{supported}")
    return normalized


def _keyring_username(provider: str) -> str:
    return f"{provider}_api_key"


def _settings_api_key(provider: str, settings: Settings) -> str | None:
    value = str(getattr(settings, _SETTINGS_KEY_ATTR[provider], "")).strip()
    return value or None


def get_stored_api_key(
    provider: str,
    *,
    settings: Settings | None = None,
    backend: Any | None = None,
) -> str | None:
    """按环境配置→系统钥匙串顺序读取密钥，不触发终端输入。"""
    normalized = normalize_provider(provider)
    resolved_settings = settings or get_settings()
    configured = _settings_api_key(normalized, resolved_settings)
    if configured:
        return configured

    keyring_backend = backend or keyring
    try:
        stored = keyring_backend.get_password(SERVICE_NAME, _keyring_username(normalized))
    except KeyringError:
        return None
    if stored is None:
        return None
    stripped = str(stored).strip()
    return stripped or None


def has_api_key(
    provider: str,
    *,
    settings: Settings | None = None,
    backend: Any | None = None,
) -> bool:
    """检查配置或钥匙串是否存在密钥，不输出密钥内容。"""
    return get_stored_api_key(provider, settings=settings, backend=backend) is not None


def resolve_api_key(
    provider: str,
    *,
    settings: Settings | None = None,
    interactive: bool | None = None,
    backend: Any | None = None,
    secret_prompt: Callable[[str], str] | None = None,
    answer_prompt: Callable[[str], str] | None = None,
    output: TextIO | None = None,
) -> str:
    """解析 API Key；缺失时在 TTY 隐藏输入并可保存到系统钥匙串。"""
    normalized = normalize_provider(provider)
    resolved_settings = settings or get_settings()
    configured = _settings_api_key(normalized, resolved_settings)
    if configured:
        return configured

    keyring_backend = backend or keyring
    keyring_available = True
    try:
        stored = keyring_backend.get_password(SERVICE_NAME, _keyring_username(normalized))
    except KeyringError:
        stored = None
        keyring_available = False
    if stored and str(stored).strip():
        return str(stored).strip()

    is_interactive = sys.stdin.isatty() if interactive is None else interactive
    if not is_interactive:
        env_name = _SETTINGS_KEY_ATTR[normalized].upper()
        raise CredentialError(f"缺少 {normalized} API Key。请设置 {env_name}，或在交互终端运行命令以保存到系统钥匙串。")

    ask_secret = secret_prompt or getpass.getpass
    api_key = ask_secret(f"请输入 {normalized} API Key（输入隐藏）: ").strip()
    if not api_key:
        raise CredentialError(f"{normalized} API Key 不能为空")

    stream = output or sys.stderr
    if not keyring_available:
        print("系统钥匙串不可用，API Key 仅用于本次运行。", file=stream)
        return api_key

    ask_answer = answer_prompt or input
    try:
        answer = ask_answer("保存到系统钥匙串？[Y/n]: ").strip().lower()
    except EOFError:
        answer = "n"
    if answer in {"", "y", "yes", "是"}:
        try:
            keyring_backend.set_password(SERVICE_NAME, _keyring_username(normalized), api_key)
        except KeyringError:
            print("系统钥匙串保存失败，API Key 仅用于本次运行。", file=stream)
        else:
            print(f"{normalized} API Key 已保存到系统钥匙串。", file=stream)

    return api_key
