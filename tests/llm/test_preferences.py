"""本地模型偏好持久化单测。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.llm.credentials import CredentialError
from src.llm.preferences import load_preferences, save_preferences


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "llm_preferences.json"
    save_preferences(path, "GLM", "glm-5-turbo")
    assert load_preferences(path) == ("glm", "glm-5-turbo")


def test_load_missing_file_returns_none(tmp_path: Path) -> None:
    assert load_preferences(tmp_path / "missing.json") is None


def test_load_corrupt_file_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "llm_preferences.json"
    path.write_text("not json", encoding="utf-8")
    assert load_preferences(path) is None


def test_load_invalid_provider_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "llm_preferences.json"
    path.write_text(
        json.dumps({"provider": "openai", "model": "gpt-x"}),
        encoding="utf-8",
    )
    assert load_preferences(path) is None


def test_load_empty_model_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "llm_preferences.json"
    path.write_text(json.dumps({"provider": "glm", "model": " "}), encoding="utf-8")
    assert load_preferences(path) is None


def test_save_creates_parent_directories(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "dir" / "llm_preferences.json"
    save_preferences(path, "deepseek", "deepseek-flash")
    assert load_preferences(path) == ("deepseek", "deepseek-flash")


def test_save_overwrites_previous_choice(tmp_path: Path) -> None:
    path = tmp_path / "llm_preferences.json"
    save_preferences(path, "glm", "glm-5.3")
    save_preferences(path, "deepseek", "deepseek-flash")
    assert load_preferences(path) == ("deepseek", "deepseek-flash")


def test_save_empty_model_raises(tmp_path: Path) -> None:
    with pytest.raises(CredentialError, match="不能为空"):
        save_preferences(tmp_path / "llm_preferences.json", "glm", "  ")
