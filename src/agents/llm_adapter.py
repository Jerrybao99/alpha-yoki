"""旧导入路径兼容层；新代码使用 ``src.llm.client``。"""

from src.llm.client import LLMClient, LLMResponse, ProviderName, ProviderSpec

__all__ = ["LLMClient", "LLMResponse", "ProviderName", "ProviderSpec"]
