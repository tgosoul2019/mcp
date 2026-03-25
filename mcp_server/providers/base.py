"""
LLM Provider Base Class

Abstract interface that all LLM providers must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

from pydantic import BaseModel


class Message(BaseModel):
    """Chat message."""

    role: str  # "system", "user", "assistant"
    content: str


class ChatRequest(BaseModel):
    """Chat completion request."""

    model: str
    messages: list[Message]
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False
    provider: Optional[str] = None  # Override default provider


class ChatResponse(BaseModel):
    """Chat completion response."""

    id: str
    model: str
    provider: str
    content: str
    finish_reason: Optional[str] = None
    usage: Optional[dict] = None


class StreamChunk(BaseModel):
    """Streaming response chunk."""

    id: str
    model: str
    provider: str
    delta: str
    finish_reason: Optional[str] = None


@dataclass
class ProviderHealth:
    """Provider health status."""

    name: str
    available: bool
    latency_ms: Optional[float] = None
    error: Optional[str] = None
    models: list[str] = field(default_factory=list)


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    To add a new provider:
    1. Create a new file in providers/ (e.g., providers/newprovider.py)
    2. Inherit from LLMProvider
    3. Implement all abstract methods
    4. Register in providers/__init__.py
    """

    name: str = "base"

    @abstractmethod
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """
        Send a chat completion request.

        Args:
            request: The chat request with messages and parameters.

        Returns:
            ChatResponse with the model's reply.

        Raises:
            ProviderError: If the request fails.
        """
        pass

    @abstractmethod
    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[StreamChunk]:
        """
        Send a streaming chat completion request.

        Args:
            request: The chat request with messages and parameters.

        Yields:
            StreamChunk objects with incremental content.

        Raises:
            ProviderError: If the request fails.
        """
        pass

    @abstractmethod
    async def health_check(self) -> ProviderHealth:
        """
        Check provider health and availability.

        Returns:
            ProviderHealth with status information.
        """
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """
        Check if provider has required configuration (API keys, etc).

        Returns:
            True if provider can be used.
        """
        pass

    @abstractmethod
    def list_models(self) -> list[str]:
        """
        Return list of supported models.

        Returns:
            List of model identifiers.
        """
        pass


class ProviderError(Exception):
    """Exception raised by LLM providers."""

    def __init__(
        self,
        message: str,
        provider: str,
        status_code: Optional[int] = None,
        retryable: bool = False,
    ):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.retryable = retryable
