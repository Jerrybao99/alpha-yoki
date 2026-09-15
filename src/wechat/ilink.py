"""腾讯 iLink Bot HTTP 客户端。协议隔离在此，版本号走 Settings。"""

from __future__ import annotations

import base64
import secrets
import uuid
from typing import Any

import httpx


class SessionExpired(RuntimeError):
    """errcode/ret = -14，需重新扫码。"""


QR_WAIT = "wait"
QR_SCANNED = "scaned"
QR_CONFIRMED = "confirmed"
QR_EXPIRED = "expired"


def extract_login_qr(payload: dict[str, Any]) -> tuple[str, str]:
    """轮询令牌与可绘成二维码的 URL；二者不能混用。"""
    nested = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    token = str(payload.get("qrcode") or nested.get("qrcode") or "")
    image = str(payload.get("qrcode_img_content") or nested.get("qrcode_img_content") or "")
    return token, image


def qr_status(payload: dict[str, Any]) -> str:
    nested = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    return str(payload.get("status") or nested.get("status") or "")


def random_wechat_uin() -> str:
    value = secrets.randbits(32)
    return base64.b64encode(str(value).encode("ascii")).decode("ascii")


class ILinkClient:
    def __init__(
        self,
        *,
        base_url: str,
        channel_version: str,
        bot_agent: str,
        timeout_ms: int,
        trust_env: bool = False,
        transport: httpx.BaseTransport | None = None,
        uin_factory: Any = random_wechat_uin,
        token: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.channel_version = channel_version
        self.bot_agent = bot_agent
        self.token = token
        self._uin_factory = uin_factory
        self._http = httpx.Client(
            base_url=self.base_url,
            trust_env=trust_env,
            timeout=timeout_ms / 1000,
            transport=transport,
        )

    def close(self) -> None:
        self._http.close()

    def _headers(self, token: str | None = None) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "AuthorizationType": "ilink_bot_token",
            "X-WECHAT-UIN": self._uin_factory(),
            "iLink-App-Id": "bot",
            "iLink-App-ClientVersion": "132099",
        }
        bearer = token if token is not None else self.token
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"
        return headers

    def _base_info(self) -> dict[str, str]:
        return {"channel_version": self.channel_version, "bot_agent": self.bot_agent}

    def _raise_if_expired(self, payload: dict[str, Any]) -> None:
        if payload.get("ret") == -14 or payload.get("errcode") == -14:
            raise SessionExpired("wechat session expired")

    def get_qrcode(self) -> dict[str, Any]:
        response = self._http.post(
            "/ilink/bot/get_bot_qrcode",
            params={"bot_type": "3"},
            json={"local_token_list": []},
            headers=self._headers(""),
        )
        response.raise_for_status()
        return response.json()

    def poll_qrcode_status(self, qrcode: str) -> dict[str, Any]:
        response = self._http.get(
            "/ilink/bot/get_qrcode_status",
            params={"qrcode": qrcode},
            headers={"iLink-App-ClientVersion": "132099"},
        )
        response.raise_for_status()
        return response.json()

    def get_updates(self, token: str, cursor: str) -> dict[str, Any]:
        response = self._http.post(
            "/ilink/bot/getupdates",
            json={"get_updates_buf": cursor, "base_info": self._base_info()},
            headers=self._headers(token),
        )
        response.raise_for_status()
        payload = response.json()
        self._raise_if_expired(payload)
        return payload

    def get_config(self, token: str, user_id: str, context_token: str) -> dict[str, Any]:
        response = self._http.post(
            "/ilink/bot/getconfig",
            json={
                "ilink_user_id": user_id,
                "context_token": context_token,
                "base_info": self._base_info(),
            },
            headers=self._headers(token),
        )
        response.raise_for_status()
        payload = response.json()
        self._raise_if_expired(payload)
        return payload

    def send_typing(self, token: str, user_id: str, typing_ticket: str, status: int) -> dict[str, Any]:
        response = self._http.post(
            "/ilink/bot/sendtyping",
            json={
                "ilink_user_id": user_id,
                "typing_ticket": typing_ticket,
                "status": status,
                "base_info": self._base_info(),
            },
            headers=self._headers(token),
        )
        response.raise_for_status()
        return response.json()

    def send_text(self, token: str, to_user: str, context_token: str, text: str) -> dict[str, Any]:
        client_id = f"alpha-jerry:{uuid.uuid4()}"
        body = {
            "msg": {
                "from_user_id": "",
                "to_user_id": to_user,
                "client_id": client_id,
                "message_type": 2,
                "message_state": 2,
                "context_token": context_token,
                "item_list": [{"type": 1, "text_item": {"text": text}}],
            },
            "base_info": self._base_info(),
        }
        response = self._http.post("/ilink/bot/sendmessage", json=body, headers=self._headers(token))
        response.raise_for_status()
        payload = response.json()
        self._raise_if_expired(payload)
        payload["client_id"] = client_id
        return payload
