"""iLink HTTP 客户端：请求头、二维码状态机、游标与 -14。"""

from __future__ import annotations

import json

import httpx
import pytest

from src.wechat.ilink import (
    QR_CONFIRMED,
    QR_EXPIRED,
    QR_SCANNED,
    QR_WAIT,
    ILinkClient,
    SessionExpired,
    qr_status,
    random_wechat_uin,
)


def _client(handler, uin: str = "uin-fixed") -> ILinkClient:
    return ILinkClient(
        base_url="https://ilinkai.weixin.qq.com",
        channel_version="2.4.8",
        bot_agent="alpha-jerry/test",
        timeout_ms=1000,
        trust_env=False,
        transport=httpx.MockTransport(handler),
        uin_factory=lambda: uin,
    )


def test_get_qrcode_headers_and_app_id() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"qrcode": "abc", "status": "wait"})

    client = _client(handler)
    payload = client.get_qrcode()
    assert payload["qrcode"] == "abc"
    request = captured[0]
    assert request.headers["AuthorizationType"] == "ilink_bot_token"
    assert request.headers["X-WECHAT-UIN"] == "uin-fixed"
    assert request.headers["iLink-App-Id"] == "bot"
    assert "Authorization" not in request.headers


def test_uin_is_random_per_request() -> None:
    captured: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request.headers["X-WECHAT-UIN"])
        return httpx.Response(200, json={"qrcode": "x"})

    client = ILinkClient(
        base_url="https://ilinkai.weixin.qq.com",
        channel_version="2.4.8",
        bot_agent="alpha-jerry/test",
        timeout_ms=1000,
        trust_env=False,
        transport=httpx.MockTransport(handler),
    )
    client.get_qrcode()
    client.get_qrcode()
    assert captured[0] != captured[1]
    assert random_wechat_uin() != random_wechat_uin()


def test_extract_login_qr_separates_poll_token_and_image_url() -> None:
    from src.wechat.ilink import extract_login_qr

    token, image = extract_login_qr(
        {"qrcode": "qrc_token", "qrcode_img_content": "https://weixin.qq.com/x/abc"}
    )
    assert token == "qrc_token"
    assert image == "https://weixin.qq.com/x/abc"


def test_qrcode_status_machine() -> None:
    assert qr_status({"status": "wait"}) == QR_WAIT
    assert qr_status({"status": "scaned"}) == QR_SCANNED
    assert qr_status({"status": "confirmed"}) == QR_CONFIRMED
    assert qr_status({"status": "expired"}) == QR_EXPIRED


def test_get_updates_passes_cursor_and_bearer() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"get_updates_buf": "next", "msgs": []})

    client = _client(handler)
    payload = client.get_updates("secret-token", "cursor-1")
    assert payload["get_updates_buf"] == "next"
    request = captured[0]
    assert request.headers["Authorization"] == "Bearer secret-token"
    body = json.loads(request.content)
    assert body["get_updates_buf"] == "cursor-1"
    assert body["base_info"]["channel_version"] == "2.4.8"
    assert body["base_info"]["bot_agent"] == "alpha-jerry/test"


@pytest.mark.parametrize("payload", [{"ret": -14}, {"errcode": -14}])
def test_get_updates_minus_14_raises_session_expired(payload: dict) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    with pytest.raises(SessionExpired):
        _client(handler).get_updates("tok", "")


def test_send_text_body_contract() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"ret": 0})

    result = _client(handler).send_text("tok", "user-1", "ctx-9", "你好")
    body = json.loads(captured[0].content)
    msg = body["msg"]
    assert msg["message_type"] == 2
    assert msg["message_state"] == 2
    assert msg["context_token"] == "ctx-9"
    assert msg["to_user_id"] == "user-1"
    assert msg["item_list"][0]["text_item"]["text"] == "你好"
    assert msg["client_id"].startswith("alpha-jerry:")
    assert result["client_id"] == msg["client_id"]
    assert body["base_info"]["channel_version"] == "2.4.8"


@pytest.mark.network
@pytest.mark.skip(reason="默认跳过：需真实 iLink 扫码与 token")
def test_ilink_live_roundtrip() -> None:
    raise AssertionError("不应执行")
