"""
LLM Providers Registry

Central registry for all available LLM providers.
"""

from .base import (
    LLMProvider,
    ChatRequest,
    ChatResponse,
    StreamChunk,
    ProviderHealth,
    ProviderError,
)
from .openai import OpenAIProvider
from .anthropic import AnthropicProvider
from .ollama import OllamaProvider


# Registry of all available providers
PROVIDERS: dict[str, type[LLMProvider]] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "ollama": OllamaProvider,
}


def get_provider(name: str) -> LLMProvider:
    """Get a provider instance by name."""
    if name not in PROVIDERS:
        raise ValueError(f"Unknown provider: {name}. Available: {list(PROVIDERS.keys())}")
    return PROVIDERS[name]()


def get_all_providers() -> dict[str, LLMProvider]:
    """Get instances of all registered providers."""
    return {name: cls() for name, cls in PROVIDERS.items()}


__all__ = [
    "LLMProvider",
    "ChatRequest",
    "ChatResponse",
    "StreamChunk",
    "ProviderHealth",
    "ProviderError",
    "OpenAIProvider",
    "AnthropicProvider",
    "OllamaProvider",
    "PROVIDERS",
    "get_provider",
    "get_all_providers",
]
