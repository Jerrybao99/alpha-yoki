"""alpha-jerry report 子命令：退出码、密钥与 fallback 接驳单测。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import src.tools.report as cli
from src.llm.credentials import CredentialError
from src.reports.reporting import Top20Result
from tests.test_cli import settings_for


@pytest.fixture(autouse=True)
def _no_fallback_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """默认不构造备用 Provider，避免单测触碰系统钥匙串。"""
    monkeypatch.setattr(cli, "build_fallback_client", lambda *_args, **_kwargs: None)


def _client(**kwargs):
    return SimpleNamespace(
        spec=SimpleNamespace(
            name=SimpleNamespace(value=kwargs["provider"]),
            model=kwargs["model"],
        )
    )


def test_noninteractive_report_requires_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "find_latest_csv", lambda _path: Path("scores.csv"))
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)
    assert cli.run_report(None, None, settings=settings_for(tmp_path)) == cli.EXIT_CONFIG
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
        return _client(**kwargs)

    monkeypatch.setattr(cli, "LLMClient", fake_client)
    monkeypatch.setattr(cli, "build_top20", lambda *_args, **_kwargs: Top20Result())
    monkeypatch.setattr(cli, "write_recommend_csv", lambda _result, path: path)
    monkeypatch.setattr(cli, "save_preferences", lambda *_args, **_kwargs: None)

    assert cli.run_report(None, None, settings=settings_for(tmp_path)) == cli.EXIT_OK
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

    assert cli.run_report(None, None, settings=settings_for(tmp_path)) == cli.EXIT_OK
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

    assert cli.run_report(None, None, settings=settings_for(tmp_path), save=False) == cli.EXIT_OK
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
        return _client(**kwargs)

    monkeypatch.setattr(cli, "LLMClient", fake_client)
    monkeypatch.setattr(cli, "build_top20", lambda *_args, **_kwargs: Top20Result())
    monkeypatch.setattr(cli, "write_recommend_csv", lambda _result, path: path)

    assert cli.run_report(None, None, settings=settings_for(tmp_path)) == cli.EXIT_OK
    assert calls["provider"] == "glm"
    assert calls["model"] == "glm-5.2"
    assert "已应用上次选择" in capsys.readouterr().out


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
    assert cli.run_report(None, None, settings=settings_for(tmp_path)) == cli.EXIT_CONFIG
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
    assert cli.run_report("deepseek", None, settings=settings_for(tmp_path)) == cli.EXIT_CONFIG
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
    monkeypatch.setattr(cli, "LLMClient", lambda **kwargs: calls.update(kwargs) or _client(**kwargs))
    monkeypatch.setattr(
        cli,
        "build_top20",
        lambda path, **_kwargs: Top20Result(rows=[]) if path == score_path else None,
    )
    monkeypatch.setattr(cli, "write_recommend_csv", lambda _result, path: path)

    result = cli.run_report("glm", "glm-custom", settings=settings_for(tmp_path))
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
    fallback = SimpleNamespace(spec=SimpleNamespace(name=SimpleNamespace(value="deepseek"), model="deepseek-flash"))
    monkeypatch.setattr(cli, "find_latest_csv", lambda _path: Path("scores.csv"))
    monkeypatch.setattr(cli, "resolve_api_key", lambda *_args, **_kwargs: "secret")
    monkeypatch.setattr(cli, "LLMClient", lambda **kwargs: _client(**kwargs))
    monkeypatch.setattr(
        cli,
        "build_fallback_client",
        lambda primary, configured, **_kwargs: fallback if (primary, configured) == ("glm", "auto") else None,
    )
    monkeypatch.setattr(
        cli,
        "build_top20",
        lambda path, **kwargs: received.update(kwargs) or Top20Result(),
    )
    monkeypatch.setattr(cli, "write_recommend_csv", lambda _result, path: path)

    settings = settings_for(tmp_path)
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
    monkeypatch.setattr(cli, "LLMClient", lambda **kwargs: _client(provider="glm", model="glm-5.3"))
    monkeypatch.setattr(
        cli,
        "build_fallback_client",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(CredentialError("不支持的 LLM Provider：nope")),
    )
    assert cli.run_report("glm", "glm-5.3", settings=settings_for(tmp_path)) == cli.EXIT_CONFIG
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
            spec=SimpleNamespace(name=SimpleNamespace(value="deepseek"), model="test-model")
        ),
    )
    monkeypatch.setattr(
        cli,
        "build_top20",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("secret must not leak")),
    )
    assert cli.run_report("deepseek", None, settings=settings_for(tmp_path)) == cli.EXIT_UPSTREAM
    error = capsys.readouterr().err
    assert "RuntimeError" in error
    assert "secret must not leak" not in error


def test_missing_scoring_csv_returns_data_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.run_report("deepseek", None, settings=settings_for(tmp_path)) == cli.EXIT_DATA
    assert "无评分 CSV" in capsys.readouterr().err
