# ══════════════════════════════════════════════════════════════════════════════
# MCP Server — JSON Database Layer
# Persistência de configurações em arquivos JSON
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import TypeVar, Type, Optional, Generic
from pydantic import BaseModel
import threading
import logging

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class JSONDatabase(Generic[T]):
    """
    Banco de dados JSON simples para persistência de configurações.
    Thread-safe com lock de escrita.
    """
    
    def __init__(
        self,
        file_path: str | Path,
        model_class: Type[T],
        default_factory: callable = None,
        backup_on_write: bool = True
    ):
        self.file_path = Path(file_path)
        self.model_class = model_class
        self.default_factory = default_factory
        self.backup_on_write = backup_on_write
        self._lock = threading.RLock()
        self._cache: Optional[T] = None
        
        # Ensure directory exists
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _load_raw(self) -> dict:
        """Carrega dados brutos do arquivo."""
        if not self.file_path.exists():
            return {}
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading {self.file_path}: {e}")
            return {}
    
    def _save_raw(self, data: dict) -> None:
        """Salva dados brutos no arquivo."""
        if self.backup_on_write and self.file_path.exists():
            backup_path = self.file_path.with_suffix(
                f".{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.backup"
            )
            try:
                shutil.copy2(self.file_path, backup_path)
            except IOError as e:
                logger.warning(f"Could not create backup: {e}")
        
        # Write to temp file first, then rename (atomic)
        temp_path = self.file_path.with_suffix(".tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            temp_path.replace(self.file_path)
        except IOError as e:
            logger.error(f"Error saving {self.file_path}: {e}")
            if temp_path.exists():
                temp_path.unlink()
            raise
    
    def load(self, use_cache: bool = True) -> T:
        """Carrega a configuração do arquivo."""
        with self._lock:
            if use_cache and self._cache is not None:
                return self._cache
            
            data = self._load_raw()
            
            if not data and self.default_factory:
                self._cache = self.default_factory()
                self.save(self._cache)
            elif data:
                try:
                    self._cache = self.model_class.model_validate(data)
                except Exception as e:
                    logger.error(f"Error validating {self.file_path}: {e}")
                    if self.default_factory:
                        self._cache = self.default_factory()
                    else:
                        raise
            else:
                self._cache = self.model_class()
            
            return self._cache
    
    def save(self, config: T) -> None:
        """Salva a configuração no arquivo."""
        with self._lock:
            data = config.model_dump(mode="json")
            self._save_raw(data)
            self._cache = config
    
    def update(self, **kwargs) -> T:
        """Atualiza campos específicos da configuração."""
        with self._lock:
            config = self.load()
            updated = config.model_copy(update=kwargs)
            self.save(updated)
            return updated
    
    def reload(self) -> T:
        """Força recarregamento do arquivo."""
        with self._lock:
            self._cache = None
            return self.load(use_cache=False)
    
    def exists(self) -> bool:
        """Verifica se o arquivo existe."""
        return self.file_path.exists()
    
    def delete(self) -> bool:
        """Remove o arquivo."""
        with self._lock:
            self._cache = None
            if self.file_path.exists():
                self.file_path.unlink()
                return True
            return False
    
    def get_backups(self) -> list[Path]:
        """Lista arquivos de backup."""
        pattern = f"{self.file_path.stem}.*.backup"
        return sorted(self.file_path.parent.glob(pattern), reverse=True)
    
    def restore_backup(self, backup_path: Path) -> T:
        """Restaura um backup."""
        with self._lock:
            if not backup_path.exists():
                raise FileNotFoundError(f"Backup not found: {backup_path}")
            shutil.copy2(backup_path, self.file_path)
            return self.reload()
    
    def cleanup_backups(self, keep_last: int = 5) -> int:
        """Remove backups antigos, mantendo os últimos N."""
        backups = self.get_backups()
        removed = 0
        for backup in backups[keep_last:]:
            try:
                backup.unlink()
                removed += 1
            except IOError:
                pass
        return removed


# ══════════════════════════════════════════════════════════════════════════════
# Database Manager — Singleton para acesso às configurações
# ══════════════════════════════════════════════════════════════════════════════

class DatabaseManager:
    """Gerenciador central de bancos de dados de configuração."""
    
    _instance: Optional["DatabaseManager"] = None
    _lock = threading.Lock()
    
    def __new__(cls, db_path: str | Path = None):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self, db_path: str | Path = None):
        if self._initialized:
            return
        
        from .models.llm import LLMConfig
        from .models.security import SecurityConfig, DEFAULT_CONTENT_FILTERS, DEFAULT_SECURITY_RULES
        from .models.customization import CustomizationConfig, DEFAULT_PERSONAS
        
        self.db_path = Path(db_path or os.environ.get("MCP_DB_PATH", "db"))
        self.db_path.mkdir(parents=True, exist_ok=True)
        
        # LLM Config
        self._llm_db = JSONDatabase(
            self.db_path / "llm_config.json",
            LLMConfig,
            default_factory=lambda: LLMConfig()
        )
        
        # Security Config (Nível 1 de Memória)
        def security_default():
            return SecurityConfig(
                content_filters=DEFAULT_CONTENT_FILTERS,
                rules=DEFAULT_SECURITY_RULES
            )
        
        self._security_db = JSONDatabase(
            self.db_path / "security_config.json",
            SecurityConfig,
            default_factory=security_default
        )
        
        # Customization Config (Nível 2 de Memória)
        def customization_default():
            return CustomizationConfig(
                personas=DEFAULT_PERSONAS,
                default_persona_id="default"
            )
        
        self._customization_db = JSONDatabase(
            self.db_path / "customization_config.json",
            CustomizationConfig,
            default_factory=customization_default
        )
        
        self._initialized = True
    
    @property
    def llm(self) -> JSONDatabase[LLMConfig]:
        """Acesso ao banco de LLM configs."""
        return self._llm_db
    
    @property
    def security(self) -> JSONDatabase[SecurityConfig]:
        """Acesso ao banco de Security configs (Nível 1)."""
        return self._security_db
    
    @property
    def customization(self) -> JSONDatabase[CustomizationConfig]:
        """Acesso ao banco de Customization configs (Nível 2)."""
        return self._customization_db
    
    def reload_all(self) -> None:
        """Recarrega todas as configurações."""
        self._llm_db.reload()
        self._security_db.reload()
        self._customization_db.reload()
    
    def cleanup_all_backups(self, keep_last: int = 5) -> dict[str, int]:
        """Limpa backups de todos os bancos."""
        return {
            "llm": self._llm_db.cleanup_backups(keep_last),
            "security": self._security_db.cleanup_backups(keep_last),
            "customization": self._customization_db.cleanup_backups(keep_last),
        }


def get_db() -> DatabaseManager:
    """Obtém a instância do DatabaseManager."""
    return DatabaseManager()
