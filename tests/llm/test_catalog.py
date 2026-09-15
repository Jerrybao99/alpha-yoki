"""官方模型目录契约单测。"""

from __future__ import annotations

import pytest

from src.llm.catalog import (
    MODEL_CATALOG_UPDATED,
    PROVIDER_API_URLS,
    ModelCatalogError,
    get_model,
    list_models,
)


def test_deepseek_catalog_contains_current_official_model_ids() -> None:
    model_ids = [model.model_id for model in list_models("deepseek")]
    assert model_ids == ["deepseek-flash", "deepseek-v4-pro"]


def test_glm_catalog_starts_with_current_flagship_models() -> None:
    model_ids = [model.model_id for model in list_models("glm")]
    assert model_ids == [
        "glm-5.3",
        "glm-5.3-flash",
        "glm-5.2",
        "glm-5-turbo",
        "glm-5.1",
        "glm-5",
    ]


def test_catalog_has_audited_date_and_documentation_links() -> None:
    assert MODEL_CATALOG_UPDATED == "2026-09-15"
    for provider in ("deepseek", "glm"):
        for model in list_models(provider):
            assert model.docs_url.startswith("https://")
            assert model.summary
            assert model.context_window > 0
            assert model.max_output_tokens > 0


def test_current_model_parameters_match_official_docs() -> None:
    deepseek = get_model("deepseek", "deepseek-flash")
    assert deepseek.context_window == 1_000_000
    assert deepseek.max_output_tokens == 393_216
    assert deepseek.reasoning_efforts == ("low", "high", "max")
    assert not deepseek.thinking_required

    glm = get_model("glm", "glm-5.3")
    assert glm.context_window == 1_000_000
    assert glm.max_output_tokens == 131_072
    assert glm.thinking_required
    assert glm.reasoning_efforts == ("low", "high", "max")

    glm_flash = get_model("glm", "glm-5.3-flash")
    assert {"text", "image", "video", "file"} <= set(glm_flash.input_modalities)


def test_provider_api_urls_include_current_protocols() -> None:
    assert PROVIDER_API_URLS["deepseek"]["openai_chat"] == "https://api.deepseek.com"
    assert (
        PROVIDER_API_URLS["glm"]["openai_chat"]
        == "https://open.bigmodel.cn/api/paas/v4/"
    )
    assert (
        PROVIDER_API_URLS["glm"]["openai_responses"]
        == "https://open.bigmodel.cn/api/v1"
    )


def test_get_model_returns_known_model() -> None:
    model = get_model("glm", "glm-5-turbo")
    assert model.display_name == "GLM-5-Turbo"


def test_get_model_rejects_unknown_model() -> None:
    with pytest.raises(ModelCatalogError, match="未知模型"):
        get_model("deepseek", "not-a-model")
