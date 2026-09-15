"""按发送者记住待确认动作；超时后视为作废。"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from src.wechat.intent import Command


@dataclass(frozen=True)
class PendingAction:
    command: Command
    created_at: float


class MemoryPending:
    def __init__(self, ttl: int = 120, clock: Callable[[], float] | None = None) -> None:
        self.ttl = ttl
        self._clock = clock or time.time
        self._items: dict[str, PendingAction] = {}

    def set(self, user_id: str, command: Command) -> None:
        self._items[user_id] = PendingAction(command=command, created_at=self._clock())

    def get(self, user_id: str) -> Command | None:
        item = self._items.get(user_id)
        if item is None:
            return None
        if self._clock() - item.created_at > self.ttl:
            self._items.pop(user_id, None)
            return None
        return item.command

    def clear(self, user_id: str) -> None:
        self._items.pop(user_id, None)
