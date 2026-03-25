"""
Ollama Provider

Implementation for local Ollama server (Llama, Mistral, etc).
"""

import time
from typing import AsyncIterator
from uuid import uuid4

import httpx

from ..config import settings
from .base import (
    LLMProvider,
    ChatRequest,
    ChatResponse,
    StreamChunk,
    ProviderHealth,
    ProviderError,
)


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider."""

    name = "ollama"

    # Common models (actual availability depends on local setup)
    MODELS = [
        "llama2",
        "llama2:70b",
        "codellama",
        "mistral",
        "mixtral",
        "phi",
        "neural-chat",
        "starling-lm",
    ]

    def __init__(self) -> None:
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.timeout = settings.mcp_request_timeout

    def is_configured(self) -> bool:
        # Ollama doesn't need API key, just needs to be running
        return True

    def list_models(self) -> list[str]:
        return self.MODELS

    async def chat(self, request: ChatRequest) -> ChatResponse:
        try:
            messages = [{"role": m.role, "content": m.content} for m in request.messages]

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": request.model,
                        "messages": messages,
                        "stream": False,
                        "options": {
                            "temperature": request.temperature,
                            "num_predict": request.max_tokens or -1,
                        },
                    },
                )
                response.raise_for_status()
                data = response.json()

            return ChatResponse(
                id=f"ollama-{uuid4().hex[:12]}",
                model=request.model,
                provider=self.name,
                content=data.get("message", {}).get("content", ""),
                finish_reason="stop" if data.get("done") else None,
                usage={
                    "prompt_tokens": data.get("prompt_eval_count", 0),
                    "completion_tokens": data.get("eval_count", 0),
                    "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
                },
            )

        except httpx.ConnectError as e:
            raise ProviderError(
                f"Cannot connect to Ollama at {self.base_url}: {e}",
                self.name,
                retryable=True,
            ) from e
        except httpx.HTTPStatusError as e:
            raise ProviderError(
                str(e),
                self.name,
                status_code=e.response.status_code,
            ) from e

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[StreamChunk]:
        try:
            messages = [{"role": m.role, "content": m.content} for m in request.messages]
            response_id = f"ollama-{uuid4().hex[:12]}"

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json={
                        "model": request.model,
                        "messages": messages,
                        "stream": True,
                        "options": {
                            "temperature": request.temperature,
                            "num_predict": request.max_tokens or -1,
                        },
                    },
                ) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            import json
                            data = json.loads(line)
                            content = data.get("message", {}).get("content", "")
                            done = data.get("done", False)

                            if content or done:
                                yield StreamChunk(
                                    id=response_id,
                                    model=request.model,
                                    provider=self.name,
                                    delta=content,
                                    finish_reason="stop" if done else None,
                                )
                        except json.JSONDecodeError:
                            continue

        except httpx.ConnectError as e:
            raise ProviderError(
                f"Cannot connect to Ollama at {self.base_url}: {e}",
                self.name,
                retryable=True,
            ) from e
        except httpx.HTTPStatusError as e:
            raise ProviderError(
                str(e),
                self.name,
                status_code=e.response.status_code,
            ) from e

    async def health_check(self) -> ProviderHealth:
        try:
            start = time.monotonic()

            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                data = response.json()

            latency = (time.monotonic() - start) * 1000

            # Get actually installed models
            models = [m.get("name", "") for m in data.get("models", [])]

            return ProviderHealth(
                name=self.name,
                available=True,
                latency_ms=round(latency, 2),
                models=models or self.MODELS,
            )

        except httpx.ConnectError:
            return ProviderHealth(
                name=self.name,
                available=False,
                error=f"Cannot connect to Ollama at {self.base_url}",
            )
        except Exception as e:
            return ProviderHealth(
                name=self.name,
                available=False,
                error=str(e)[:200],
            )
