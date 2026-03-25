"""
MCP Server Entry Point

Run with: python -m mcp_server
"""

import uvicorn
from .config import settings


def main() -> None:
    """Start the MCP server."""
    print("=" * 60)
    print("  MCP Server — Multi-LLM Gateway")
    print("=" * 60)
    print(f"  Host:     {settings.mcp_host}")
    print(f"  Port:     {settings.mcp_port}")
    print(f"  Debug:    {settings.mcp_debug}")
    print(f"  Default:  {settings.mcp_default_provider}")
    print(f"  Fallback: {settings.fallback_providers}")
    print("=" * 60)
    print()

    # List configured providers
    available = settings.get_available_providers()
    print(f"  Available providers: {available}")
    print()

    uvicorn.run(
        "mcp_server.app:app",
        host=settings.mcp_host,
        port=settings.mcp_port,
        reload=settings.mcp_debug,
        workers=1 if settings.mcp_debug else settings.mcp_workers,
        log_level="debug" if settings.mcp_debug else "info",
    )


if __name__ == "__main__":
    main()
