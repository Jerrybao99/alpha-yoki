"""本地模型偏好持久化：保存并恢复最近一次 Provider / 模型选择。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.config import Settings, get_settings
from src.llm.credentials import SUPPORTED_PROVIDERS, CredentialError, normalize_provider

PREFERENCES_FILENAME = "llm_preferences.json"


def preferences_path(settings: Settings | None = None) -> Path:
    """返回偏好文件路径：data/cache/llm_preferences.json。"""
    return (settings or get_settings()).data_path("cache") / PREFERENCES_FILENAME


def load_preferences(path: Path) -> tuple[str, str] | None:
    """读取上次选择；缺失、损坏或不合法时返回 None，不阻断运行。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    provider = str(data.get("provider", "")).strip().lower()
    model = str(data.get("model", "")).strip()
    if provider not in SUPPORTED_PROVIDERS or not model:
        return None
    return provider, model


def save_preferences(path: Path, provider: str, model: str) -> None:
    """覆盖保存最近一次选择；写入失败抛 CredentialError，不静默吞异常。"""
    normalized = normalize_provider(provider)
    model_id = model.strip()
    if not model_id:
        raise CredentialError("模型 ID 不能为空")
    payload: dict[str, Any] = {"provider": normalized, "model": model_id}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise CredentialError(f"模型偏好写入失败：{exc}") from exc
