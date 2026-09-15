"""会话落盘不含 token；context_token / typing_ticket 按用户缓存。"""

from __future__ import annotations

import json
from pathlib import Path

from keyring.errors import KeyringError

from src.llm.credentials import SERVICE_NAME
from src.wechat.session import TOKEN_USERNAME, SessionStore


class _FakeKeyring:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.values.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.values[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        self.values.pop((service, username), None)


class _BrokenKeyring:
    def get_password(self, service: str, username: str) -> str | None:
        raise KeyringError("unavailable")

    def set_password(self, service: str, username: str, password: str) -> None:
        raise KeyringError("unavailable")

    def delete_password(self, service: str, username: str) -> None:
        raise KeyringError("unavailable")


def test_session_json_excludes_token(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "session.json", backend=_FakeKeyring())
    store.set_token("super-secret-ilink-token-abcdef")
    store.save_meta(
        {
            "bot_id": "bot-1",
            "user_id": "owner-1",
            "base_url": "https://ilinkai.weixin.qq.com",
            "cursor": "c0",
        }
    )
    raw = (tmp_path / "session.json").read_text(encoding="utf-8")
    data = json.loads(raw)
    assert "token" not in data
    assert "super-secret" not in raw
    assert data["user_id"] == "owner-1"
    assert store.get_token() == "super-secret-ilink-token-abcdef"
    assert (SERVICE_NAME, TOKEN_USERNAME) in store.backend.values


def test_expire_clears_cursor_and_token(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "session.json", backend=_FakeKeyring())
    store.set_token("tok-12345678901234567890")
    store.save_meta({"user_id": "u", "cursor": "old-cursor", "contexts": {"u": "ctx"}})
    store.expire()
    assert store.get_token() is None
    assert store.load_meta()["cursor"] == ""
    assert store.load_meta()["contexts"]["u"] == "ctx"


def test_remember_context_and_typing(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "session.json", backend=_FakeKeyring())
    store.remember_context("alice", "ctx-a", "type-a")
    store.remember_context("bob", "ctx-b", "type-b")
    meta = store.load_meta()
    assert meta["contexts"]["alice"] == "ctx-a"
    assert meta["contexts"]["bob"] == "ctx-b"
    assert meta["typing"]["bob"] == "type-b"
    assert meta["last_user_id"] == "bob"
    assert store.latest_context() == ("bob", "ctx-b")


def test_missing_keyring_returns_none(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "session.json", backend=_BrokenKeyring())
    store.set_token("tok")
    assert store.get_token() is None
