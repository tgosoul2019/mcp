"""
MCP Server Configuration

Loads settings from environment variables with sensible defaults.
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Server ────────────────────────────────────────────────────────────────
    mcp_host: str = Field(default="127.0.0.1", alias="MCP_HOST")
    mcp_port: int = Field(default=9200, alias="MCP_PORT")
    mcp_debug: bool = Field(default=False, alias="MCP_DEBUG")
    mcp_workers: int = Field(default=4, alias="MCP_WORKERS")

    # ── LLM Providers ─────────────────────────────────────────────────────────
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    openai_org_id: Optional[str] = Field(default=None, alias="OPENAI_ORG_ID")
    openai_base_url: str = Field(
        default="https://api.openai.com/v1", alias="OPENAI_BASE_URL"
    )

    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")

    ollama_base_url: str = Field(
        default="http://localhost:11434", alias="OLLAMA_BASE_URL"
    )

    # ── Router ────────────────────────────────────────────────────────────────
    mcp_default_provider: str = Field(default="openai", alias="MCP_DEFAULT_PROVIDER")
    mcp_fallback_chain: str = Field(
        default="openai,anthropic,ollama", alias="MCP_FALLBACK_CHAIN"
    )
    mcp_request_timeout: int = Field(default=120, alias="MCP_REQUEST_TIMEOUT")

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    mcp_rate_limit_requests: int = Field(default=100, alias="MCP_RATE_LIMIT_REQUESTS")
    mcp_rate_limit_window: int = Field(default=60, alias="MCP_RATE_LIMIT_WINDOW")

    # ── Logging ───────────────────────────────────────────────────────────────
    mcp_log_level: str = Field(default="INFO", alias="MCP_LOG_LEVEL")
    mcp_log_file: Optional[str] = Field(default=None, alias="MCP_LOG_FILE")
    mcp_log_format: str = Field(default="json", alias="MCP_LOG_FORMAT")

    # ── Monitoring ────────────────────────────────────────────────────────────
    mcp_metrics_enabled: bool = Field(default=True, alias="MCP_METRICS_ENABLED")
    mcp_admin_user: str = Field(default="admin", alias="MCP_ADMIN_USER")
    mcp_admin_password: str = Field(default="changeme", alias="MCP_ADMIN_PASSWORD")

    # ── Security ──────────────────────────────────────────────────────────────
    mcp_api_key: Optional[str] = Field(default=None, alias="MCP_API_KEY")
    mcp_cors_origins: str = Field(default="*", alias="MCP_CORS_ORIGINS")

    @property
    def fallback_providers(self) -> list[str]:
        """Parse fallback chain into list."""
        return [p.strip() for p in self.mcp_fallback_chain.split(",") if p.strip()]

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins into list."""
        if self.mcp_cors_origins == "*":
            return ["*"]
        return [o.strip() for o in self.mcp_cors_origins.split(",") if o.strip()]

    def get_available_providers(self) -> list[str]:
        """Return list of providers with configured API keys."""
        providers = []
        if self.openai_api_key:
            providers.append("openai")
        if self.anthropic_api_key:
            providers.append("anthropic")
        # Ollama doesn't need API key
        providers.append("ollama")
        return providers


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
