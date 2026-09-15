"""微信会话元数据落盘；token 只进系统钥匙串。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import keyring
from keyring.errors import KeyringError

from src.llm.credentials import SERVICE_NAME

TOKEN_USERNAME = "wechat_ilink_token"

_EMPTY: dict[str, Any] = {
    "bot_id": "",
    "user_id": "",
    "base_url": "",
    "cursor": "",
    "contexts": {},
    "typing": {},
    "last_user_id": "",
    "digest_fired": [],
}


class SessionStore:
    def __init__(self, path: Path, *, backend: Any | None = None) -> None:
        self.path = path
        self.backend = backend or keyring

    def load_meta(self) -> dict[str, Any]:
        if not self.path.exists():
            return dict(_EMPTY)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        merged = dict(_EMPTY)
        merged.update(data)
        merged.pop("token", None)
        merged["contexts"] = dict(merged.get("contexts") or {})
        merged["typing"] = dict(merged.get("typing") or {})
        merged["digest_fired"] = list(merged.get("digest_fired") or [])
        return merged

    def save_meta(self, data: dict[str, Any]) -> None:
        current = self.load_meta()
        current.update(data)
        current.pop("token", None)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def set_token(self, token: str) -> None:
        try:
            self.backend.set_password(SERVICE_NAME, TOKEN_USERNAME, token)
        except KeyringError:
            return

    def get_token(self) -> str | None:
        try:
            stored = self.backend.get_password(SERVICE_NAME, TOKEN_USERNAME)
        except KeyringError:
            return None
        if stored is None:
            return None
        stripped = str(stored).strip()
        return stripped or None

    def expire(self) -> None:
        meta = self.load_meta()
        meta["cursor"] = ""
        self.save_meta(meta)
        try:
            self.backend.delete_password(SERVICE_NAME, TOKEN_USERNAME)
        except KeyringError:
            pass

    def remember_context(self, user_id: str, context_token: str, typing_ticket: str = "") -> None:
        meta = self.load_meta()
        meta["contexts"][user_id] = context_token
        if typing_ticket:
            meta["typing"][user_id] = typing_ticket
        meta["last_user_id"] = user_id
        self.save_meta(meta)

    def latest_context(self) -> tuple[str, str] | None:
        meta = self.load_meta()
        contexts: dict[str, str] = meta["contexts"]
        if not contexts:
            return None
        last = str(meta.get("last_user_id") or "")
        if last and last in contexts:
            return last, contexts[last]
        user_id, token = next(reversed(list(contexts.items())))
        return user_id, token
