"""getupdates 长轮询：白名单路由、输入态、定时摘要。"""

from __future__ import annotations

import datetime as _dt
import time
from collections.abc import Callable
from typing import Any

from src.config import Settings
from src.tools.holdings import HoldingsParams, run_holdings
from src.tools.status import StatusParams, run_status
from src.wechat.ilink import SessionExpired
from src.wechat.notify import append_trace, push_text
from src.wechat.pending import MemoryPending
from src.wechat.router import Incoming, default_tools, handle_incoming, split_message
from src.wechat.session import SessionStore


def parse_digest_times(raw: str) -> set[str]:
    return {part.strip() for part in raw.split(",") if part.strip()}


def extract_text(message: dict[str, Any]) -> str:
    for item in message.get("item_list") or []:
        text_item = item.get("text_item") or {}
        text = text_item.get("text")
        if text:
            return str(text)
    return str(message.get("text") or "")


class WechatBot:
    def __init__(
        self,
        *,
        client: Any,
        store: SessionStore,
        settings: Settings,
        now_fn: Callable[[], _dt.datetime] | None = None,
        digest_builder: Callable[[], str] | None = None,
        tools: dict[str, Callable[..., str]] | None = None,
        pending: MemoryPending | None = None,
    ) -> None:
        self.client = client
        self.store = store
        self.settings = settings
        self.now_fn = now_fn or _dt.datetime.now
        self.digest_builder = digest_builder or (lambda: self._default_digest())
        self.tools = tools
        self.pending = pending or MemoryPending(ttl=settings.wechat_confirm_ttl_seconds)
        self._stopped = False

    def stop(self) -> None:
        self._stopped = True

    def run(self, sleeper: Callable[[float], None] = time.sleep) -> None:
        while not self._stopped:
            self.maybe_digest()
            self.step()
            if self._stopped:
                break
            sleeper(1)

    def step(self) -> bool:
        token = self.store.get_token()
        if not token:
            raise SessionExpired("missing wechat token")
        meta = self.store.load_meta()
        payload = self.client.get_updates(token, str(meta.get("cursor") or ""))
        meta["cursor"] = str(payload.get("get_updates_buf") or meta.get("cursor") or "")
        self.store.save_meta(meta)
        for message in payload.get("msgs") or []:
            self._handle_message(message, token)
        return True

    def maybe_digest(self) -> None:
        now = self.now_fn()
        slot = now.strftime("%H:%M")
        if slot not in parse_digest_times(self.settings.wechat_digest_times):
            return
        key = f"{now.date().isoformat()}T{slot}"
        meta = self.store.load_meta()
        fired = set(meta.get("digest_fired") or [])
        if key in fired:
            return
        try:
            push_text(self.store, self.client, self.digest_builder(), self.settings)
        except Exception:
            return
        fired.add(key)
        meta["digest_fired"] = sorted(fired)
        self.store.save_meta(meta)

    def _handle_message(self, message: dict[str, Any], token: str) -> None:
        incoming = Incoming(
            sender=str(message.get("from_user_id") or message.get("ilink_user_id") or ""),
            text=extract_text(message),
            group_id=str(message.get("group_id") or ""),
            context_token=str(message.get("context_token") or ""),
            typing_ticket=str(message.get("typing_ticket") or ""),
        )
        if incoming.context_token and incoming.sender:
            self.store.remember_context(incoming.sender, incoming.context_token, incoming.typing_ticket)
        owner_id = str(self.store.load_meta().get("user_id") or "")
        reply = handle_incoming(
            incoming,
            self.settings,
            owner_id=owner_id,
            tools=self.tools or default_tools(self.settings),
            pending=self.pending,
        )
        if reply is None:
            return
        if incoming.typing_ticket:
            self.client.send_typing(token, incoming.sender, incoming.typing_ticket, 1)
        for chunk in split_message(reply, self.settings.wechat_max_message_chars):
            self.client.send_text(token, incoming.sender, incoming.context_token, chunk)
        if incoming.typing_ticket:
            self.client.send_typing(token, incoming.sender, incoming.typing_ticket, 2)
        append_trace(
            self.settings,
            {"event": "reply", "user_id": incoming.sender, "command": incoming.text},
        )

    def _default_digest(self) -> str:
        _code, status_payload = run_status(StatusParams(check=False), self.settings)
        items = (status_payload.get("data") or {}).get("items") or []
        freshness = "；".join(f"{item['kind']}={item['reason']}" for item in items) or "无产物"
        _hold_code, hold_payload = run_holdings(HoldingsParams(action="list"), self.settings)
        holds = (hold_payload.get("data") or {}).get("items") or []
        names = "、".join(str(row.get("ts_code")) for row in holds) or "空仓"
        return f"定时摘要 {freshness}；持仓 {names}"
