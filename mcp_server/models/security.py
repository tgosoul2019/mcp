# ══════════════════════════════════════════════════════════════════════════════
# MCP Server — Security Configuration Models
# Nível 1 de Memória: Políticas de Segurança
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class FilterAction(str, Enum):
    """Ação quando um filtro é acionado."""
    BLOCK = "block"           # Bloqueia completamente
    REDACT = "redact"         # Remove/mascara o conteúdo
    WARN = "warn"             # Permite mas registra warning
    ALLOW = "allow"           # Permite explicitamente


class FilterDirection(str, Enum):
    """Direção do filtro."""
    INPUT = "input"           # Filtra entrada do usuário
    OUTPUT = "output"         # Filtra saída da LLM
    BOTH = "both"             # Filtra ambos


class ContentFilter(BaseModel):
    """Filtro de conteúdo individual."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = Field(..., description="Nome do filtro")
    enabled: bool = Field(default=True)
    
    # Padrão de match
    pattern: str = Field(..., description="Regex ou string para match")
    is_regex: bool = Field(default=True, description="Se é expressão regular")
    case_sensitive: bool = Field(default=False)
    
    # Comportamento
    direction: FilterDirection = Field(default=FilterDirection.BOTH)
    action: FilterAction = Field(default=FilterAction.BLOCK)
    replacement: Optional[str] = Field(default="[REDACTED]", description="Texto de substituição se action=redact")
    
    # Contexto
    description: str = Field(default="", description="Descrição do filtro")
    category: str = Field(default="general", description="Categoria (pii, profanity, secrets, etc)")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SecurityRule(BaseModel):
    """Regra de segurança de alto nível."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = Field(..., description="Nome da regra")
    enabled: bool = Field(default=True)
    priority: int = Field(default=100, description="Prioridade (menor = primeiro)")
    
    # Condições
    applies_to_providers: list[str] = Field(default_factory=list, description="IDs de providers (vazio = todos)")
    applies_to_models: list[str] = Field(default_factory=list, description="Modelos específicos (vazio = todos)")
    
    # Limites
    max_input_tokens: Optional[int] = Field(default=None, description="Limite de tokens de entrada")
    max_output_tokens: Optional[int] = Field(default=None, description="Limite de tokens de saída")
    max_context_messages: Optional[int] = Field(default=None, description="Limite de mensagens no contexto")
    
    # Filtros de conteúdo associados
    content_filters: list[str] = Field(default_factory=list, description="IDs de filtros aplicáveis")
    
    # Sistema
    system_prompt_prefix: Optional[str] = Field(default=None, description="Prefixo obrigatório no system prompt")
    system_prompt_suffix: Optional[str] = Field(default=None, description="Sufixo obrigatório no system prompt")
    blocked_topics: list[str] = Field(default_factory=list, description="Tópicos bloqueados")
    
    # Logging
    log_requests: bool = Field(default=True, description="Logar todas as requisições")
    log_responses: bool = Field(default=True, description="Logar todas as respostas")
    
    description: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SecurityConfig(BaseModel):
    """Configuração completa de segurança (Nível 1 de Memória)."""
    
    enabled: bool = Field(default=True, description="Segurança ativa globalmente")
    
    # Filtros de conteúdo
    content_filters: list[ContentFilter] = Field(default_factory=list)
    
    # Regras de segurança
    rules: list[SecurityRule] = Field(default_factory=list)
    
    # PII Protection
    pii_detection_enabled: bool = Field(default=True)
    pii_categories: list[str] = Field(
        default_factory=lambda: ["cpf", "email", "phone", "credit_card", "api_key"]
    )
    
    # Rate limiting por usuário
    user_rate_limit_enabled: bool = Field(default=True)
    user_rate_limit_rpm: int = Field(default=30, description="Requests por minuto por usuário")
    user_rate_limit_tpm: int = Field(default=50000, description="Tokens por minuto por usuário")
    
    # Auditoria
    audit_enabled: bool = Field(default=True)
    audit_retention_days: int = Field(default=30)
    
    # Palavras/padrões bloqueados globalmente
    global_blocked_patterns: list[str] = Field(default_factory=list)
    
    def get_filter(self, filter_id: str) -> Optional[ContentFilter]:
        """Busca um filtro pelo ID."""
        for f in self.content_filters:
            if f.id == filter_id:
                return f
        return None
    
    def get_active_filters(self, direction: FilterDirection = FilterDirection.BOTH) -> list[ContentFilter]:
        """Retorna filtros ativos para uma direção."""
        return [
            f for f in self.content_filters 
            if f.enabled and (f.direction == direction or f.direction == FilterDirection.BOTH)
        ]
    
    def get_rule(self, rule_id: str) -> Optional[SecurityRule]:
        """Busca uma regra pelo ID."""
        for r in self.rules:
            if r.id == rule_id:
                return r
        return None
    
    def get_active_rules(self) -> list[SecurityRule]:
        """Retorna regras ativas ordenadas por prioridade."""
        return sorted([r for r in self.rules if r.enabled], key=lambda r: r.priority)


# ── Filtros padrão ────────────────────────────────────────────────────────────

DEFAULT_CONTENT_FILTERS = [
    ContentFilter(
        id="pii_cpf",
        name="CPF Brasileiro",
        pattern=r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}",
        category="pii",
        action=FilterAction.REDACT,
        description="Detecta e mascara CPFs"
    ),
    ContentFilter(
        id="pii_email",
        name="Email",
        pattern=r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        category="pii",
        action=FilterAction.WARN,
        description="Detecta emails"
    ),
    ContentFilter(
        id="pii_phone_br",
        name="Telefone BR",
        pattern=r"(?:\+55\s?)?(?:\(?\d{2}\)?\s?)?\d{4,5}-?\d{4}",
        category="pii",
        action=FilterAction.WARN,
        description="Detecta telefones brasileiros"
    ),
    ContentFilter(
        id="secrets_api_key",
        name="API Keys",
        pattern=r"(?:sk-|api[_-]?key|bearer\s+)[a-zA-Z0-9_-]{20,}",
        category="secrets",
        action=FilterAction.BLOCK,
        case_sensitive=False,
        description="Bloqueia API keys e tokens"
    ),
    ContentFilter(
        id="pii_credit_card",
        name="Cartão de Crédito",
        pattern=r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
        category="pii",
        action=FilterAction.BLOCK,
        description="Bloqueia números de cartão de crédito"
    ),
]


DEFAULT_SECURITY_RULES = [
    SecurityRule(
        id="default_limits",
        name="Limites Padrão",
        priority=100,
        max_input_tokens=8000,
        max_output_tokens=4000,
        max_context_messages=50,
        description="Limites padrão para todas as requisições"
    ),
]
