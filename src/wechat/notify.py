"""主动推送：复用最近一条入站消息的 context_token。"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Protocol

from src.config import Settings
from src.tools import EXIT_DATA, ToolError
from src.wechat.router import split_message
from src.wechat.session import SessionStore

_SECRET_LIKE = re.compile(r"\*{2,}\w+|[A-Za-z0-9_-]{20,}")


class TextSender(Protocol):
    def send_text(self, token: str, to_user: str, context_token: str, text: str) -> dict[str, Any]: ...


def redact(value: Any) -> Any:
    if isinstance(value, str):
        return _SECRET_LIKE.sub("***", value)
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def append_trace(settings: Settings, record: dict[str, Any], *, today: date | None = None) -> Path:
    stamp = (today or date.today()).strftime("%y%m%d")
    path = settings.data_path("monitor") / f"wechat-{stamp}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(redact(record), ensure_ascii=False) + "\n")
    return path


def push_text(
    store: SessionStore,
    client: TextSender,
    text: str,
    settings: Settings,
) -> list[str]:
    latest = store.latest_context()
    if latest is None:
        raise ToolError("先在微信里给机器人发一条消息", EXIT_DATA)
    token = store.get_token()
    if not token:
        raise ToolError("未登录，请先运行 wechat login", EXIT_DATA)
    user_id, context_token = latest
    client_ids: list[str] = []
    for chunk in split_message(text, settings.wechat_max_message_chars):
        payload = client.send_text(token, user_id, context_token, chunk)
        client_ids.append(str(payload.get("client_id") or ""))
    append_trace(settings, {"event": "push", "user_id": user_id, "chars": len(text)})
    return client_ids
