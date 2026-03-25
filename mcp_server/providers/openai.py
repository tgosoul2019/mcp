"""
OpenAI Provider

Implementation for OpenAI API (GPT-4, GPT-3.5, etc).
"""

import time
from typing import AsyncIterator
from uuid import uuid4

from openai import AsyncOpenAI, APIError, APIConnectionError, RateLimitError

from ..config import settings
from .base import (
    LLMProvider,
    ChatRequest,
    ChatResponse,
    StreamChunk,
    ProviderHealth,
    ProviderError,
)


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""

    name = "openai"

    # Supported models (subset — OpenAI has many)
    MODELS = [
        "gpt-4-turbo-preview",
        "gpt-4-0125-preview",
        "gpt-4-1106-preview",
        "gpt-4",
        "gpt-4-32k",
        "gpt-3.5-turbo",
        "gpt-3.5-turbo-16k",
    ]

    def __init__(self) -> None:
        self._client: AsyncOpenAI | None = None
        if self.is_configured():
            self._client = AsyncOpenAI(
                api_key=settings.openai_api_key,
                organization=settings.openai_org_id or None,
                base_url=settings.openai_base_url,
                timeout=settings.mcp_request_timeout,
            )

    def is_configured(self) -> bool:
        return bool(settings.openai_api_key)

    def list_models(self) -> list[str]:
        return self.MODELS

    async def chat(self, request: ChatRequest) -> ChatResponse:
        if not self._client:
            raise ProviderError("OpenAI not configured", self.name)

        try:
            messages = [{"role": m.role, "content": m.content} for m in request.messages]

            response = await self._client.chat.completions.create(
                model=request.model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=False,
            )

            choice = response.choices[0]
            return ChatResponse(
                id=response.id,
                model=response.model,
                provider=self.name,
                content=choice.message.content or "",
                finish_reason=choice.finish_reason,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                } if response.usage else None,
            )

        except RateLimitError as e:
            raise ProviderError(str(e), self.name, status_code=429, retryable=True)
        except APIConnectionError as e:
            raise ProviderError(str(e), self.name, retryable=True)
        except APIError as e:
            raise ProviderError(str(e), self.name, status_code=e.status_code)

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[StreamChunk]:
        if not self._client:
            raise ProviderError("OpenAI not configured", self.name)

        try:
            messages = [{"role": m.role, "content": m.content} for m in request.messages]

            stream = await self._client.chat.completions.create(
                model=request.model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=True,
            )

            response_id = f"chatcmpl-{uuid4().hex[:12]}"

            async for chunk in stream:
                if chunk.choices:
                    choice = chunk.choices[0]
                    delta = choice.delta.content or ""
                    if delta or choice.finish_reason:
                        yield StreamChunk(
                            id=response_id,
                            model=request.model,
                            provider=self.name,
                            delta=delta,
                            finish_reason=choice.finish_reason,
                        )

        except RateLimitError as e:
            raise ProviderError(str(e), self.name, status_code=429, retryable=True)
        except APIConnectionError as e:
            raise ProviderError(str(e), self.name, retryable=True)
        except APIError as e:
            raise ProviderError(str(e), self.name, status_code=e.status_code)

    async def health_check(self) -> ProviderHealth:
        if not self._client:
            return ProviderHealth(
                name=self.name,
                available=False,
                error="Not configured (missing OPENAI_API_KEY)",
            )

        try:
            start = time.monotonic()
            # Simple models list call to check connectivity
            await self._client.models.list()
            latency = (time.monotonic() - start) * 1000

            return ProviderHealth(
                name=self.name,
                available=True,
                latency_ms=round(latency, 2),
                models=self.MODELS,
            )
        except Exception as e:
            return ProviderHealth(
                name=self.name,
                available=False,
                error=str(e)[:200],
            )
