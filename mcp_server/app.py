"""
MCP Server FastAPI Application

Main application entry point with all routes and middleware.
"""

import time
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from .config import settings
from .router import router as llm_router
from .providers import ChatRequest, ProviderError


# Logging setup
logging.basicConfig(
    level=getattr(logging, settings.mcp_log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("mcp_server")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title="MCP Server",
        description="Multi-LLM Gateway Server",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Request tracking middleware ───────────────────────────────────────────
    @app.middleware("http")
    async def track_requests(request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        duration = (time.monotonic() - start) * 1000

        logger.info(
            f"{request.method} {request.url.path} "
            f"status={response.status_code} "
            f"duration={duration:.2f}ms "
            f"ip={request.client.host if request.client else 'unknown'}"
        )
        return response

    # ── Health endpoints ──────────────────────────────────────────────────────
    @app.get("/health")
    async def health():
        """Basic health check."""
        return {
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "0.1.0",
        }

    @app.get("/health/providers")
    async def health_providers():
        """Health check for all LLM providers."""
        results = await llm_router.health_check_all()
        return {
            "providers": {
                name: {
                    "available": h.available,
                    "latency_ms": h.latency_ms,
                    "error": h.error,
                    "models": h.models,
                }
                for name, h in results.items()
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ── Provider info ─────────────────────────────────────────────────────────
    @app.get("/v1/providers")
    async def list_providers():
        """List all available providers and their models."""
        return llm_router.list_providers()

    @app.get("/v1/models")
    async def list_models():
        """List all available models across providers."""
        providers = llm_router.list_providers()
        models = []
        for provider_name, info in providers.items():
            if info["configured"]:
                for model in info["models"]:
                    models.append({
                        "id": model,
                        "provider": provider_name,
                    })
        return {"models": models}

    # ── Chat completions (OpenAI-compatible) ──────────────────────────────────
    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request):
        """
        Chat completion endpoint (OpenAI-compatible).

        Supports both streaming and non-streaming responses.
        """
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(400, "Invalid JSON body")

        try:
            chat_request = ChatRequest(**body)
        except Exception as e:
            raise HTTPException(400, f"Invalid request: {e}")

        # Streaming response
        if chat_request.stream:
            async def generate():
                try:
                    async for chunk in llm_router.chat_stream(chat_request):
                        yield {
                            "event": "message",
                            "data": chunk.model_dump_json(),
                        }
                    yield {"event": "done", "data": "[DONE]"}
                except ProviderError as e:
                    yield {
                        "event": "error",
                        "data": f'{{"error": "{e}", "provider": "{e.provider}"}}',
                    }

            return EventSourceResponse(generate())

        # Non-streaming response
        try:
            response = await llm_router.chat(chat_request)
            return response.model_dump()
        except ProviderError as e:
            status = e.status_code or 500
            return JSONResponse(
                status_code=status,
                content={
                    "error": str(e),
                    "provider": e.provider,
                    "retryable": e.retryable,
                },
            )

    # ── Metrics endpoint ──────────────────────────────────────────────────────
    @app.get("/metrics")
    async def metrics():
        """Prometheus-style metrics (placeholder)."""
        # TODO: Implement proper metrics collection
        return {
            "requests_total": 0,
            "requests_by_provider": {},
            "latency_histogram": {},
        }

    return app


# Create app instance
app = create_app()
