"""uv_sync：CI 走官方源，否则按探测耗时排序并在失败时换源。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "uv_sync.py"


def _load():
    spec = importlib.util.spec_from_file_location("uv_sync", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ci_uses_official_only() -> None:
    mod = _load()
    assert mod.pick_index(ci=True) == [mod.OFFICIAL]


def test_pick_index_ranks_fastest_success() -> None:
    mod = _load()
    order = mod.pick_index(
        ci=False,
        probes=[
            (mod.OFFICIAL, None),
            ("https://pypi.tuna.tsinghua.edu.cn/simple", 0.12),
            ("https://mirrors.aliyun.com/pypi/simple", 0.40),
        ],
    )
    assert order[0] == "https://pypi.tuna.tsinghua.edu.cn/simple"
    assert order[-1] == mod.OFFICIAL


def test_pick_index_keeps_official_when_it_is_fastest() -> None:
    mod = _load()
    order = mod.pick_index(
        ci=False,
        probes=[
            (mod.OFFICIAL, 0.20),
            ("https://pypi.tuna.tsinghua.edu.cn/simple", 0.80),
        ],
    )
    assert order[0] == mod.OFFICIAL


def test_pick_index_falls_back_to_catalog_when_all_probes_fail() -> None:
    mod = _load()
    assert mod.pick_index(ci=False, probes=[(url, None) for url in mod.INDEXES]) == list(mod.INDEXES)


def test_main_retries_next_index_after_sync_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load()
    calls: list[str] = []

    def fake_sync(index: str, extra: list[str]) -> int:
        calls.append(index)
        return 1 if len(calls) == 1 else 0

    monkeypatch.setattr(mod, "pick_index", lambda **_kwargs: ["https://slow.example/simple", mod.OFFICIAL])
    monkeypatch.setattr(mod, "run_uv_sync", fake_sync)
    assert mod.main([]) == 0
    assert calls == ["https://slow.example/simple", mod.OFFICIAL]


def test_probe_success_and_error(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load()

    class _Resp:
        status = 200

        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr(mod.urllib.request, "urlopen", lambda *_args, **_kwargs: _Resp())
    assert mod.probe("https://pypi.org/simple") is not None
    monkeypatch.setattr(
        mod.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(mod.urllib.error.URLError("down")),
    )
    assert mod.probe("https://pypi.org/simple") is None
