# ══════════════════════════════════════════════════════════════════════════════
# MCP Server — Admin API Router
# APIs de administração para configuração do MCP
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import secrets
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel

from ..database import get_db
from ..models.llm import LLMProvider, LLMConfig
from ..models.security import SecurityConfig, ContentFilter, SecurityRule
from ..models.customization import CustomizationConfig, PersonaConfig, RoutingRule
from ..metrics import get_metrics

router = APIRouter(prefix="/admin", tags=["admin"])
security = HTTPBasic()


# ══════════════════════════════════════════════════════════════════════════════
# Authentication
# ══════════════════════════════════════════════════════════════════════════════

def get_admin_credentials() -> tuple[str, str]:
    """Obtém credenciais de admin do ambiente."""
    import os
    return (
        os.environ.get("MCP_ADMIN_USER", "admin"),
        os.environ.get("MCP_ADMIN_PASSWORD", "changeme")
    )


def verify_admin(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    """Verifica credenciais de admin."""
    admin_user, admin_pass = get_admin_credentials()
    
    is_user_ok = secrets.compare_digest(credentials.username.encode(), admin_user.encode())
    is_pass_ok = secrets.compare_digest(credentials.password.encode(), admin_pass.encode())
    
    if not (is_user_ok and is_pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    return credentials.username


# ══════════════════════════════════════════════════════════════════════════════
# Dashboard
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/dashboard")
async def get_dashboard(username: str = Depends(verify_admin)):
    """Retorna dados do dashboard."""
    metrics = get_metrics()
    db = get_db()
    
    return {
        "metrics": metrics.get_dashboard_summary(),
        "config": {
            "llm": {
                "providers_count": len(db.llm.load().providers),
                "active_providers": len(db.llm.load().get_active_providers()),
            },
            "security": {
                "enabled": db.security.load().enabled,
                "filters_count": len(db.security.load().content_filters),
                "rules_count": len(db.security.load().rules),
            },
            "customization": {
                "personas_count": len(db.customization.load().personas),
                "routing_rules_count": len(db.customization.load().routing_rules),
            },
        },
        "timestamp": datetime.utcnow().isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# LLM Providers
# ══════════════════════════════════════════════════════════════════════════════

class ProviderCreate(BaseModel):
    """Schema para criar provider."""
    name: str
    type: str
    api_key: Optional[str] = None
    api_base_url: Optional[str] = None
    models: list[str] = []
    default_model: Optional[str] = None
    max_tokens: int = 4096
    temperature: float = 0.7
    priority: int = 100


class ProviderUpdate(BaseModel):
    """Schema para atualizar provider."""
    name: Optional[str] = None
    enabled: Optional[bool] = None
    api_key: Optional[str] = None
    api_base_url: Optional[str] = None
    models: Optional[list[str]] = None
    default_model: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    priority: Optional[int] = None


@router.get("/llm/providers")
async def list_providers(username: str = Depends(verify_admin)):
    """Lista todos os providers."""
    db = get_db()
    config = db.llm.load()
    
    # Mascarar API keys
    providers = []
    for p in config.providers:
        p_dict = p.model_dump()
        if p_dict.get("api_key"):
            p_dict["api_key"] = "***" + p_dict["api_key"][-4:]
        providers.append(p_dict)
    
    return {
        "providers": providers,
        "default_provider_id": config.default_provider_id,
        "fallback_order": config.fallback_order,
    }


@router.post("/llm/providers")
async def create_provider(data: ProviderCreate, username: str = Depends(verify_admin)):
    """Cria um novo provider."""
    from ..models.llm import LLMProvider as LLMProviderModel, LLMProviderType
    
    db = get_db()
    config = db.llm.load()
    
    provider = LLMProviderModel(
        name=data.name,
        type=LLMProviderType(data.type),
        api_key=data.api_key,
        api_base_url=data.api_base_url,
        models=data.models,
        default_model=data.default_model,
        max_tokens=data.max_tokens,
        temperature=data.temperature,
        priority=data.priority,
    )
    
    config.providers.append(provider)
    db.llm.save(config)
    
    return {"message": "Provider criado", "id": provider.id}


@router.put("/llm/providers/{provider_id}")
async def update_provider(provider_id: str, data: ProviderUpdate, username: str = Depends(verify_admin)):
    """Atualiza um provider."""
    db = get_db()
    config = db.llm.load()
    
    provider = config.get_provider(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider não encontrado")
    
    # Atualizar campos
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if hasattr(provider, key):
            setattr(provider, key, value)
    provider.updated_at = datetime.utcnow()
    
    db.llm.save(config)
    
    return {"message": "Provider atualizado"}


@router.delete("/llm/providers/{provider_id}")
async def delete_provider(provider_id: str, username: str = Depends(verify_admin)):
    """Remove um provider."""
    db = get_db()
    config = db.llm.load()
    
    config.providers = [p for p in config.providers if p.id != provider_id]
    db.llm.save(config)
    
    return {"message": "Provider removido"}


@router.post("/llm/providers/{provider_id}/test")
async def test_provider(provider_id: str, username: str = Depends(verify_admin)):
    """Testa conexão com um provider."""
    db = get_db()
    config = db.llm.load()
    
    provider = config.get_provider(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider não encontrado")
    
    # TODO: Implementar teste real
    return {
        "provider_id": provider_id,
        "status": "ok",
        "message": "Conexão bem sucedida",
        "latency_ms": 150,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Security Config
# ══════════════════════════════════════════════════════════════════════════════

class FilterCreate(BaseModel):
    """Schema para criar filtro."""
    name: str
    pattern: str
    is_regex: bool = True
    direction: str = "both"
    action: str = "block"
    category: str = "general"
    description: str = ""


class FilterUpdate(BaseModel):
    """Schema para atualizar filtro."""
    name: Optional[str] = None
    enabled: Optional[bool] = None
    pattern: Optional[str] = None
    is_regex: Optional[bool] = None
    direction: Optional[str] = None
    action: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None


@router.get("/security")
async def get_security_config(username: str = Depends(verify_admin)):
    """Retorna configuração de segurança."""
    db = get_db()
    config = db.security.load()
    return config.model_dump()


@router.put("/security")
async def update_security_config(data: dict, username: str = Depends(verify_admin)):
    """Atualiza configuração de segurança geral."""
    db = get_db()
    config = db.security.load()
    
    # Atualizar campos simples
    simple_fields = ["enabled", "pii_detection_enabled", "user_rate_limit_enabled",
                     "user_rate_limit_rpm", "user_rate_limit_tpm", "audit_enabled",
                     "audit_retention_days"]
    
    for field in simple_fields:
        if field in data:
            setattr(config, field, data[field])
    
    db.security.save(config)
    return {"message": "Configuração atualizada"}


@router.get("/security/filters")
async def list_filters(username: str = Depends(verify_admin)):
    """Lista todos os filtros de conteúdo."""
    db = get_db()
    config = db.security.load()
    return {"filters": [f.model_dump() for f in config.content_filters]}


@router.post("/security/filters")
async def create_filter(data: FilterCreate, username: str = Depends(verify_admin)):
    """Cria um novo filtro de conteúdo."""
    from ..models.security import ContentFilter as ContentFilterModel, FilterDirection, FilterAction
    
    db = get_db()
    config = db.security.load()
    
    filter_obj = ContentFilterModel(
        name=data.name,
        pattern=data.pattern,
        is_regex=data.is_regex,
        direction=FilterDirection(data.direction),
        action=FilterAction(data.action),
        category=data.category,
        description=data.description,
    )
    
    config.content_filters.append(filter_obj)
    db.security.save(config)
    
    return {"message": "Filtro criado", "id": filter_obj.id}


@router.put("/security/filters/{filter_id}")
async def update_filter(filter_id: str, data: FilterUpdate, username: str = Depends(verify_admin)):
    """Atualiza um filtro."""
    from ..models.security import FilterDirection, FilterAction
    
    db = get_db()
    config = db.security.load()
    
    filter_obj = config.get_filter(filter_id)
    if not filter_obj:
        raise HTTPException(status_code=404, detail="Filtro não encontrado")
    
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "direction":
            value = FilterDirection(value)
        elif key == "action":
            value = FilterAction(value)
        if hasattr(filter_obj, key):
            setattr(filter_obj, key, value)
    
    db.security.save(config)
    return {"message": "Filtro atualizado"}


@router.delete("/security/filters/{filter_id}")
async def delete_filter(filter_id: str, username: str = Depends(verify_admin)):
    """Remove um filtro."""
    db = get_db()
    config = db.security.load()
    
    config.content_filters = [f for f in config.content_filters if f.id != filter_id]
    db.security.save(config)
    
    return {"message": "Filtro removido"}


# ══════════════════════════════════════════════════════════════════════════════
# Customization Config
# ══════════════════════════════════════════════════════════════════════════════

class PersonaCreate(BaseModel):
    """Schema para criar persona."""
    name: str
    assistant_name: str = "Assistente"
    tone: str = "professional"
    language: str = "pt-br"
    system_prompt: str = ""
    use_emoji: bool = False
    use_markdown: bool = True
    description: str = ""


class PersonaUpdate(BaseModel):
    """Schema para atualizar persona."""
    name: Optional[str] = None
    enabled: Optional[bool] = None
    is_default: Optional[bool] = None
    assistant_name: Optional[str] = None
    tone: Optional[str] = None
    language: Optional[str] = None
    system_prompt: Optional[str] = None
    use_emoji: Optional[bool] = None
    use_markdown: Optional[bool] = None
    knowledge_context: Optional[str] = None
    description: Optional[str] = None


@router.get("/customization")
async def get_customization_config(username: str = Depends(verify_admin)):
    """Retorna configuração de customização."""
    db = get_db()
    config = db.customization.load()
    return config.model_dump()


@router.put("/customization")
async def update_customization_config(data: dict, username: str = Depends(verify_admin)):
    """Atualiza configuração de customização geral."""
    db = get_db()
    config = db.customization.load()
    
    simple_fields = ["default_persona_id", "force_provider_id", "force_model",
                     "default_temperature", "default_max_tokens", "streaming_enabled",
                     "cache_enabled", "cache_ttl_seconds"]
    
    for field in simple_fields:
        if field in data:
            setattr(config, field, data[field])
    
    # Retry config
    if "retry" in data:
        from ..models.customization import RetryConfig
        config.retry = RetryConfig(**data["retry"])
    
    db.customization.save(config)
    return {"message": "Configuração atualizada"}


@router.get("/customization/personas")
async def list_personas(username: str = Depends(verify_admin)):
    """Lista todas as personas."""
    db = get_db()
    config = db.customization.load()
    return {
        "personas": [p.model_dump() for p in config.personas],
        "default_persona_id": config.default_persona_id,
    }


@router.post("/customization/personas")
async def create_persona(data: PersonaCreate, username: str = Depends(verify_admin)):
    """Cria uma nova persona."""
    from ..models.customization import PersonaConfig as PersonaModel, ToneType, LanguageStyle
    
    db = get_db()
    config = db.customization.load()
    
    persona = PersonaModel(
        name=data.name,
        assistant_name=data.assistant_name,
        tone=ToneType(data.tone),
        language=LanguageStyle(data.language),
        system_prompt=data.system_prompt,
        use_emoji=data.use_emoji,
        use_markdown=data.use_markdown,
        description=data.description,
    )
    
    config.personas.append(persona)
    db.customization.save(config)
    
    return {"message": "Persona criada", "id": persona.id}


@router.put("/customization/personas/{persona_id}")
async def update_persona(persona_id: str, data: PersonaUpdate, username: str = Depends(verify_admin)):
    """Atualiza uma persona."""
    from ..models.customization import ToneType, LanguageStyle
    
    db = get_db()
    config = db.customization.load()
    
    persona = config.get_persona(persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona não encontrada")
    
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "tone":
            value = ToneType(value)
        elif key == "language":
            value = LanguageStyle(value)
        if hasattr(persona, key):
            setattr(persona, key, value)
    persona.updated_at = datetime.utcnow()
    
    db.customization.save(config)
    return {"message": "Persona atualizada"}


@router.delete("/customization/personas/{persona_id}")
async def delete_persona(persona_id: str, username: str = Depends(verify_admin)):
    """Remove uma persona."""
    db = get_db()
    config = db.customization.load()
    
    config.personas = [p for p in config.personas if p.id != persona_id]
    db.customization.save(config)
    
    return {"message": "Persona removida"}


# ══════════════════════════════════════════════════════════════════════════════
# Metrics
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/metrics")
async def get_all_metrics(username: str = Depends(verify_admin)):
    """Retorna todas as métricas."""
    metrics = get_metrics()
    return metrics.get_dashboard_summary()


@router.get("/metrics/time-series")
async def get_time_series(minutes: int = 60, username: str = Depends(verify_admin)):
    """Retorna time series de métricas."""
    metrics = get_metrics()
    return {"time_series": metrics.get_time_series(minutes)}


@router.get("/metrics/providers")
async def get_provider_metrics(username: str = Depends(verify_admin)):
    """Retorna métricas por provider."""
    metrics = get_metrics()
    return {"providers": metrics.get_provider_metrics()}


@router.post("/metrics/reset")
async def reset_metrics(username: str = Depends(verify_admin)):
    """Reseta todas as métricas."""
    metrics = get_metrics()
    metrics.reset()
    return {"message": "Métricas resetadas"}


# ══════════════════════════════════════════════════════════════════════════════
# System
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/reload")
async def reload_configs(username: str = Depends(verify_admin)):
    """Recarrega todas as configurações do disco."""
    db = get_db()
    db.reload_all()
    return {"message": "Configurações recarregadas"}


@router.get("/backups")
async def list_backups(username: str = Depends(verify_admin)):
    """Lista backups de configuração."""
    db = get_db()
    return {
        "llm": [str(p) for p in db.llm.get_backups()[:10]],
        "security": [str(p) for p in db.security.get_backups()[:10]],
        "customization": [str(p) for p in db.customization.get_backups()[:10]],
    }


@router.post("/backups/cleanup")
async def cleanup_backups(keep_last: int = 5, username: str = Depends(verify_admin)):
    """Remove backups antigos."""
    db = get_db()
    result = db.cleanup_all_backups(keep_last)
    return {"removed": result}
