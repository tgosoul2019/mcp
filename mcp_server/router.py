"""
LLM Router

Routes requests to the appropriate LLM provider with support for
fallback, load balancing, and provider-specific model mapping.
"""

from typing import AsyncIterator

from .config import settings
from .providers import (
    ChatRequest,
    ChatResponse,
    StreamChunk,
    ProviderError,
    ProviderHealth,
    get_provider,
    get_all_providers,
)


class LLMRouter:
    """
    Routes chat requests to configured LLM providers.

    Features:
    - Default provider selection
    - Fallback chain when primary fails
    - Provider health checking
    - Model-to-provider mapping
    """

    # Map model prefixes to providers
    MODEL_PROVIDER_MAP = {
        "gpt-": "openai",
        "claude-": "anthropic",
        "llama": "ollama",
        "mistral": "ollama",
        "codellama": "ollama",
        "mixtral": "ollama",
        "phi": "ollama",
    }

    def __init__(self) -> None:
        self.default_provider = settings.mcp_default_provider
        self.fallback_chain = settings.fallback_providers
        self._providers = get_all_providers()

    def _infer_provider(self, model: str) -> str | None:
        """Infer provider from model name."""
        model_lower = model.lower()
        for prefix, provider in self.MODEL_PROVIDER_MAP.items():
            if model_lower.startswith(prefix):
                return provider
        return None

    def _get_provider_for_request(self, request: ChatRequest) -> str:
        """Determine which provider to use for a request."""
        # 1. Explicit provider in request
        if request.provider:
            return request.provider

        # 2. Infer from model name
        inferred = self._infer_provider(request.model)
        if inferred and inferred in self._providers:
            provider = self._providers[inferred]
            if provider.is_configured():
                return inferred

        # 3. Fall back to default
        return self.default_provider

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """
        Route a chat request to the appropriate provider.

        Tries the determined provider first, then falls back through
        the fallback chain if it fails with a retryable error.
        """
        provider_name = self._get_provider_for_request(request)
        tried_providers = set()

        # Build attempt order: requested provider first, then fallback chain
        attempt_order = [provider_name] + [
            p for p in self.fallback_chain if p != provider_name
        ]

        last_error: ProviderError | None = None

        for name in attempt_order:
            if name in tried_providers:
                continue
            tried_providers.add(name)

            provider = self._providers.get(name)
            if not provider or not provider.is_configured():
                continue

            try:
                return await provider.chat(request)
            except ProviderError as e:
                last_error = e
                if not e.retryable:
                    raise
                # Continue to next provider

        if last_error:
            raise last_error
        raise ProviderError(
            f"No available providers. Tried: {list(tried_providers)}",
            provider="router",
        )

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[StreamChunk]:
        """
        Route a streaming chat request to the appropriate provider.

        Note: Fallback is not supported for streaming (would be confusing UX).
        """
        provider_name = self._get_provider_for_request(request)
        provider = self._providers.get(provider_name)

        if not provider or not provider.is_configured():
            raise ProviderError(
                f"Provider '{provider_name}' not available",
                provider_name,
            )

        async for chunk in provider.chat_stream(request):
            yield chunk

    async def health_check_all(self) -> dict[str, ProviderHealth]:
        """Check health of all providers."""
        results = {}
        for name, provider in self._providers.items():
            results[name] = await provider.health_check()
        return results

    def list_providers(self) -> dict[str, dict]:
        """List all providers and their status."""
        return {
            name: {
                "configured": provider.is_configured(),
                "models": provider.list_models(),
            }
            for name, provider in self._providers.items()
        }


# Global router instance
router = LLMRouter()
