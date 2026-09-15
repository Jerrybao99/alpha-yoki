"""alpha-jerry CLI 交互与退出码单测。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import src.cli as cli
from src.config import Settings
from src.llm.credentials import CredentialError
from src.reports.reporting import Top20Result


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        data_dir=str(tmp_path),
        deepseek_api_key="",
        glm_api_key="",
    )


@pytest.fixture(autouse=True)
def _no_fallback_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """默认不构造备用 Provider，避免单测触碰系统钥匙串。"""
    monkeypatch.setattr(cli, "build_fallback_client", lambda *_args, **_kwargs: None)


def test_parser_accepts_provider_and_model() -> None:
    args = cli.build_parser().parse_args(
        ["report", "--provider", "glm", "--model", "glm-custom"]
    )
    assert args.command == "report"
    assert args.provider == "glm"
    assert args.model == "glm-custom"


def test_parser_accepts_models_command() -> None:
    args = cli.build_parser().parse_args(["models", "--provider", "deepseek"])
    assert args.command == "models"
    assert args.provider == "deepseek"


def test_parser_accepts_save_flag() -> None:
    args = cli.build_parser().parse_args(
        ["report", "--provider", "glm", "--model", "glm-5.3"]
    )
    assert args.save is True
    args = cli.build_parser().parse_args(["report", "--no-save"])
    assert args.save is False


def test_save_preferences_persists_last_choice(tmp_path: Path) -> None:
    cli.save_preferences(
        cli.preferences_path(settings=_settings(tmp_path)), "glm", "glm-5.3"
    )
    provider, model = cli.load_preferences(
        cli.preferences_path(settings=_settings(tmp_path))
    )
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


def test_noninteractive_report_requires_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "find_latest_csv", lambda _path: Path("scores.csv"))
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)
    assert cli.run_report(None, None, settings=_settings(tmp_path)) == cli.EXIT_CONFIG
    assert "--provider" in capsys.readouterr().err


def test_interactive_report_selects_provider_and_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict = {}
    monkeypatch.setattr(cli, "find_latest_csv", lambda _path: Path("scores.csv"))
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli, "select_provider", lambda: "glm")
    monkeypatch.setattr(cli, "select_model", lambda provider, default: "glm-5-turbo")
    monkeypatch.setattr(cli, "resolve_api_key", lambda *_args, **_kwargs: "secret")

    def fake_client(**kwargs):
        calls.update(kwargs)
        return SimpleNamespace(
            spec=SimpleNamespace(
                name=SimpleNamespace(value=kwargs["provider"]),
                model=kwargs["model"],
            )
        )

    monkeypatch.setattr(cli, "LLMClient", fake_client)
    monkeypatch.setattr(cli, "build_top20", lambda *_args, **_kwargs: Top20Result())
    monkeypatch.setattr(cli, "write_recommend_csv", lambda _result, path: path)
    monkeypatch.setattr(cli, "save_preferences", lambda *_args, **_kwargs: None)

    assert cli.run_report(None, None, settings=_settings(tmp_path)) == cli.EXIT_OK
    assert calls["provider"] == "glm"
    assert calls["model"] == "glm-5-turbo"


def test_interactive_report_persists_choice_to_preferences(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved: list[tuple[str, str]] = []
    monkeypatch.setattr(cli, "find_latest_csv", lambda _path: Path("scores.csv"))
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli, "select_provider", lambda: "glm")
    monkeypatch.setattr(cli, "select_model", lambda provider, default: "glm-5.3")
    monkeypatch.setattr(cli, "resolve_api_key", lambda *_args, **_kwargs: "secret")
    monkeypatch.setattr(
        cli,
        "save_preferences",
        lambda _path, provider, model: saved.append((provider, model)),
    )
    monkeypatch.setattr(cli, "build_top20", lambda *_args, **_kwargs: Top20Result())

    assert cli.run_report(None, None, settings=_settings(tmp_path)) == cli.EXIT_OK
    assert saved == [("glm", "glm-5.3")]


def test_interactive_report_no_save_skips_persistence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved: list[tuple[str, str]] = []
    monkeypatch.setattr(cli, "find_latest_csv", lambda _path: Path("scores.csv"))
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli, "select_provider", lambda: "glm")
    monkeypatch.setattr(cli, "select_model", lambda provider, default: "glm-5.3")
    monkeypatch.setattr(cli, "resolve_api_key", lambda *_args, **_kwargs: "secret")
    monkeypatch.setattr(
        cli,
        "save_preferences",
        lambda _path, provider, model: saved.append((provider, model)),
    )
    monkeypatch.setattr(cli, "build_top20", lambda *_args, **_kwargs: Top20Result())

    assert (
        cli.run_report(None, None, settings=_settings(tmp_path), save=False)
        == cli.EXIT_OK
    )
    assert saved == []


def test_noninteractive_report_auto_applies_saved_preference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: dict = {}
    preference_path = tmp_path / "llm_preferences.json"
    cli.save_preferences(preference_path, "glm", "glm-5.2")
    monkeypatch.setattr(cli, "find_latest_csv", lambda _path: Path("scores.csv"))
    monkeypatch.setattr(cli, "preferences_path", lambda settings=None: preference_path)
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(cli, "resolve_api_key", lambda *_args, **_kwargs: "secret")

    def fake_client(**kwargs):
        calls.update(kwargs)
        return SimpleNamespace(
            spec=SimpleNamespace(
                name=SimpleNamespace(value=kwargs["provider"]),
                model=kwargs["model"],
            )
        )

    monkeypatch.setattr(cli, "LLMClient", fake_client)
    monkeypatch.setattr(cli, "build_top20", lambda *_args, **_kwargs: Top20Result())
    monkeypatch.setattr(cli, "write_recommend_csv", lambda _result, path: path)

    assert cli.run_report(None, None, settings=_settings(tmp_path)) == cli.EXIT_OK
    assert calls["provider"] == "glm"
    assert calls["model"] == "glm-5.2"
    output = capsys.readouterr().out
    assert "已应用上次选择" in output


def test_noninteractive_report_without_preference_requires_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "find_latest_csv", lambda _path: Path("scores.csv"))
    monkeypatch.setattr(
        cli,
        "preferences_path",
        lambda settings=None: tmp_path / "missing.json",
    )
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)
    assert cli.run_report(None, None, settings=_settings(tmp_path)) == cli.EXIT_CONFIG
    assert "--provider" in capsys.readouterr().err


def test_missing_api_key_returns_config_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "find_latest_csv", lambda _path: Path("scores.csv"))
    monkeypatch.setattr(
        cli,
        "resolve_api_key",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(CredentialError("missing key")),
    )
    assert (
        cli.run_report("deepseek", None, settings=_settings(tmp_path))
        == cli.EXIT_CONFIG
    )
    assert "missing key" in capsys.readouterr().err


def test_report_passes_selected_provider_and_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: dict = {}
    score_path = Path("260915.csv")
    monkeypatch.setattr(cli, "find_latest_csv", lambda _path: score_path)
    monkeypatch.setattr(cli, "resolve_api_key", lambda *_args, **_kwargs: "secret")

    def fake_client(**kwargs):
        calls.update(kwargs)
        return SimpleNamespace(
            spec=SimpleNamespace(
                name=SimpleNamespace(value=kwargs["provider"]),
                model=kwargs["model"],
            )
        )

    monkeypatch.setattr(cli, "LLMClient", fake_client)
    monkeypatch.setattr(
        cli,
        "build_top20",
        lambda path, **_kwargs: Top20Result(rows=[]) if path == score_path else None,
    )
    monkeypatch.setattr(
        cli,
        "write_recommend_csv",
        lambda _result, path: path,
    )

    result = cli.run_report(
        "glm",
        "glm-custom",
        settings=_settings(tmp_path),
    )
    assert result == cli.EXIT_OK
    assert calls["provider"] == "glm"
    assert calls["model"] == "glm-custom"
    output = capsys.readouterr().out
    assert "Provider: glm" in output
    assert "Fallback: 规则模板" in output
    assert "secret" not in output


def test_report_passes_fallback_client_to_generator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    received: dict = {}
    fallback = SimpleNamespace(
        spec=SimpleNamespace(
            name=SimpleNamespace(value="deepseek"), model="deepseek-flash"
        )
    )
    monkeypatch.setattr(cli, "find_latest_csv", lambda _path: Path("scores.csv"))
    monkeypatch.setattr(cli, "resolve_api_key", lambda *_args, **_kwargs: "secret")
    monkeypatch.setattr(
        cli,
        "LLMClient",
        lambda **kwargs: SimpleNamespace(
            spec=SimpleNamespace(
                name=SimpleNamespace(value=kwargs["provider"]), model=kwargs["model"]
            )
        ),
    )
    monkeypatch.setattr(
        cli,
        "build_fallback_client",
        lambda primary, configured, **_kwargs: (
            fallback if (primary, configured) == ("glm", "auto") else None
        ),
    )

    def fake_build_top20(path, **kwargs):
        received.update(kwargs)
        return Top20Result()

    monkeypatch.setattr(cli, "build_top20", fake_build_top20)
    monkeypatch.setattr(cli, "write_recommend_csv", lambda _result, path: path)

    settings = _settings(tmp_path)
    assert cli.run_report("glm", "glm-5.3", settings=settings) == cli.EXIT_OK
    assert received["fallback_client"] is fallback
    assert received["settings"] is settings
    assert "Fallback: deepseek / deepseek-flash" in capsys.readouterr().out


def test_invalid_fallback_provider_is_config_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "find_latest_csv", lambda _path: Path("scores.csv"))
    monkeypatch.setattr(cli, "resolve_api_key", lambda *_args, **_kwargs: "secret")
    monkeypatch.setattr(
        cli,
        "LLMClient",
        lambda **kwargs: SimpleNamespace(
            spec=SimpleNamespace(name=SimpleNamespace(value="glm"), model="glm-5.3")
        ),
    )
    monkeypatch.setattr(
        cli,
        "build_fallback_client",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            CredentialError("不支持的 LLM Provider：nope")
        ),
    )
    assert (
        cli.run_report("glm", "glm-5.3", settings=_settings(tmp_path))
        == cli.EXIT_CONFIG
    )
    assert "不支持的 LLM Provider" in capsys.readouterr().err


def test_upstream_error_does_not_leak_exception_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "find_latest_csv", lambda _path: Path("scores.csv"))
    monkeypatch.setattr(cli, "resolve_api_key", lambda *_args, **_kwargs: "secret")
    monkeypatch.setattr(
        cli,
        "LLMClient",
        lambda **_kwargs: SimpleNamespace(
            spec=SimpleNamespace(
                name=SimpleNamespace(value="deepseek"),
                model="test-model",
            )
        ),
    )
    monkeypatch.setattr(
        cli,
        "build_top20",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("secret must not leak")
        ),
    )
    assert (
        cli.run_report("deepseek", None, settings=_settings(tmp_path))
        == cli.EXIT_UPSTREAM
    )
    error = capsys.readouterr().err
    assert "RuntimeError" in error
    assert "secret must not leak" not in error


def test_missing_scoring_csv_returns_data_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        cli.run_report("deepseek", None, settings=_settings(tmp_path)) == cli.EXIT_DATA
    )
    assert "无评分 CSV" in capsys.readouterr().err
