"""wechat login/serve/push/status 退出码与 push 前置条件。"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config import Settings
from src.tools import EXIT_CONFIG, EXIT_DATA, EXIT_OK, ToolError
from src.tools.wechat import WechatParams, run_wechat
from src.wechat.ilink import SessionExpired
from src.wechat.session import SessionStore


class _FakeKeyring:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.values.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.values[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        self.values.pop((service, username), None)


class _LoginClient:
    def get_qrcode(self) -> dict:
        return {"qrcode": "https://qr.example/login"}

    def poll_qrcode_status(self, qrcode: str) -> dict:
        assert qrcode == "https://qr.example/login"
        return {
            "status": "confirmed",
            "bot_token": "login-token-xyz",
            "ilink_user_id": "owner-9",
            "bot_id": "bot-9",
        }


class _ExpireClient:
    def get_updates(self, token: str, cursor: str) -> dict:
        raise SessionExpired("expired")


def _settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, data_dir=str(tmp_path))


def test_login_saves_qrcode_and_session(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "wechat" / "session.json", backend=_FakeKeyring())
    code, payload = run_wechat(
        WechatParams(action="login"),
        _settings(tmp_path),
        store=store,
        client_factory=lambda **_kw: _LoginClient(),
    )
    assert code == EXIT_OK
    qr_path = tmp_path / "wechat" / "qrcode.txt"
    assert qr_path.read_text(encoding="utf-8") == "https://qr.example/login"
    assert store.get_token() == "login-token-xyz"
    assert store.load_meta()["user_id"] == "owner-9"
    assert "https://qr.example/login" in (payload["data"] or {}).get("message", "")


def test_status_without_session(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "wechat" / "session.json", backend=_FakeKeyring())
    code, payload = run_wechat(WechatParams(action="status"), _settings(tmp_path), store=store)
    assert code == EXIT_OK
    assert payload["data"]["logged_in"] is False


def test_push_without_context_token_exits_4(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "wechat" / "session.json", backend=_FakeKeyring())
    store.set_token("tok")
    store.save_meta({"user_id": "me", "contexts": {}})
    with pytest.raises(ToolError) as exc:
        run_wechat(WechatParams(action="push", text="测试"), _settings(tmp_path), store=store)
    assert exc.value.code == EXIT_DATA
    assert "先在微信里给机器人发一条消息" in str(exc.value)


def test_serve_session_expired_exits_2(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "wechat" / "session.json", backend=_FakeKeyring())
    store.set_token("tok")
    store.save_meta({"user_id": "me", "cursor": "c"})
    code, payload = run_wechat(
        WechatParams(action="serve"),
        _settings(tmp_path),
        store=store,
        client_factory=lambda **_kw: _ExpireClient(),
        sleeper=lambda _seconds: None,
    )
    assert code == EXIT_CONFIG
    assert payload["ok"] is False
    assert store.get_token() is None
    assert store.load_meta()["cursor"] == ""
