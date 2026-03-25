# ══════════════════════════════════════════════════════════════════════════════
# MCP Server — Customization Memory (Nível 2)
# Responsável por personalização e comportamento do assistente
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import logging
from typing import Optional, Any
from dataclasses import dataclass, field

from ..models.customization import (
    CustomizationConfig,
    PersonaConfig,
    RetryConfig,
    RoutingRule,
    ToneType,
)

logger = logging.getLogger(__name__)


@dataclass
class RequestContext:
    """Contexto de uma requisição para personalização."""
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    keywords: list[str] = field(default_factory=list)
    provider_id: Optional[str] = None
    model: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class CustomizationResult:
    """Resultado da aplicação de customizações."""
    persona: Optional[PersonaConfig] = None
    system_prompt: str = ""
    temperature: float = 0.7
    max_tokens: int = 2048
    force_provider_id: Optional[str] = None
    force_model: Optional[str] = None
    streaming: bool = True
    retry_config: Optional[RetryConfig] = None
    applied_rules: list[str] = field(default_factory=list)
    extra_params: dict[str, Any] = field(default_factory=dict)


class CustomizationMemory:
    """
    Nível 2 de Memória: Customização
    
    Responsabilidades:
    - Gerenciar personas/personalidades
    - Aplicar configurações de retry/fallback
    - Rotear requisições para providers específicos
    - Configurar parâmetros de geração
    """
    
    def __init__(self, config: CustomizationConfig = None):
        from ..database import get_db
        self._db = get_db()
        self._config = config
    
    @property
    def config(self) -> CustomizationConfig:
        """Obtém configuração (do cache ou carrega)."""
        if self._config is None:
            self._config = self._db.customization.load()
        return self._config
    
    def reload_config(self) -> None:
        """Recarrega configuração do disco."""
        self._config = self._db.customization.reload()
    
    def get_customization(
        self,
        context: RequestContext = None,
        persona_id: str = None
    ) -> CustomizationResult:
        """
        Obtém customizações para uma requisição.
        
        Args:
            context: Contexto da requisição
            persona_id: ID de persona específica (override)
        
        Returns:
            CustomizationResult com todas as configurações aplicadas
        """
        result = CustomizationResult()
        context = context or RequestContext()
        
        # 1. Obter persona
        persona = self._resolve_persona(persona_id, context)
        if persona:
            result.persona = persona
            result.system_prompt = self._build_system_prompt(persona)
        
        # 2. Aplicar regras de roteamento
        routing_rule = self._apply_routing_rules(context)
        if routing_rule:
            result.applied_rules.append(routing_rule.id)
            if routing_rule.force_provider_id:
                result.force_provider_id = routing_rule.force_provider_id
            if routing_rule.force_model:
                result.force_model = routing_rule.force_model
            if routing_rule.apply_persona_id:
                override_persona = self.config.get_persona(routing_rule.apply_persona_id)
                if override_persona:
                    result.persona = override_persona
                    result.system_prompt = self._build_system_prompt(override_persona)
        
        # 3. Aplicar overrides globais
        if self.config.force_provider_id and not result.force_provider_id:
            result.force_provider_id = self.config.force_provider_id
        if self.config.force_model and not result.force_model:
            result.force_model = self.config.force_model
        
        # 4. Configurar parâmetros de geração
        result.temperature = self.config.default_temperature
        result.max_tokens = self.config.default_max_tokens
        result.streaming = self.config.streaming_enabled
        
        # 5. Configurar retry
        result.retry_config = self.config.retry
        
        # 6. Provider override específico
        if context.provider_id:
            override = self.config.get_provider_override(context.provider_id)
            if override:
                if override.temperature_override is not None:
                    result.temperature = override.temperature_override
                if override.max_tokens_override is not None:
                    result.max_tokens = override.max_tokens_override
                if override.force_model:
                    result.force_model = override.force_model
        
        return result
    
    def _resolve_persona(
        self,
        persona_id: str = None,
        context: RequestContext = None
    ) -> Optional[PersonaConfig]:
        """Resolve qual persona usar."""
        # Override explícito
        if persona_id:
            persona = self.config.get_persona(persona_id)
            if persona and persona.enabled:
                return persona
        
        # Regra de roteamento
        if context:
            rule = self.config.get_matching_routing_rule(
                keywords=context.keywords,
                user_id=context.user_id
            )
            if rule and rule.apply_persona_id:
                persona = self.config.get_persona(rule.apply_persona_id)
                if persona and persona.enabled:
                    return persona
        
        # Padrão
        return self.config.get_default_persona()
    
    def _build_system_prompt(self, persona: PersonaConfig) -> str:
        """Constrói o system prompt completo baseado na persona."""
        parts = []
        
        # System prompt base
        if persona.system_prompt:
            parts.append(persona.system_prompt)
        
        # Contexto de conhecimento adicional
        if persona.knowledge_context:
            parts.append(f"\n\nContexto adicional:\n{persona.knowledge_context}")
        
        # Instruções de tom
        tone_instructions = self._get_tone_instructions(persona.tone)
        if tone_instructions:
            parts.append(f"\n\nTom de comunicação:\n{tone_instructions}")
        
        # Tópicos proibidos
        if persona.forbidden_topics:
            topics = ", ".join(persona.forbidden_topics)
            parts.append(f"\n\nNão aborde os seguintes tópicos: {topics}")
        
        # Formatação
        if persona.use_markdown:
            parts.append("\n\nUse formatação Markdown quando apropriado.")
        if persona.use_emoji:
            parts.append("Você pode usar emojis para tornar a conversa mais expressiva.")
        
        # Limite de resposta
        if persona.max_response_length:
            parts.append(f"\n\nMantenha as respostas com no máximo {persona.max_response_length} caracteres.")
        
        return "\n".join(parts)
    
    def _get_tone_instructions(self, tone: ToneType) -> str:
        """Retorna instruções de tom baseado no tipo."""
        tone_map = {
            ToneType.FORMAL: "Use linguagem formal e respeitosa. Evite gírias e coloquialismos.",
            ToneType.CASUAL: "Use linguagem casual e descontraída, mas ainda assim respeitosa.",
            ToneType.PROFESSIONAL: "Mantenha um tom profissional, objetivo e cortês.",
            ToneType.FRIENDLY: "Seja amigável e acolhedor, criando uma atmosfera de conversa.",
            ToneType.TECHNICAL: "Use terminologia técnica apropriada. Seja preciso e detalhado.",
            ToneType.EDUCATIONAL: "Explique conceitos de forma didática, como um professor paciente.",
            ToneType.CONCISE: "Seja breve e direto ao ponto. Evite explicações desnecessárias.",
            ToneType.DETAILED: "Forneça explicações completas e detalhadas. Inclua exemplos quando útil.",
        }
        return tone_map.get(tone, "")
    
    def _apply_routing_rules(self, context: RequestContext) -> Optional[RoutingRule]:
        """Aplica regras de roteamento ao contexto."""
        return self.config.get_matching_routing_rule(
            keywords=context.keywords,
            user_id=context.user_id
        )
    
    def get_retry_strategy(self) -> RetryConfig:
        """Retorna configuração de retry."""
        return self.config.retry
    
    def list_personas(self, enabled_only: bool = True) -> list[PersonaConfig]:
        """Lista todas as personas disponíveis."""
        personas = self.config.personas
        if enabled_only:
            return [p for p in personas if p.enabled]
        return personas
    
    def get_persona(self, persona_id: str) -> Optional[PersonaConfig]:
        """Obtém uma persona específica."""
        return self.config.get_persona(persona_id)
    
    def should_use_cache(self) -> bool:
        """Verifica se o cache está habilitado."""
        return self.config.cache_enabled
    
    def get_cache_ttl(self) -> int:
        """Retorna TTL do cache em segundos."""
        return self.config.cache_ttl_seconds
