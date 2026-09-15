"""wechat login / serve / push / status：iLink 胶水。"""

from __future__ import annotations

import argparse
import time
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict

from src.config import Settings, get_settings
from src.tools import EXIT_CONFIG, EXIT_DATA, EXIT_OK, ToolError, envelope
from src.wechat.bot import WechatBot
from src.wechat.ilink import QR_CONFIRMED, QR_EXPIRED, ILinkClient, SessionExpired, qr_status
from src.wechat.notify import push_text
from src.wechat.session import SessionStore


class WechatParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str
    text: str = ""


def session_store(settings: Settings, store: SessionStore | None = None) -> SessionStore:
    return store or SessionStore(settings.data_path("wechat") / "session.json")


def make_client(settings: Settings, token: str | None = None) -> ILinkClient:
    return ILinkClient(
        base_url=settings.wechat_base_url,
        channel_version=settings.wechat_channel_version,
        bot_agent=settings.wechat_bot_agent,
        timeout_ms=settings.wechat_poll_timeout_ms,
        trust_env=settings.wechat_trust_env,
        token=token,
    )


def _login(
    settings: Settings,
    store: SessionStore,
    client: Any,
    sleeper: Callable[[float], None],
) -> tuple[int, dict[str, Any]]:
    payload = client.get_qrcode()
    qrcode = str(payload.get("qrcode") or (payload.get("data") or {}).get("qrcode") or "")
    if not qrcode:
        raise ToolError("未能获取登录二维码", EXIT_DATA)
    qr_path = settings.data_path("wechat") / "qrcode.txt"
    qr_path.write_text(qrcode, encoding="utf-8")
    status = _poll_login(client, qrcode, sleeper)
    token = str(status.get("bot_token") or status.get("token") or "")
    user_id = str(status.get("ilink_user_id") or status.get("user_id") or "")
    bot_id = str(status.get("bot_id") or "")
    if not token:
        raise ToolError("扫码成功但未返回 token", EXIT_DATA)
    store.set_token(token)
    store.save_meta(
        {
            "bot_id": bot_id,
            "user_id": user_id,
            "base_url": settings.wechat_base_url,
            "cursor": "",
        }
    )
    return EXIT_OK, envelope(
        ok=True,
        command="wechat",
        data={"message": f"已保存二维码 {qr_path}：{qrcode}", "user_id": user_id},
    )


def _poll_login(client: Any, qrcode: str, sleeper: Callable[[float], None], rounds: int = 120) -> dict[str, Any]:
    for _ in range(rounds):
        status = client.poll_qrcode_status(qrcode)
        kind = qr_status(status)
        if kind == QR_CONFIRMED:
            return status
        if kind == QR_EXPIRED:
            raise ToolError("二维码已过期，请重新 login", EXIT_DATA)
        sleeper(2)
    raise ToolError("登录超时", EXIT_DATA)


def _serve(
    settings: Settings,
    store: SessionStore,
    client: Any,
    sleeper: Callable[[float], None],
) -> tuple[int, dict[str, Any]]:
    if not store.get_token():
        raise ToolError("未登录，请先运行 wechat login", EXIT_CONFIG)
    bot = WechatBot(client=client, store=store, settings=settings)
    try:
        bot.run(sleeper=sleeper)
    except SessionExpired:
        store.expire()
        return EXIT_CONFIG, envelope(ok=False, command="wechat", error="session_expired")
    return EXIT_OK, envelope(ok=True, command="wechat", data={"message": "wechat serve 已停止"})


def run_wechat(
    params: WechatParams,
    settings: Settings | None = None,
    *,
    store: SessionStore | None = None,
    client_factory: Callable[..., Any] | None = None,
    sleeper: Callable[[float], None] = time.sleep,
) -> tuple[int, dict[str, Any]]:
    resolved = settings or get_settings()
    resolved_store = session_store(resolved, store)
    factory = client_factory or (lambda **kwargs: make_client(resolved, kwargs.get("token")))
    action = params.action
    if action == "login":
        return _login(resolved, resolved_store, factory(), sleeper)
    if action == "status":
        meta = resolved_store.load_meta()
        logged_in = resolved_store.get_token() is not None
        return EXIT_OK, envelope(
            ok=True,
            command="wechat",
            data={
                "logged_in": logged_in,
                "user_id": meta.get("user_id") or "",
                "has_context": bool(meta.get("contexts")),
            },
        )
    if action == "push":
        if not params.text.strip():
            raise ToolError("push 需要 --text", EXIT_DATA)
        client = factory(token=resolved_store.get_token())
        client_ids = push_text(resolved_store, client, params.text, resolved)
        return EXIT_OK, envelope(ok=True, command="wechat", data={"client_ids": client_ids})
    if action == "serve":
        client = factory(token=resolved_store.get_token())
        return _serve(resolved, resolved_store, client, sleeper)
    raise ToolError(f"未知 wechat 动作：{action}", EXIT_DATA)


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("wechat", help="微信 iLink 登录 / 收发 / 推送")
    action = parser.add_subparsers(dest="wechat_action", required=True)
    action.add_parser("login", help="扫码登录并保存会话")
    action.add_parser("serve", help="长轮询收消息并回复")
    push = action.add_parser("push", help="向最近会话主动推送文本")
    push.add_argument("--text", required=True, help="推送正文")
    action.add_parser("status", help="查看登录与 context_token 状态")
    parser.set_defaults(handler="wechat")
