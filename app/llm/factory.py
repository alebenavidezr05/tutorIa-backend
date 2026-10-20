from app.core.config import Settings
from app.llm.anthropic_client import AnthropicClient
from app.llm.base import LLMClient
from app.llm.fake_client import FakeClient


def crear_llm_client(settings: Settings) -> LLMClient:
    if settings.llm_provider == "anthropic":
        return AnthropicClient(settings)
    return FakeClient()
