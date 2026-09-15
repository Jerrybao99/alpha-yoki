"""models use：切换并记住 Provider / 型号，不跑 report。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import src.cli as cli
from src.llm.preferences import load_preferences, preferences_path
from tests.test_cli import settings_for


def test_parser_accepts_models_use_provider_and_model() -> None:
    parser = cli.build_parser()
    named = parser.parse_args(["models", "use", "glm"])
    assert named.models_action == "use"
    assert named.use_provider == "glm"
    assert named.use_model is None
    positional = parser.parse_args(["models", "use", "deepseek", "deepseek-v4-pro"])
    assert positional.use_provider == "deepseek"
    assert positional.use_model == "deepseek-v4-pro"
    flagged = parser.parse_args(["models", "use", "glm", "--model", "glm-5-turbo"])
    assert flagged.use_model_flag == "glm-5-turbo"


def test_models_use_glm_writes_env_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = settings_for(tmp_path)
    monkeypatch.setattr("src.config.get_settings", lambda: settings)
    assert cli.main(["models", "use", "glm"]) == cli.EXIT_OK
    assert load_preferences(preferences_path(settings=settings)) == ("glm", settings.glm_model)
    assert f"已切换为 glm / {settings.glm_model}" in capsys.readouterr().out


def test_models_use_deepseek_positional_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = settings_for(tmp_path)
    monkeypatch.setattr("src.config.get_settings", lambda: settings)
    assert cli.main(["models", "use", "deepseek", "deepseek-v4-pro"]) == cli.EXIT_OK
    assert load_preferences(preferences_path(settings=settings)) == ("deepseek", "deepseek-v4-pro")


def test_models_use_model_flag_overrides_positional(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = settings_for(tmp_path)
    monkeypatch.setattr("src.config.get_settings", lambda: settings)
    assert cli.main(["models", "use", "glm", "glm-5.3", "--model", "glm-5-turbo"]) == cli.EXIT_OK
    assert load_preferences(preferences_path(settings=settings)) == ("glm", "glm-5-turbo")


def test_models_use_blank_model_is_data_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = settings_for(tmp_path)
    monkeypatch.setattr("src.config.get_settings", lambda: settings)
    assert cli.main(["models", "use", "glm", "--model", "   "]) == cli.EXIT_DATA
    assert load_preferences(preferences_path(settings=settings)) is None


def test_models_list_includes_saved_preference(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = settings_for(tmp_path)
    cli.save_preferences(preferences_path(settings=settings), "glm", "glm-5-turbo")
    assert cli.run_models(None, settings=settings) == cli.EXIT_OK
    output = capsys.readouterr().out
    assert "当前偏好：glm / glm-5-turbo" in output


def test_models_json_use_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = settings_for(tmp_path)
    monkeypatch.setattr("src.config.get_settings", lambda: settings)
    monkeypatch.setattr(cli.sys.stdout, "isatty", lambda: False)
    assert cli.main(["--json", "models", "use", "deepseek"]) == cli.EXIT_OK
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["ok"] is True
    assert payload["command"] == "models"
    assert payload["data"]["provider"] == "deepseek"
    assert payload["data"]["model"] == settings.deepseek_model
