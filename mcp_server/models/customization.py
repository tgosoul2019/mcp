# ══════════════════════════════════════════════════════════════════════════════
# MCP Server — Customization Configuration Models
# Nível 2 de Memória: Personalização e Comportamento
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field
import uuid


class ToneType(str, Enum):
    """Tipos de tom de comunicação."""
    FORMAL = "formal"
    CASUAL = "casual"
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    TECHNICAL = "technical"
    EDUCATIONAL = "educational"
    CONCISE = "concise"
    DETAILED = "detailed"


class LanguageStyle(str, Enum):
    """Estilos de linguagem."""
    PT_BR = "pt-br"
    PT_PT = "pt-pt"
    EN_US = "en-us"
    EN_UK = "en-uk"
    ES = "es"
    AUTO = "auto"


class PersonaConfig(BaseModel):
    """Configuração de persona/personalidade do assistente."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = Field(..., description="Nome da persona")
    enabled: bool = Field(default=True)
    is_default: bool = Field(default=False)
    
    # Identidade
    assistant_name: str = Field(default="Assistente", description="Nome do assistente")
    description: str = Field(default="", description="Descrição da persona")
    
    # Comunicação
    tone: ToneType = Field(default=ToneType.PROFESSIONAL)
    language: LanguageStyle = Field(default=LanguageStyle.PT_BR)
    
    # System prompt customizado
    system_prompt: str = Field(
        default="Você é um assistente útil e profissional.",
        description="System prompt base"
    )
    
    # Comportamentos
    use_emoji: bool = Field(default=False, description="Usar emojis nas respostas")
    use_markdown: bool = Field(default=True, description="Usar formatação Markdown")
    max_response_length: Optional[int] = Field(default=None, description="Limite de caracteres")
    
    # Contexto adicional
    knowledge_context: str = Field(default="", description="Contexto adicional de conhecimento")
    forbidden_topics: list[str] = Field(default_factory=list, description="Tópicos que a persona não deve abordar")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class RetryConfig(BaseModel):
    """Configuração de retry/fallback."""
    
    enabled: bool = Field(default=True)
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_delay_ms: int = Field(default=1000, description="Delay inicial em ms")
    exponential_backoff: bool = Field(default=True)
    max_delay_ms: int = Field(default=30000, description="Delay máximo em ms")
    
    # Condições de retry
    retry_on_timeout: bool = Field(default=True)
    retry_on_rate_limit: bool = Field(default=True)
    retry_on_server_error: bool = Field(default=True)
    retry_status_codes: list[int] = Field(default_factory=lambda: [429, 500, 502, 503, 504])
    
    # Fallback
    fallback_enabled: bool = Field(default=True)
    fallback_on_error: bool = Field(default=True)


class ProviderOverride(BaseModel):
    """Override de configuração para um provider específico."""
    
    provider_id: str = Field(..., description="ID do provider")
    force_model: Optional[str] = Field(default=None, description="Forçar uso de modelo específico")
    temperature_override: Optional[float] = Field(default=None, ge=0, le=2)
    max_tokens_override: Optional[int] = Field(default=None)
    enabled: bool = Field(default=True)


class RoutingRule(BaseModel):
    """Regra de roteamento de requisições."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = Field(..., description="Nome da regra")
    enabled: bool = Field(default=True)
    priority: int = Field(default=100)
    
    # Condições
    match_keywords: list[str] = Field(default_factory=list, description="Keywords que ativam a regra")
    match_user_ids: list[str] = Field(default_factory=list, description="User IDs específicos")
    match_time_start: Optional[str] = Field(default=None, description="Horário início (HH:MM)")
    match_time_end: Optional[str] = Field(default=None, description="Horário fim (HH:MM)")
    
    # Ação
    force_provider_id: Optional[str] = Field(default=None, description="Forçar provider específico")
    force_model: Optional[str] = Field(default=None, description="Forçar modelo específico")
    apply_persona_id: Optional[str] = Field(default=None, description="Aplicar persona específica")
    
    description: str = Field(default="")


