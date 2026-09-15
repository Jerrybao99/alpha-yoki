"""探测最快 PyPI 源后执行 uv sync。CI 固定官方源；缺包则按名次换源。"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

OFFICIAL = "https://pypi.org/simple"
INDEXES = (
    OFFICIAL,
    "https://pypi.tuna.tsinghua.edu.cn/simple",
    "https://mirrors.aliyun.com/pypi/simple",
)
TIMEOUT_SEC = 2.0


def probe(url: str, timeout: float = TIMEOUT_SEC) -> float | None:
    target = url.rstrip("/") + "/pip/"
    started = time.monotonic()
    try:
        with urllib.request.urlopen(target, timeout=timeout) as resp:
            status = int(getattr(resp, "status", 200))
            if 200 <= status < 300:
                return time.monotonic() - started
    except (urllib.error.URLError, TimeoutError, OSError):
        return None
    return None


def pick_index(
    *,
    ci: bool,
    probes: list[tuple[str, float | None]] | None = None,
) -> list[str]:
    if ci:
        return [OFFICIAL]
    measured = list(probes) if probes is not None else [(url, probe(url)) for url in INDEXES]
    ranked = sorted(((url, cost) for url, cost in measured if cost is not None), key=lambda item: item[1])
    if not ranked:
        return [url for url, _cost in measured]
    order = [url for url, _cost in ranked]
    order.extend(url for url, cost in measured if cost is None and url not in order)
    return order


def run_uv_sync(index: str, extra: list[str]) -> int:
    env = os.environ.copy()
    env["UV_DEFAULT_INDEX"] = index
    try:
        return subprocess.call(["uv", "sync", "--default-index", index, *extra], env=env)
    except FileNotFoundError:
        print("未找到 uv，请先安装：https://docs.astral.sh/uv/", file=sys.stderr)
        return 2


def main(argv: list[str] | None = None) -> int:
    extra = list(sys.argv[1:] if argv is None else argv)
    ci = bool(os.environ.get("CI"))
    for index in pick_index(ci=ci):
        print(f"使用索引 {index}", flush=True)
        code = run_uv_sync(index, extra)
        if code == 0:
            return 0
        print("同步失败，换源重试", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
