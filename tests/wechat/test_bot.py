"""长轮询循环：处理消息、持久化游标、可停止、定时摘要每时点一次。"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

from src.config import Settings
from src.wechat.bot import WechatBot
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


class _FakeClient:
    def __init__(self, waves: list[dict], *, expire: bool = False) -> None:
        self.waves = list(waves)
        self.expire = expire
        self.sent: list[tuple[str, str, str]] = []
        self.typing: list[tuple[str, int]] = []
        self.polls = 0

    def get_updates(self, token: str, cursor: str) -> dict:
        self.polls += 1
        if self.expire:
            raise SessionExpired("expired")
        if not self.waves:
            return {"get_updates_buf": cursor or "empty", "msgs": []}
        return self.waves.pop(0)

    def send_typing(self, token: str, user_id: str, typing_ticket: str, status: int) -> dict:
        self.typing.append((user_id, status))
        return {"ret": 0}

    def send_text(self, token: str, to_user: str, context_token: str, text: str) -> dict:
        self.sent.append((to_user, context_token, text))
        return {"ret": 0, "client_id": f"cid-{len(self.sent)}"}


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        data_dir=str(tmp_path),
        wechat_digest_times="09:00,17:00",
        wechat_max_message_chars=1800,
    )


def test_bot_processes_message_and_persists_cursor(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "wechat" / "session.json", backend=_FakeKeyring())
    store.set_token("tok")
    store.save_meta({"user_id": "me", "cursor": ""})
    client = _FakeClient(
        [
            {
                "get_updates_buf": "cur-2",
                "msgs": [
                    {
                        "from_user_id": "me",
                        "group_id": "",
                        "context_token": "ctx-1",
                        "typing_ticket": "tt-1",
                        "item_list": [{"type": 1, "text_item": {"text": "帮助"}}],
                    }
                ],
            }
        ]
    )
    bot = WechatBot(client=client, store=store, settings=_settings(tmp_path))
    assert bot.step() is True
    assert store.load_meta()["cursor"] == "cur-2"
    assert store.load_meta()["contexts"]["me"] == "ctx-1"
    assert client.typing == [("me", 1), ("me", 2)]
    assert client.sent and "状态" in client.sent[0][2]


def test_bot_stops_after_flag(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "session.json", backend=_FakeKeyring())
    store.set_token("tok")
    store.save_meta({"user_id": "me", "cursor": ""})
    client = _FakeClient([])
    bot = WechatBot(client=client, store=store, settings=_settings(tmp_path))
    bot.stop()
    bot.run(sleeper=lambda _seconds: None)
    assert client.polls == 0


def test_digest_fires_once_per_slot(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "session.json", backend=_FakeKeyring())
    store.set_token("tok")
    store.save_meta({"user_id": "me", "cursor": "", "contexts": {"me": "ctx"}})
    store.remember_context("me", "ctx", "tt")
    client = _FakeClient([])
    now = _dt.datetime(2026, 9, 15, 9, 0)
    bot = WechatBot(
        client=client,
        store=store,
        settings=_settings(tmp_path),
        now_fn=lambda: now,
        digest_builder=lambda: "摘要",
    )
    bot.maybe_digest()
    bot.maybe_digest()
    assert [item[2] for item in client.sent] == ["摘要"]
    assert "2026-09-15T09:00" in store.load_meta()["digest_fired"]