class CustomizationConfig(BaseModel):
    """Configuração completa de customização (Nível 2 de Memória)."""
    
    # Personas
    personas: list[PersonaConfig] = Field(default_factory=list)
    default_persona_id: Optional[str] = Field(default=None)
    
    # Retry
    retry: RetryConfig = Field(default_factory=RetryConfig)
    
    # Provider overrides
    provider_overrides: list[ProviderOverride] = Field(default_factory=list)
    
    # Routing
    routing_rules: list[RoutingRule] = Field(default_factory=list)
    
    # Global settings
    force_provider_id: Optional[str] = Field(default=None, description="Forçar provider globalmente")
    force_model: Optional[str] = Field(default=None, description="Forçar modelo globalmente")
    
    # Defaults
    default_temperature: float = Field(default=0.7, ge=0, le=2)
    default_max_tokens: int = Field(default=2048)
    default_top_p: float = Field(default=1.0, ge=0, le=1)
    
    # Streaming
    streaming_enabled: bool = Field(default=True)
    stream_chunk_size: int = Field(default=10, description="Tokens por chunk no streaming")
    
    # Cache
    cache_enabled: bool = Field(default=False)
    cache_ttl_seconds: int = Field(default=3600)
    cache_max_entries: int = Field(default=1000)
    
    # Extras
    extra_settings: dict[str, Any] = Field(default_factory=dict, description="Configurações extras")
    
    def get_persona(self, persona_id: str) -> Optional[PersonaConfig]:
        """Busca uma persona pelo ID."""
        for p in self.personas:
            if p.id == persona_id:
                return p
        return None
    
    def get_default_persona(self) -> Optional[PersonaConfig]:
        """Retorna a persona padrão."""
        if self.default_persona_id:
            return self.get_persona(self.default_persona_id)
        # Procura por is_default=True
        for p in self.personas:
            if p.is_default and p.enabled:
                return p
        return None
    
    def get_provider_override(self, provider_id: str) -> Optional[ProviderOverride]:
        """Busca override de um provider."""
        for o in self.provider_overrides:
            if o.provider_id == provider_id and o.enabled:
                return o
        return None
    
    def get_matching_routing_rule(self, keywords: list[str] = None, user_id: str = None) -> Optional[RoutingRule]:
        """Encontra a primeira regra de roteamento que match."""
        rules = sorted([r for r in self.routing_rules if r.enabled], key=lambda r: r.priority)
        for rule in rules:
            # Check keywords
            if rule.match_keywords and keywords:
                if any(kw.lower() in " ".join(keywords).lower() for kw in rule.match_keywords):
                    return rule
            # Check user
            if rule.match_user_ids and user_id:
                if user_id in rule.match_user_ids:
                    return rule
        return None


# ── Personas padrão ───────────────────────────────────────────────────────────

DEFAULT_PERSONAS = [
    PersonaConfig(
        id="default",
        name="Assistente Padrão",
        is_default=True,
        assistant_name="Assistente MCP",
        tone=ToneType.PROFESSIONAL,
        language=LanguageStyle.PT_BR,
        system_prompt="""Você é um assistente profissional e útil.

Diretrizes:
- Responda de forma clara e objetiva
- Use português brasileiro
- Formate respostas com Markdown quando apropriado
- Seja educado e prestativo""",
        use_markdown=True,
        description="Persona padrão do sistema"
    ),
    PersonaConfig(
        id="technical",
        name="Assistente Técnico",
        is_default=False,
        assistant_name="Tech Assistant",
        tone=ToneType.TECHNICAL,
        language=LanguageStyle.PT_BR,
        system_prompt="""Você é um assistente técnico especializado em desenvolvimento de software.

Diretrizes:
- Forneça respostas técnicas precisas
- Use exemplos de código quando relevante
- Explique conceitos complexos de forma clara
- Siga boas práticas de desenvolvimento""",
        use_markdown=True,
        description="Persona para questões técnicas e de programação"
    ),
]
