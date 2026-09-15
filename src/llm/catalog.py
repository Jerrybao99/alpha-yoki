"""经官方文档核验的 DeepSeek / GLM 模型目录。"""

from __future__ import annotations

from dataclasses import dataclass

from src.llm.credentials import normalize_provider

MODEL_CATALOG_UPDATED = "2026-09-15"

PROVIDER_DISPLAY_NAMES = {
    "deepseek": "DeepSeek",
    "glm": "智谱 GLM",
}

PROVIDER_DOCS_URLS = {
    "deepseek": "https://api-docs.deepseek.com/quick_start/pricing",
    "glm": "https://docs.bigmodel.cn/cn/guide/start/model-overview",
}

PROVIDER_API_URLS = {
    "deepseek": {
        "openai_chat": "https://api.deepseek.com",
        "anthropic": "https://api.deepseek.com/anthropic",
    },
    "glm": {
        "openai_chat": "https://open.bigmodel.cn/api/paas/v4/",
        "openai_responses": "https://open.bigmodel.cn/api/v1",
        "anthropic": "https://open.bigmodel.cn/api/anthropic",
    },
}


class ModelCatalogError(ValueError):
    """模型不在当前官方目录中。"""


@dataclass(frozen=True)
class ModelSpec:
    provider: str
    model_id: str
    display_name: str
    summary: str
    docs_url: str
    context_window: int
    max_output_tokens: int
    input_modalities: tuple[str, ...] = ("text",)
    thinking_required: bool = False
    reasoning_efforts: tuple[str, ...] = ()
    default_reasoning_effort: str | None = None
    recommended_temperature: float | None = None
    recommended_top_p: float | None = None


_MODELS: dict[str, tuple[ModelSpec, ...]] = {
    "deepseek": (
        ModelSpec(
            provider="deepseek",
            model_id="deepseek-flash",
            display_name="DeepSeek V4.1 Flash",
            summary="官方当前推荐的通用模型，支持思考与非思考模式",
            docs_url="https://api-docs.deepseek.com/news/news260910",
            context_window=1_000_000,
            max_output_tokens=393_216,
            input_modalities=("text", "image", "file"),
            reasoning_efforts=("low", "high", "max"),
            default_reasoning_effort="high",
        ),
        ModelSpec(
            provider="deepseek",
            model_id="deepseek-v4-pro",
            display_name="DeepSeek V4 Pro",
            summary="旗舰模型，官方确认继续提供独立 API 服务",
            docs_url="https://api-docs.deepseek.com/quick_start/pricing",
            context_window=1_000_000,
            max_output_tokens=393_216,
            reasoning_efforts=("low", "high", "max"),
            default_reasoning_effort="high",
        ),
    ),
    "glm": (
        ModelSpec(
            provider="glm",
            model_id="glm-5.3",
            display_name="GLM-5.3",
            summary="最新文本旗舰，面向复杂软件工程与 Agent 任务",
            docs_url="https://docs.bigmodel.cn/cn/guide/models/text/glm-5.3",
            context_window=1_000_000,
            max_output_tokens=131_072,
            thinking_required=True,
            reasoning_efforts=("low", "high", "max"),
            default_reasoning_effort="max",
            recommended_temperature=1.0,
            recommended_top_p=0.95,
        ),
        ModelSpec(
            provider="glm",
            model_id="glm-5.3-flash",
            display_name="GLM-5.3-Flash",
            summary="最新低成本原生多模态模型，适合金融研究与文档任务",
            docs_url="https://docs.bigmodel.cn/cn/guide/models/vlm/glm-5.3-flash",
            context_window=1_000_000,
            max_output_tokens=131_072,
            input_modalities=("text", "image", "video", "file"),
            thinking_required=True,
            reasoning_efforts=("low", "high", "max"),
            default_reasoning_effort="max",
            recommended_temperature=1.0,
            recommended_top_p=0.95,
        ),
        ModelSpec(
            provider="glm",
            model_id="glm-5.2",
            display_name="GLM-5.2",
            summary="长程任务旗舰模型，支持 1M 上下文",
            docs_url="https://docs.bigmodel.cn/cn/guide/models/text/glm-5.2",
            context_window=1_000_000,
            max_output_tokens=131_072,
            reasoning_efforts=("low", "high", "max"),
            default_reasoning_effort="max",
            recommended_temperature=1.0,
            recommended_top_p=0.95,
        ),
        ModelSpec(
            provider="glm",
            model_id="glm-5-turbo",
            display_name="GLM-5-Turbo",
            summary="面向长链路 Agent 与 OpenClaw 场景优化",
            docs_url="https://docs.bigmodel.cn/cn/guide/models/text/glm-5-turbo",
            context_window=200_000,
            max_output_tokens=131_072,
        ),
        ModelSpec(
            provider="glm",
            model_id="glm-5.1",
            display_name="GLM-5.1",
            summary="官方已开放 API 的 GLM 5.1 文本模型",
            docs_url="https://docs.bigmodel.cn/cn/guide/models/text/glm-5.1",
            context_window=200_000,
            max_output_tokens=131_072,
        ),
        ModelSpec(
            provider="glm",
            model_id="glm-5",
            display_name="GLM-5",
            summary="官方已开放 API 的 GLM 5 文本模型",
            docs_url="https://docs.bigmodel.cn/cn/guide/models/text/glm-5",
            context_window=200_000,
            max_output_tokens=131_072,
        ),
    ),
}


def list_models(provider: str) -> tuple[ModelSpec, ...]:
    """返回指定 Provider 的已核验模型目录。"""
    return _MODELS[normalize_provider(provider)]


def get_model(provider: str, model_id: str) -> ModelSpec:
    """按 Provider 和模型 ID 查找模型。"""
    model = find_model(provider, model_id)
    if model is not None:
        return model
    raise ModelCatalogError(f"{provider} 未知模型：{model_id}")


def find_model(provider: str, model_id: str) -> ModelSpec | None:
    """查找模型；自定义或未来模型返回 None。"""
    for model in list_models(provider):
        if model.model_id == model_id:
            return model
    return None
