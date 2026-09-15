"""alpha-jerry 命令行入口：UTF-8、JSON 信封、退出码 0/2/3/4。"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from src.banner import banner_for_stdio
from src.llm.preferences import load_preferences, preferences_path, save_preferences
from src.tools import EXIT_CONFIG, EXIT_DATA, EXIT_OK, EXIT_UPSTREAM, ToolError, emit, envelope
from src.tools import holdings as holdings_tool
from src.tools import market as market_tool
from src.tools import report as report_tool
from src.tools import status as status_tool
from src.tools import wechat as wechat_tool
from src.tools.report import run_models, run_report, select_model, select_provider

__all__ = [
    "EXIT_CONFIG",
    "EXIT_DATA",
    "EXIT_OK",
    "EXIT_UPSTREAM",
    "build_parser",
    "load_preferences",
    "main",
    "preferences_path",
    "run_models",
    "run_report",
    "save_preferences",
    "select_model",
    "select_provider",
]


_HELP_EPILOG = """\
更多帮助：alpha-jerry <命令> --help

常用：
  alpha-jerry status --check
  alpha-jerry collect --update
  alpha-jerry collect --codes 600519.SH
  alpha-jerry scores
  alpha-jerry report --provider glm --model glm-5-turbo
  alpha-jerry wechat login

退出码：0 成功 · 2 配置 · 3 上游 · 4 数据缺失/过期
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="alpha-jerry",
        description="A 股基本面分析本地命令行工具。-h / --help 查看本指南。",
        epilog=_HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )
    parser.add_argument("-h", "--help", action="help", help="打印命令指南并退出")
    parser.add_argument("--json", action="store_true", help="只输出一份 JSON 信封 {ok,command,data,error}")
    subparsers = parser.add_subparsers(dest="command", metavar="<命令>")
    status_tool.register(subparsers)
    market_tool.register(subparsers)
    holdings_tool.register(subparsers)
    report_tool.register(subparsers)
    wechat_tool.register(subparsers)
    return parser


def _json_mode(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "json", False))


def dispatch(args: argparse.Namespace) -> tuple[int, dict]:
    from src.config import get_settings

    settings = get_settings()
    handler = getattr(args, "handler", args.command)
    if handler == "status":
        return status_tool.run_status(status_tool.StatusParams(check=bool(args.check)), settings)
    if handler == "collect":
        return market_tool.run_collect(
            market_tool.CollectParams(
                update=bool(args.update),
                force=bool(args.force),
                codes=list(args.codes or []),
                period=args.period,
            ),
            settings,
        )
    if handler == "scores":
        return market_tool.run_market_scores(
            market_tool.ScoresParams(codes=list(args.codes or []), date=args.date),
            settings,
        )
    if handler == "screen":
        return market_tool.run_screen(
            market_tool.ScreenParams(industry=args.industry, rating=args.rating),
            settings,
        )
    if handler == "holdings":
        return holdings_tool.run_holdings(
            holdings_tool.HoldingsParams(
                action=args.holdings_action,
                ts_code=getattr(args, "ts_code", "") or "",
                name=getattr(args, "name", "") or "",
            ),
            settings,
        )
    if handler == "models":
        if _json_mode(args):
            return EXIT_OK, report_tool.models_payload(args.provider, settings)
        return run_models(args.provider, settings=settings), envelope(ok=True, command="models")
    if handler == "report":
        code = run_report(args.provider, args.model, settings=settings, save=args.save, quiet=_json_mode(args))
        ok = code == EXIT_OK
        return code, envelope(ok=ok, command="report", error=None if ok else "report_failed")
    if handler == "wechat":
        return wechat_tool.run_wechat(
            wechat_tool.WechatParams(action=args.wechat_action, text=getattr(args, "text", "") or ""),
            settings,
        )
    raise ToolError("请指定子命令", EXIT_CONFIG)


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(argv)
    json_mode = _json_mode(args)
    if args.command is None:
        if json_mode:
            emit(envelope(ok=False, command="", error="missing_command"))
            return EXIT_CONFIG
        art = banner_for_stdio()
        if art:
            print(art)
        parser.print_help()
        return EXIT_OK
    try:
        code, payload = dispatch(args)
    except ToolError as exc:
        code = exc.code
        payload = envelope(ok=False, command=str(args.command or ""), error=str(exc))
    if json_mode:
        emit(payload)
        return code
    if payload.get("error") and code != EXIT_OK:
        print(payload["error"], file=sys.stderr)
    data = payload.get("data") or {}
    message = data.get("message")
    if message:
        print(message)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
