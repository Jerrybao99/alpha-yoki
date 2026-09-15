"""alpha-jerry CLI：参数解析、交互选择与模型目录单测。"""

from __future__ import annotations

from pathlib import Path

import pytest

import src.cli as cli
from src.config import Settings


def settings_for(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        data_dir=str(tmp_path),
        deepseek_api_key="",
        glm_api_key="",
    )


def test_parser_accepts_provider_and_model() -> None:
    args = cli.build_parser().parse_args(["report", "--provider", "glm", "--model", "glm-custom"])
    assert args.command == "report"
    assert args.provider == "glm"
    assert args.model == "glm-custom"


def test_parser_accepts_models_command() -> None:
    args = cli.build_parser().parse_args(["models", "--provider", "deepseek"])
    assert args.command == "models"
    assert args.provider == "deepseek"


def test_parser_accepts_save_flag() -> None:
    args = cli.build_parser().parse_args(["report", "--provider", "glm", "--model", "glm-5.3"])
    assert args.save is True
    args = cli.build_parser().parse_args(["report", "--no-save"])
    assert args.save is False


def test_save_preferences_persists_last_choice(tmp_path: Path) -> None:
    cli.save_preferences(cli.preferences_path(settings=settings_for(tmp_path)), "glm", "glm-5.3")
    provider, model = cli.load_preferences(cli.preferences_path(settings=settings_for(tmp_path)))
    assert (provider, model) == ("glm", "glm-5.3")


def test_select_provider_retries_invalid_input(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    answers = iter(["invalid", "2"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    assert cli.select_provider() == "glm"
    assert "输入无效" in capsys.readouterr().err


def test_select_model_uses_numbered_choice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("builtins.input", lambda _prompt: "2")
    assert cli.select_model("deepseek", "deepseek-flash") == "deepseek-v4-pro"


def test_select_model_uses_configured_default_on_enter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("builtins.input", lambda _prompt: "")
    assert cli.select_model("glm", "glm-5.3-flash") == "glm-5.3-flash"


def test_select_model_accepts_custom_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = iter(["c", "future-model"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    assert cli.select_model("glm", "glm-5.2") == "future-model"


def test_models_command_lists_endpoints_and_models(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.run_models(None, settings=Settings(_env_file=None)) == cli.EXIT_OK
    output = capsys.readouterr().out
    assert "https://api.deepseek.com" in output
    assert "deepseek-flash" in output
    assert "https://open.bigmodel.cn/api/paas/v4/" in output
    assert "glm-5.3" in output
    assert "上下文: 1M" in output
    assert "最大输出: 128K" in output


def test_parser_registers_all_subcommands() -> None:
    parser = cli.build_parser()
    for command in ("status", "collect", "scores", "screen", "holdings", "report", "models", "wechat"):
        extra = []
        if command == "holdings":
            extra = ["list"]
        elif command == "wechat":
            extra = ["status"]
        args = parser.parse_args([command, *extra])
        assert args.command == command


def test_main_json_emits_single_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import json

    monkeypatch.setattr("src.config.get_settings", lambda: settings_for(tmp_path))
    monkeypatch.setattr(cli.sys.stdout, "isatty", lambda: False)
    code = cli.main(["--json", "status", "--check"])
    out = capsys.readouterr().out.strip()
    assert code == cli.EXIT_DATA
    payload = json.loads(out)
    assert set(payload) == {"ok", "command", "data", "error"}
    assert payload["command"] == "status"
    assert out.count("{") >= 1


def test_main_non_tty_has_no_banner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("src.config.get_settings", lambda: settings_for(tmp_path))
    monkeypatch.setattr(cli.sys.stdout, "isatty", lambda: False)
    cli.main(["status"])
    output = capsys.readouterr().out
    assert "🐰" not in output
    assert "alpha-jerry v" not in output
