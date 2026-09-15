"""微信文本指令 → CLI 工具；只读直出，改数据 / 调 LLM 先确认。"""

from __future__ import annotations

from dataclasses import dataclass

from src.config import Settings
from src.wechat.actions import ToolMap, default_tools
from src.wechat.intent import NO, YES, Command, normalize_ts_code, parse_command
from src.wechat.pending import MemoryPending

HELP_TEXT = (
    "只读：帮助 / 状态 / 报告 / 摘要 / 持仓 / 查 600519 / 筛选 白酒\n"
    "需确认：更新 / 全量采集 / 评分 / 锐评 / 加仓 600519 / 减仓 600519"
    "（示例，可换其他代码如 000001）"
)

__all__ = [
    "Command",
    "HELP_TEXT",
    "Incoming",
    "default_tools",
    "handle_incoming",
    "normalize_ts_code",
    "parse_command",
    "split_message",
]


@dataclass(frozen=True)
class Incoming:
    sender: str
    text: str
    group_id: str
    context_token: str
    typing_ticket: str = ""


def split_message(text: str, max_chars: int) -> list[str]:
    if max_chars <= 0 or not text:
        return [text]
    return [text[index : index + max_chars] for index in range(0, len(text), max_chars)]


def is_allowed(sender: str, settings: Settings, owner_id: str) -> bool:
    raw = settings.wechat_allowed_users.strip()
    if not raw:
        return bool(owner_id) and sender == owner_id
    allowed = {part.strip() for part in raw.split(",") if part.strip()}
    return sender in allowed


def confirm_prompt(command: Command) -> str:
    return f"识别到「{command.trigger}」，将{command.summary}。回复「确认」执行，回复「取消」放弃。"


def _run(command: Command, tools: ToolMap) -> str:
    handler = tools.get(command.name)
    if handler is None:
        return HELP_TEXT
    if command.name == "screen":
        return handler(command.industry, command.rating)
    if command.code:
        return handler(command.code)
    return handler()


def handle_incoming(
    incoming: Incoming,
    settings: Settings,
    *,
    owner_id: str,
    tools: ToolMap | None = None,
    pending: MemoryPending | None = None,
) -> str | None:
    if incoming.group_id:
        return None
    if not is_allowed(incoming.sender, settings, owner_id):
        return None
    resolved = tools or default_tools(settings)
    text = incoming.text.strip()
    current = pending.get(incoming.sender) if pending is not None else None
    if current is not None and pending is not None:
        if text in YES:
            pending.clear(incoming.sender)
            return _run(current, resolved)
        if text in NO:
            pending.clear(incoming.sender)
            return "已取消"

    command = parse_command(text)
    if command.name == "unknown":
        if pending is not None and current is not None:
            pending.clear(incoming.sender)
            return "已取消待确认操作。未知指令，回复「帮助」查看用法"
        return "未知指令，回复「帮助」查看用法"
    if command.name == "hint":
        return command.summary
    if command.name == "help":
        if pending is not None:
            pending.clear(incoming.sender)
        return HELP_TEXT
    if command.needs_confirm:
        store = pending if pending is not None else MemoryPending()
        store.set(incoming.sender, command)
        return confirm_prompt(command)
    if pending is not None:
        pending.clear(incoming.sender)
    return _run(command, resolved)
