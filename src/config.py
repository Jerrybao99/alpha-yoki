"""全局配置入口。用 pydantic-settings 集中管理路径/超时/模型/密钥等配置，从 ``.env`` 加载，
业务代码通过 ``get_settings()`` 读取单例。配置项对齐 docs/dev-guide.md §10.2，禁止硬编码。
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# data/ 下属子目录英文简写映射（AGENTS.md 管道逻辑）
DATA_SUBDIRS = {
    "fin": "财务",
    "full_report": "荐股",
    "hold": "持股",
    "hot": "热点",
    "monitor": "监控",
    "feedback": "反馈",
    "rag": "知识库",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ===== LLM（DeepSeek，BRD C-04）=====
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-v4-pro"
    deepseek_base_url: str = "https://api.deepseek.com"

    # ===== 数据源（Tushare，BRD C-05）=====
    tushare_token: str = ""

    # ===== 数据与采集 =====
    data_dir: str = "data"
    concurrency: int = 4
    tushare_rate_limit: int = 500  # 每分钟调用上限（5000积分 500次/分，见 doc_id=290）
    cache_ttl_hours: int = 24  # "最新"缓存有效期（小时），过期重采以获取新报告期
    batch_size: int = 500  # 批量采集流式写盘行数（每 N 行 flush 一次）
    vip_page_size: int = 5000  # VIP 接口分页每页行数
    perf_mode: str = "mid"  # 性能模式：low（低配）/ mid（中配）/ high（高配），影响 concurrency/batch_size

    # ===== 定时任务（dev-guide §10.2）=====
    hotspot_cron_09: str = "0 9 * * *"
    hotspot_cron_17: str = "0 17 * * *"
    portfolio_cron_09: str = "0 9 * * *"
    portfolio_cron_17: str = "0 17 * * *"

    # ===== 推送 =====
    smtp_host: str = ""
    smtp_port: int = 0
    smtp_user: str = ""
    smtp_pass: str = ""
    wechat_push_enabled: bool = False

    # ===== 兜底 =====
    llm_local_fallback: bool = False

    @property
    def data_root(self) -> Path:
        """返回数据根目录并自动创建。"""
        root = Path(self.data_dir)
        root.mkdir(parents=True, exist_ok=True)
        return root

    def data_path(self, sub: str) -> Path:
        """返回 data 下子目录并自动创建（运行期 data 不入库，见 §5）。"""
        p = self.data_root / sub
        p.mkdir(parents=True, exist_ok=True)
        return p


_settings: Settings | None = None


def get_settings() -> Settings:
    """返回配置单例（重复导入复用缓存，避免反复加载 .env）。"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
