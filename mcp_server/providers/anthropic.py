"""
Anthropic Claude Provider

Implementation for Anthropic API (Claude 3, Claude 2, etc).
"""

import time
from typing import AsyncIterator
from uuid import uuid4

from anthropic import AsyncAnthropic, APIError, APIConnectionError, RateLimitError

from ..config import settings
from .base import (
    LLMProvider,
    ChatRequest,
    ChatResponse,
    StreamChunk,
    ProviderHealth,
    ProviderError,
)


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider."""

    name = "anthropic"

    # Supported models
    MODELS = [
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
        "claude-2.1",
        "claude-2.0",
        "claude-instant-1.2",
    ]

    def __init__(self) -> None:
        self._client: AsyncAnthropic | None = None
        if self.is_configured():
            self._client = AsyncAnthropic(
                api_key=settings.anthropic_api_key,
                timeout=settings.mcp_request_timeout,
            )

    def is_configured(self) -> bool:
        return bool(settings.anthropic_api_key)

    def list_models(self) -> list[str]:
        return self.MODELS

    def _convert_messages(self, messages: list) -> tuple[str | None, list[dict]]:
        """Convert OpenAI-style messages to Anthropic format."""
        system = None
        converted = []

        for msg in messages:
            if msg.role == "system":
                system = msg.content
            else:
                converted.append({
                    "role": msg.role,
                    "content": msg.content,
                })

        return system, converted

    async def chat(self, request: ChatRequest) -> ChatResponse:
        if not self._client:
            raise ProviderError("Anthropic not configured", self.name)

        try:
            system, messages = self._convert_messages(request.messages)

            response = await self._client.messages.create(
                model=request.model,
                messages=messages,
                system=system or "",
                temperature=request.temperature,
                max_tokens=request.max_tokens or 4096,
            )

            content = ""
            if response.content:
                content = response.content[0].text

            return ChatResponse(
                id=response.id,
                model=response.model,
                provider=self.name,
                content=content,
                finish_reason=response.stop_reason,
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                } if response.usage else None,
            )

        except RateLimitError as e:
            raise ProviderError(str(e), self.name, status_code=429, retryable=True) from e
        except APIConnectionError as e:
            raise ProviderError(str(e), self.name, retryable=True) from e
        except APIError as e:
            raise ProviderError(str(e), self.name, status_code=getattr(e, "status_code", None)) from e

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[StreamChunk]:
        if not self._client:
            raise ProviderError("Anthropic not configured", self.name)

        try:
            system, messages = self._convert_messages(request.messages)

            response_id = f"msg-{uuid4().hex[:12]}"

            async with self._client.messages.stream(
                model=request.model,
                messages=messages,
                system=system or "",
                temperature=request.temperature,
                max_tokens=request.max_tokens or 4096,
            ) as stream:
                async for text in stream.text_stream:
                    yield StreamChunk(
                        id=response_id,
                        model=request.model,
                        provider=self.name,
                        delta=text,
                        finish_reason=None,
                    )

                # Final chunk with finish reason
                yield StreamChunk(
                    id=response_id,
                    model=request.model,
                    provider=self.name,
                    delta="",
                    finish_reason="stop",
                )

        except RateLimitError as e:
            raise ProviderError(str(e), self.name, status_code=429, retryable=True) from e
        except APIConnectionError as e:
            raise ProviderError(str(e), self.name, retryable=True) from e
        except APIError as e:
            raise ProviderError(str(e), self.name, status_code=getattr(e, "status_code", None)) from e

    async def health_check(self) -> ProviderHealth:
        if not self._client:
            return ProviderHealth(
                name=self.name,
                available=False,
                error="Not configured (missing ANTHROPIC_API_KEY)",
            )

        try:
            start = time.monotonic()
            # Quick test with minimal tokens
            await self._client.messages.create(
                model="claude-3-haiku-20240307",
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=1,
            )
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
