# ══════════════════════════════════════════════════════════════════════════════
# MCP Server — LLM Configuration Models
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class LLMProviderType(str, Enum):
    """Tipos de provedores LLM suportados."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    AZURE_OPENAI = "azure_openai"
    GOOGLE = "google"
    CUSTOM = "custom"


class LLMProvider(BaseModel):
    """Configuração de um provedor LLM."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = Field(..., description="Nome do provedor (ex: OpenAI GPT-4)")
    type: LLMProviderType = Field(..., description="Tipo do provedor")
    enabled: bool = Field(default=True, description="Se o provedor está ativo")
    
    # Autenticação
    api_key: Optional[str] = Field(default=None, description="API Key (criptografada)")
    api_base_url: Optional[str] = Field(default=None, description="URL base da API")
    organization_id: Optional[str] = Field(default=None, description="ID da organização")
    
    # Modelos disponíveis
    models: list[str] = Field(default_factory=list, description="Modelos disponíveis")
    default_model: Optional[str] = Field(default=None, description="Modelo padrão")
    
    # Limites
    max_tokens: int = Field(default=4096, description="Máximo de tokens por request")
    rate_limit_rpm: int = Field(default=60, description="Limite de requests por minuto")
    rate_limit_tpm: int = Field(default=100000, description="Limite de tokens por minuto")
    
    # Configurações
    timeout: int = Field(default=120, description="Timeout em segundos")
    temperature: float = Field(default=0.7, ge=0, le=2, description="Temperatura padrão")
    
    # Fallback
    priority: int = Field(default=100, description="Prioridade (menor = mais prioritário)")
    is_fallback: bool = Field(default=False, description="Usar como fallback")
    
    # Metadados
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class LLMConfig(BaseModel):
    """Configuração geral de LLMs."""
    
    providers: list[LLMProvider] = Field(default_factory=list)
    default_provider_id: Optional[str] = Field(default=None)
    fallback_enabled: bool = Field(default=True)
    fallback_order: list[str] = Field(default_factory=list, description="IDs em ordem de fallback")
    
    # Global settings
    global_timeout: int = Field(default=120)
    global_max_tokens: int = Field(default=4096)
    
    def get_provider(self, provider_id: str) -> Optional[LLMProvider]:
        """Busca um provedor pelo ID."""
        for p in self.providers:
            if p.id == provider_id:
                return p
        return None
    
    def get_active_providers(self) -> list[LLMProvider]:
        """Retorna apenas provedores ativos."""
        return [p for p in self.providers if p.enabled]
    
    def get_fallback_chain(self) -> list[LLMProvider]:
        """Retorna a cadeia de fallback ordenada."""
        if self.fallback_order:
            ordered = []
            for pid in self.fallback_order:
                p = self.get_provider(pid)
                if p and p.enabled:
                    ordered.append(p)
            return ordered
        # Fallback por prioridade
        return sorted(self.get_active_providers(), key=lambda p: p.priority)
