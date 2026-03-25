# ══════════════════════════════════════════════════════════════════════════════
# MCP Server — Security Memory (Nível 1)
# Responsável por filtrar e validar conteúdo antes de enviar para LLMs
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import re
import logging
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime

from ..models.security import (
    SecurityConfig,
    SecurityRule,
    ContentFilter,
    FilterAction,
    FilterDirection,
)

logger = logging.getLogger(__name__)


@dataclass
class FilterMatch:
    """Resultado de um match de filtro."""
    filter_id: str
    filter_name: str
    pattern: str
    matched_text: str
    action: FilterAction
    position: tuple[int, int]  # start, end
    category: str


@dataclass
class SecurityCheckResult:
    """Resultado de uma verificação de segurança."""
    allowed: bool = True
    filtered_content: Optional[str] = None
    matches: list[FilterMatch] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blocked_reason: Optional[str] = None
    applied_rules: list[str] = field(default_factory=list)
    processing_time_ms: float = 0


class SecurityMemory:
    """
    Nível 1 de Memória: Segurança
    
    Responsabilidades:
    - Filtrar conteúdo sensível (PII, secrets, etc)
    - Aplicar regras de segurança
    - Validar limites de tokens
    - Registrar auditoria
    """
    
    def __init__(self, config: SecurityConfig = None):
        from ..database import get_db
        self._db = get_db()
        self._config = config
    
    @property
    def config(self) -> SecurityConfig:
        """Obtém configuração (do cache ou carrega)."""
        if self._config is None:
            self._config = self._db.security.load()
        return self._config
    
    def reload_config(self) -> None:
        """Recarrega configuração do disco."""
        self._config = self._db.security.reload()
    
    def check_input(
        self,
        content: str,
        provider_id: str = None,
        model: str = None,
        user_id: str = None
    ) -> SecurityCheckResult:
        """
        Verifica e filtra conteúdo de entrada (do usuário).
        
        Args:
            content: Texto a ser verificado
            provider_id: ID do provider (para regras específicas)
            model: Nome do modelo (para regras específicas)
            user_id: ID do usuário (para rate limiting)
        
        Returns:
            SecurityCheckResult com status e conteúdo filtrado
        """
        start_time = datetime.utcnow()
        
        if not self.config.enabled:
            return SecurityCheckResult(
                allowed=True,
                filtered_content=content
            )
        
        result = SecurityCheckResult(allowed=True, filtered_content=content)
        
        # Aplicar filtros de conteúdo
        result = self._apply_content_filters(
            result, 
            FilterDirection.INPUT,
            provider_id,
            model
        )
        
        # Aplicar regras de segurança
        result = self._apply_security_rules(
            result,
            provider_id,
            model
        )
        
        # Calcular tempo de processamento
        result.processing_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return result
    
    def check_output(
        self,
        content: str,
        provider_id: str = None,
        model: str = None
    ) -> SecurityCheckResult:
        """
        Verifica e filtra conteúdo de saída (da LLM).
        
        Args:
            content: Texto de resposta da LLM
            provider_id: ID do provider
            model: Nome do modelo
        
        Returns:
            SecurityCheckResult com status e conteúdo filtrado
        """
        start_time = datetime.utcnow()
        
        if not self.config.enabled:
            return SecurityCheckResult(
                allowed=True,
                filtered_content=content
            )
        
        result = SecurityCheckResult(allowed=True, filtered_content=content)
        
        # Aplicar filtros de conteúdo para saída
        result = self._apply_content_filters(
            result,
            FilterDirection.OUTPUT,
            provider_id,
            model
        )
        
        result.processing_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return result
    
    def _apply_content_filters(
        self,
        result: SecurityCheckResult,
        direction: FilterDirection,
        provider_id: str = None,
        model: str = None
    ) -> SecurityCheckResult:
        """Aplica filtros de conteúdo ao resultado."""
        
        filters = self.config.get_active_filters(direction)
        content = result.filtered_content
        
        for f in filters:
            matches = self._find_matches(content, f)
            
            for match in matches:
                result.matches.append(match)
                
                if match.action == FilterAction.BLOCK:
                    result.allowed = False
                    result.blocked_reason = f"Conteúdo bloqueado pelo filtro '{f.name}': {match.matched_text[:50]}..."
                    logger.warning(
                        "Content blocked by filter %s: %s",
                        f.name, match.matched_text[:50]
                    )
                    return result
                
                elif match.action == FilterAction.REDACT:
                    # Substituir conteúdo
                    replacement = f.replacement or "[REDACTED]"
                    content = content[:match.position[0]] + replacement + content[match.position[1]:]
                    result.filtered_content = content
                    logger.info(
                        "Content redacted by filter %s",
                        f.name
                    )
                
                elif match.action == FilterAction.WARN:
                    result.warnings.append(
                        f"Alerta do filtro '{f.name}': conteúdo detectado - {match.category}"
                    )
                    logger.info(
                        "Content warning from filter %s: %s",
                        f.name, match.matched_text[:50]
                    )
        
        return result
    
    def _apply_security_rules(
        self,
        result: SecurityCheckResult,
        provider_id: str = None,
        model: str = None
    ) -> SecurityCheckResult:
        """Aplica regras de segurança ao resultado."""
        
        rules = self.config.get_active_rules()
        
        for rule in rules:
            # Verificar se a regra se aplica ao provider/model
            if rule.applies_to_providers and provider_id:
                if provider_id not in rule.applies_to_providers:
                    continue
            
            if rule.applies_to_models and model:
                if model not in rule.applies_to_models:
                    continue
            
            result.applied_rules.append(rule.id)
            
            # Verificar limite de tokens de entrada
            if rule.max_input_tokens:
                # Estimativa simples: ~4 chars por token
                estimated_tokens = len(result.filtered_content) // 4
                if estimated_tokens > rule.max_input_tokens:
                    result.allowed = False
                    result.blocked_reason = f"Excede limite de tokens de entrada ({rule.max_input_tokens})"
                    return result
            
            # Verificar tópicos bloqueados
            if rule.blocked_topics:
                content_lower = result.filtered_content.lower()
                for topic in rule.blocked_topics:
                    if topic.lower() in content_lower:
                        result.allowed = False
                        result.blocked_reason = f"Tópico bloqueado: {topic}"
                        return result
        
        return result
    
    def _find_matches(self, content: str, filter_config: ContentFilter) -> list[FilterMatch]:
        """Encontra matches de um filtro no conteúdo."""
        matches = []
        
        try:
            if filter_config.is_regex:
                flags = 0 if filter_config.case_sensitive else re.IGNORECASE
                pattern = re.compile(filter_config.pattern, flags)
                
                for m in pattern.finditer(content):
                    matches.append(FilterMatch(
                        filter_id=filter_config.id,
                        filter_name=filter_config.name,
                        pattern=filter_config.pattern,
                        matched_text=m.group(),
                        action=filter_config.action,
                        position=(m.start(), m.end()),
                        category=filter_config.category
                    ))
            else:
                # Busca simples de string
                search_content = content if filter_config.case_sensitive else content.lower()
                search_pattern = filter_config.pattern if filter_config.case_sensitive else filter_config.pattern.lower()
                
                start = 0
                while True:
                    pos = search_content.find(search_pattern, start)
                    if pos == -1:
                        break
                    
                    matches.append(FilterMatch(
                        filter_id=filter_config.id,
                        filter_name=filter_config.name,
                        pattern=filter_config.pattern,
                        matched_text=content[pos:pos + len(filter_config.pattern)],
                        action=filter_config.action,
                        position=(pos, pos + len(filter_config.pattern)),
                        category=filter_config.category
                    ))
                    start = pos + 1
        
        except re.error as e:
            logger.error("Invalid regex pattern in filter %s: %s", filter_config.id, e)
        
        return matches
    
    def get_system_prompt_modifications(
        self,
        provider_id: str = None,
        model: str = None
    ) -> tuple[str, str]:
        """
        Retorna modificações de system prompt (prefix, suffix).
        
        Returns:
            Tuple de (prefix, suffix) para adicionar ao system prompt
        """
        prefix_parts = []
        suffix_parts = []
        
        for rule in self.config.get_active_rules():
            # Verificar se a regra se aplica
            if rule.applies_to_providers and provider_id:
                if provider_id not in rule.applies_to_providers:
                    continue
            
            if rule.applies_to_models and model:
                if model not in rule.applies_to_models:
                    continue
            
            if rule.system_prompt_prefix:
                prefix_parts.append(rule.system_prompt_prefix)
            
            if rule.system_prompt_suffix:
                suffix_parts.append(rule.system_prompt_suffix)
        
        return "\n".join(prefix_parts), "\n".join(suffix_parts)
    
    def validate_token_limits(
        self,
        input_tokens: int,
        max_output_tokens: int,
        provider_id: str = None,
        model: str = None
    ) -> tuple[bool, str]:
        """
        Valida limites de tokens.
        
        Returns:
            Tuple de (is_valid, error_message)
        """
        for rule in self.config.get_active_rules():
            if rule.applies_to_providers and provider_id:
                if provider_id not in rule.applies_to_providers:
                    continue
            
            if rule.applies_to_models and model:
                if model not in rule.applies_to_models:
                    continue
            
            if rule.max_input_tokens and input_tokens > rule.max_input_tokens:
                return False, f"Entrada excede limite de {rule.max_input_tokens} tokens"
            
            if rule.max_output_tokens and max_output_tokens > rule.max_output_tokens:
                return False, f"Saída solicitada excede limite de {rule.max_output_tokens} tokens"
        
        return True, ""
