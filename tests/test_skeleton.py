"""M0 工程骨架测试（ROADMAP Step 0.4）。

目的：让 CI 有东西可跑，验证工程基线（配置入口可导入、单例可构造、数据目录可创建）。
后续里程碑的纯逻辑单测另起文件，不堆在这里。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config import DATA_SUBDIRS, Settings, get_settings


def test_settings_importable() -> None:
    """ROADMAP 给出的最小骨架用例：Settings 可导入。"""
    assert Settings is not None


def test_get_settings_singleton() -> None:
    """get_settings() 返回单例，重复调用同一实例。"""
    a = get_settings()
    b = get_settings()
    assert a is b


def test_settings_defaults() -> None:
    """默认值对齐 dev-guide §10.2 / .env.example。"""
    s = Settings()
    assert s.deepseek_model == "deepseek-v4-pro"
    assert s.deepseek_base_url == "https://api.deepseek.com"
    assert s.data_dir == "data"
    assert s.concurrency == 4
    assert s.tushare_rate_limit == 500
    assert s.cache_ttl_hours == 24
    assert s.wechat_push_enabled is False


def test_data_path_creates_subdir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """data_path() 返回子目录并自动创建，子目录名覆盖 DATA_SUBDIRS 全部键。"""
    s = Settings()
    monkeypatch.setattr(s, "data_dir", str(tmp_path))
    for sub in DATA_SUBDIRS:
        p = s.data_path(sub)
        assert p.exists() and p.is_dir()
        assert p.parent == tmp_path


def test_data_subdirs_mapping_complete() -> None:
    """data 子目录映射与 dev-guide §0 约定一致。"""
    assert set(DATA_SUBDIRS) == {
        "fin",
        "analysis",
        "hold",
        "hot",
        "monitor",
        "feedback",
        "rag",
    }


def test_main_entry_importable() -> None:
    """main.py 入口可导入且 main() 无副作用执行。"""
    from src.main import main

    main()  # 仅打印状态，不应抛异常
