"""待确认动作：确认执行、取消、超时作废、新指令替换。"""

from __future__ import annotations

from src.wechat.intent import parse_command
from src.wechat.pending import MemoryPending


def test_pending_expires() -> None:
    ticks = iter([0.0, 10.0, 200.0])
    store = MemoryPending(ttl=120, clock=lambda: next(ticks))
    store.set("me", parse_command("更新"))
    assert store.get("me") is not None
    assert store.get("me") is None
