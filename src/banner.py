"""巧克力色侏儒兔 banner：OpenCode 风格左兔右标，ANSI / 纯 ASCII / 单行降级。"""

from __future__ import annotations

import os
import sys
from importlib import metadata

CHOCOLATE = "\x1b[38;2;138;82;38m"
GOLD = "\x1b[38;2;217;165;58m"
DIM = "\x1b[90m"
RESET = "\x1b[0m"
NARROW_WIDTH = 48
WIDE_WIDTH = 68

_LINE_RABBIT = (
    "╭──╮   ╭──╮",
    "│  │   │  │",
    "│  ╰───╯  │",
    "│  ●   ●  │",
    "│    ω    │",
    "╰─────────╯",
)
_ASCII_RABBIT = (
    " /\\   /\\",
    "| |   | |",
    "|  \\_/  |",
    "| o   o |",
    "|   w   |",
    " \\_____/",
)

# 5 行位图，OpenCode 风格块状字母；仅覆盖 wordmark 用到的字形。
_GLYPHS: dict[str, tuple[str, ...]] = {
    "A": ("▄▀▀▄", "█▄▄█", "█  █", "█  █", "▀  ▀"),
    "L": ("█   ", "█   ", "█   ", "█   ", "▀▀▀▀"),
    "P": ("█▀▀▄", "█  █", "█▀▀ ", "█   ", "▀   "),
    "H": ("█  █", "█  █", "█▀▀█", "█  █", "▀  ▀"),
    "J": ("   █", "   █", "   █", "█  █", " ▀▀ "),
    "E": ("█▀▀▀", "█   ", "█▀▀ ", "█   ", "▀▀▀▀"),
    "R": ("█▀▀▄", "█  █", "█▀▀▄", "█  █", "▀  ▀"),
    "Y": ("█  █", "█  █", " ▀█▀", "  █ ", "  ▀ "),
    "-": ("    ", "    ", " ▀▀ ", "    ", "    "),
    " ": ("  ", "  ", "  ", "  ", "  "),
}
_ASCII_GLYPHS: dict[str, tuple[str, ...]] = {
    "A": (" ## ", "#  #", "####", "#  #", "#  #"),
    "L": ("#   ", "#   ", "#   ", "#   ", "####"),
    "P": ("### ", "#  #", "### ", "#   ", "#   "),
    "H": ("#  #", "#  #", "####", "#  #", "#  #"),
    "J": ("  ##", "   #", "   #", "#  #", " ## "),
    "E": ("####", "#   ", "### ", "#   ", "####"),
    "R": ("### ", "#  #", "### ", "#  #", "#  #"),
    "Y": ("#  #", "#  #", " ## ", "  # ", "  # "),
    "-": ("    ", "    ", " ## ", "    ", "    "),
    " ": ("  ", "  ", "  ", "  ", "  "),
}


def _package_version() -> str:
    try:
        return metadata.version("alpha-jerry")
    except metadata.PackageNotFoundError:
        return "1.0.0"


VERSION = _package_version()


def _wordmark(ascii_only: bool) -> list[str]:
    table = _ASCII_GLYPHS if ascii_only else _GLYPHS
    rows = [""] * 5
    for char in "ALPHA-JERRY":
        glyph = table.get(char, table[" "])
        for index, piece in enumerate(glyph):
            rows[index] += piece + " "
    return [row.rstrip() for row in rows]


def _paint(text: str, colorful: bool) -> str:
    if not colorful:
        return text
    return f"{CHOCOLATE}{text}{RESET}"


def _paint_rabbit(row: str, colorful: bool) -> str:
    """眼鼻用金币金点缀，呼应品牌 Logo 配色。"""
    if not colorful:
        return row
    accented = row.replace("●", f"{GOLD}●{CHOCOLATE}").replace("ω", f"{GOLD}ω{CHOCOLATE}")
    return f"{CHOCOLATE}{accented}{RESET}"


def _subtitle(ascii_only: bool, colorful: bool) -> str:
    if ascii_only:
        return f"alpha-jerry v{VERSION}"
    if not colorful:
        return f"阿尔法杰瑞 · v{VERSION}"
    return f"{GOLD}阿尔法杰瑞{RESET} {DIM}· v{VERSION}{RESET}"


def render(width: int, color: bool, ascii_only: bool) -> str:
    """宽屏左兔右标，中屏上下堆叠，窄屏单行；ascii_only 保证 .isascii()。"""
    if width < NARROW_WIDTH:
        if ascii_only:
            return f"alpha-jerry v{VERSION}"
        return f"🐰 阿尔法杰瑞 · alpha-jerry v{VERSION}"
    colorful = color and not ascii_only
    raw_rabbit = _ASCII_RABBIT if ascii_only else _LINE_RABBIT
    side_by_side = width >= WIDE_WIDTH
    cell = max(len(row) for row in raw_rabbit) + 3 if side_by_side else 0
    rabbit = [_paint_rabbit(row.ljust(cell), colorful) for row in raw_rabbit]
    right = [_paint(row, colorful) for row in _wordmark(ascii_only)]
    right.append(_subtitle(ascii_only, colorful))
    if not side_by_side:
        return "\n".join(rabbit + [""] + right)
    lines = []
    for index in range(max(len(rabbit), len(right))):
        left = rabbit[index] if index < len(rabbit) else " " * cell
        lines.append(left + (right[index] if index < len(right) else ""))
    return "\n".join(lines)


def detect_mode(
    env: dict[str, str],
    isatty: bool,
    encoding: str,
    platform: str,
) -> str:
    """silent / ascii / plain / color。"""
    if not isatty:
        return "silent"
    if env.get("NO_COLOR") or env.get("TERM") == "dumb":
        return "plain"
    if platform == "win32" and not env.get("WT_SESSION"):
        return "ascii"
    if encoding.lower().replace("-", "") in {"ascii"}:
        return "ascii"
    return "color"


def enable_windows_vt() -> bool:
    """Windows 尝试打开 VT；失败则调用方降为无色。"""
    if sys.platform != "win32":
        return True
    try:
        import ctypes

        handle = ctypes.windll.kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(ctypes.windll.kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:  # noqa: BLE001
        return False


def banner_for_stdio(width: int | None = None) -> str:
    columns = width
    if columns is None:
        try:
            columns = os.get_terminal_size().columns
        except OSError:
            columns = 80
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    mode = detect_mode(dict(os.environ), bool(sys.stdout.isatty()), encoding, sys.platform)
    if mode == "silent":
        return ""
    color = mode == "color"
    if color and not enable_windows_vt():
        color = False
    ascii_only = mode == "ascii"
    if mode == "plain" and encoding.lower().replace("-", "") == "ascii":
        ascii_only = True
    return render(columns, color=color, ascii_only=ascii_only)
