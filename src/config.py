"""全局配置入口。用 pydantic-settings 集中管理路径/超时/模型/密钥等配置，从 ``.env`` 加载，
业务代码通过 ``get_settings()`` 读取单例。配置项与 ``.env.example`` 一一对应，禁止硬编码。
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# data/ 下属子目录英文简写映射（AGENTS.md 项目目录）
DATA_SUBDIRS = {
    "fin": "财务",
    "ref": "参考数据",
    "cache": "采集缓存",
    "hold": "持股",
    "monitor": "监控",
    "test": "测试产物",
    "wechat": "微信会话",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ===== LLM =====
    llm_provider: str = "deepseek"

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-flash"
    deepseek_base_url: str = "https://api.deepseek.com"

    # 智谱 GLM
    glm_api_key: str = ""
    glm_model: str = "glm-5.3-flash"
    glm_base_url: str = "https://open.bigmodel.cn/api/paas/v4/"

    # ===== 锐评子系统（src/llm/review.py）=====
    review_fallback_provider: str = "auto"  # auto=另一家 Provider；与主 Provider 相同则不切换
    review_max_retries: int = 1  # 主 Provider 校验失败后的重试次数
    review_max_tokens: int = 600  # 三段 JSON 的输出预算；思考链已关闭
    review_temperature: float = 0.3
    review_cache_enabled: bool = True  # data/cache/review/ 本地缓存

    # ===== 数据源（Tushare）=====
    tushare_token: str = ""

    # ===== 数据与采集 =====
    data_dir: str = "data"
    concurrency: int = 4
    tushare_rate_limit: int = 500  # 每分钟调用上限（5000积分 500次/分，见 doc_id=290）
    cache_ttl_hours: int = 24  # "最新"缓存有效期（小时），过期重采以获取新报告期
    batch_size: int = 500  # 批量采集流式写盘行数（每 N 行 flush 一次）
    vip_page_size: int = 5000  # VIP 接口分页每页行数
    perf_mode: str = "mid"  # 性能模式：low（低配）/ mid（中配）/ high（高配），影响 concurrency/batch_size

    # ===== 微信 iLink =====
    wechat_base_url: str = "https://ilinkai.weixin.qq.com"
    wechat_channel_version: str = "2.4.8"
    wechat_bot_agent: str = "alpha-yoki/1.0.0"
    wechat_poll_timeout_ms: int = 35000
    wechat_allowed_users: str = ""  # 空=仅扫码授权者；逗号分隔 ilink_user_id
    wechat_digest_times: str = "09:00,17:00"
    wechat_max_message_chars: int = 1800
    wechat_confirm_ttl_seconds: int = 120  # 改数据 / 锐评待确认的有效期
    wechat_trust_env: bool = False

    @property
    def data_root(self) -> Path:
        """返回数据根目录并自动创建。"""
        root = Path(self.data_dir)
        root.mkdir(parents=True, exist_ok=True)
        return root

    def data_path(self, sub: str) -> Path:
        """返回 data 下子目录并自动创建（运行期 data 不入库）。"""
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
