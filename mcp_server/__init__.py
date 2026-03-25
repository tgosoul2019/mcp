"""
MCP Server — Multi-LLM Gateway

A FastAPI-based gateway that routes requests to multiple LLM providers
with support for streaming, fallback, rate limiting, and monitoring.
"""

__version__ = "0.1.0"
__author__ = "Observabilidade Brasil"

from .app import create_app
from .config import settings

__all__ = ["create_app", "settings", "__version__"]
