# ══════════════════════════════════════════════════════════════════════════════
# MCP Server — Seed de Providers Gratuitos
# LLMs com API gratuita para testes
# ══════════════════════════════════════════════════════════════════════════════

"""
Lista de providers LLM com APIs gratuitas (Março 2026):

1. Groq - Extremamente rápido, gratuito com limite generoso
2. Together AI - Free tier disponível
3. OpenRouter - Acesso a vários modelos, alguns gratuitos
4. Google AI Studio (Gemini) - Free tier
5. Mistral - Free tier para alguns modelos
6. Cerebras - Inference gratuita
7. Cohere - Free tier para testes

Para usar, configure a API_KEY no .env do VPS.
"""

GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
]

TOGETHER_FREE_MODELS = [
    "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    "meta-llama/Llama-3.2-3B-Instruct-Turbo",
    "mistralai/Mixtral-8x7B-Instruct-v0.1",
]

OPENROUTER_FREE_MODELS = [
    "meta-llama/llama-3.2-3b-instruct:free",
    "google/gemma-2-9b-it:free",
    "qwen/qwen-2-7b-instruct:free",
]

GOOGLE_GEMINI_MODELS = [
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-2.0-flash-exp",
]

SEED_PROVIDERS = [
    {
        "id": "groq",
        "name": "Groq (Gratuito)",
        "type": "custom",
        "api_base_url": "https://api.groq.com/openai/v1",
        "api_key": "",  # Set GROQ_API_KEY
        "default_model": "llama-3.3-70b-versatile",
        "models": GROQ_MODELS,
        "enabled": False,
        "rate_limit_rpm": 30,
        "rate_limit_tpm": 6000,
    },
    {
        "id": "together",
        "name": "Together AI (Free Tier)",
        "type": "custom",
        "api_base_url": "https://api.together.xyz/v1",
        "api_key": "",  # Set TOGETHER_API_KEY
        "default_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "models": TOGETHER_FREE_MODELS,
        "enabled": False,
        "rate_limit_rpm": 60,
        "rate_limit_tpm": 100000,
    },
    {
        "id": "openrouter",
        "name": "OpenRouter (Free Models)",
        "type": "custom",
        "api_base_url": "https://openrouter.ai/api/v1",
        "api_key": "",  # Set OPENROUTER_API_KEY
        "default_model": "meta-llama/llama-3.2-3b-instruct:free",
        "models": OPENROUTER_FREE_MODELS,
        "enabled": False,
        "rate_limit_rpm": 20,
        "rate_limit_tpm": 50000,
    },
    {
        "id": "google",
        "name": "Google Gemini (Free)",
        "type": "google",
        "api_base_url": "https://generativelanguage.googleapis.com/v1beta",
        "api_key": "",  # Set GOOGLE_API_KEY
        "default_model": "gemini-1.5-flash",
        "models": GOOGLE_GEMINI_MODELS,
        "enabled": False,
        "rate_limit_rpm": 15,
        "rate_limit_tpm": 32000,
    },
    {
        "id": "ollama",
        "name": "Ollama (Local)",
        "type": "ollama",
        "api_base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
        "default_model": "llama3.2",
        "models": ["llama3.2", "llama3.1", "mistral", "codellama", "phi3"],
        "enabled": False,
        "rate_limit_rpm": 1000,
        "rate_limit_tpm": 1000000,
    },
]


def get_seed_providers():
    """Retorna lista de providers para seed inicial."""
    return SEED_PROVIDERS


if __name__ == "__main__":
    import json
    print(json.dumps(SEED_PROVIDERS, indent=2))
