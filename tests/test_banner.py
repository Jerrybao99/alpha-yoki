"""侏儒兔 banner：三档纯函数与终端检测。"""

from __future__ import annotations

from src.banner import VERSION, detect_mode, render


def test_render_wide_color_contains_wordmark_and_version() -> None:
    text = render(width=80, color=True, ascii_only=False)
    assert "alpha-jerry" in text.lower() or "ALPHA" in text or "▀" in text or "█" in text
    assert VERSION in text
    assert "\x1b[" in text


def test_render_narrow_is_single_line() -> None:
    text = render(width=30, color=False, ascii_only=False)
    assert text.count("\n") == 0
    assert "🐰" in text
    assert "alpha-jerry" in text
    assert VERSION in text


def test_render_ascii_only_is_ascii() -> None:
    text = render(width=80, color=False, ascii_only=True)
    assert text.isascii()
    assert "alpha-jerry" in text.lower() or "ALPHA-JERRY" in text or "#" in text


def test_render_color_shows_chinese_name_and_gold_accent() -> None:
    text = render(width=80, color=True, ascii_only=False)
    assert "阿尔法杰瑞" in text
    assert "\x1b[38;2;217;165;58m" in text


def test_render_plain_shows_chinese_name_without_escape() -> None:
    text = render(width=80, color=False, ascii_only=False)
    assert "阿尔法杰瑞" in text
    assert "\x1b[" not in text


def test_render_wide_lays_rabbit_beside_wordmark() -> None:
    lines = render(width=80, color=False, ascii_only=False).splitlines()
    assert any("│" in line and "█" in line for line in lines)


def test_render_medium_stacks_rabbit_above_wordmark() -> None:
    text = render(width=50, color=False, ascii_only=False)
    assert text.index("╰─────────╯") < text.index("█")
    assert not any("│" in line and "█" in line for line in text.splitlines())


def test_render_narrow_shows_chinese_name() -> None:
    text = render(width=30, color=False, ascii_only=False)
    assert "阿尔法杰瑞" in text
    assert "alpha-jerry" in text


def test_render_ascii_subtitle_is_latin() -> None:
    text = render(width=80, color=False, ascii_only=True)
    assert text.isascii()
    assert f"alpha-jerry v{VERSION}" in text


def test_detect_mode_no_color_and_dumb_term() -> None:
    assert detect_mode({"NO_COLOR": "1"}, isatty=True, encoding="utf-8", platform="linux") == "plain"
    assert detect_mode({"TERM": "dumb"}, isatty=True, encoding="utf-8", platform="linux") == "plain"


def test_detect_mode_non_tty_is_silent() -> None:
    assert detect_mode({}, isatty=False, encoding="utf-8", platform="darwin") == "silent"


def test_detect_mode_windows_without_wt_session_is_ascii() -> None:
    assert detect_mode({}, isatty=True, encoding="utf-8", platform="win32") == "ascii"
    assert detect_mode({"WT_SESSION": "1"}, isatty=True, encoding="utf-8", platform="win32") == "color"


def test_detect_mode_macos_tty_is_color() -> None:
    assert detect_mode({"TERM": "xterm-256color"}, isatty=True, encoding="utf-8", platform="darwin") == "color"


def test_bare_cli_prints_banner_and_help(monkeypatch, capsys) -> None:
    import src.cli as cli

    monkeypatch.setattr(cli.sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr("src.banner.detect_mode", lambda *_args, **_kwargs: "ascii")
    monkeypatch.setattr("src.banner.enable_windows_vt", lambda: False)
    assert cli.main([]) == cli.EXIT_OK
    output = capsys.readouterr().out
    assert "alpha-jerry" in output.lower()
    assert "usage:" in output.lower() or "status" in output


def test_json_never_prints_banner(monkeypatch, capsys, tmp_path) -> None:
    import src.cli as cli
    from src.config import Settings

    monkeypatch.setattr("src.config.get_settings", lambda: Settings(_env_file=None, data_dir=str(tmp_path)))
    monkeypatch.setattr(cli.sys.stdout, "isatty", lambda: True)
    cli.main(["--json", "status"])
    output = capsys.readouterr().out
    assert "🐰" not in output
    assert "\x1b[" not in output
    assert output.strip().startswith("{")
