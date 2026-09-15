"""CLI 工具契约：统一退出码、ToolError 与 JSON 信封。"""

from __future__ import annotations

import json
from typing import Any

EXIT_OK = 0
EXIT_CONFIG = 2
EXIT_UPSTREAM = 3
EXIT_DATA = 4


class ToolError(Exception):
    """可映射为 CLI 退出码的工具失败。"""

    def __init__(self, message: str, code: int = EXIT_DATA) -> None:
        super().__init__(message)
        self.code = code


def envelope(*, ok: bool, command: str, data: Any = None, error: str | None = None) -> dict[str, Any]:
    return {"ok": ok, "command": command, "data": data, "error": error}


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, default=str))
