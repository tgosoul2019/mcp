# ══════════════════════════════════════════════════════════════════════════════
# MCP Server — Metrics Storage
# Persistência de métricas em arquivo
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import threading
import logging

logger = logging.getLogger(__name__)


class MetricsStorage:
    """
    Armazenamento persistente de métricas.
    Salva métricas agregadas em arquivos JSON diários.
    """
    
    def __init__(self, storage_path: str | Path = None):
        self.storage_path = Path(storage_path or os.environ.get("MCP_METRICS_PATH", "db/metrics"))
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
    
    def save_daily_metrics(self, metrics: dict, date: datetime = None) -> None:
        """Salva métricas do dia."""
        date = date or datetime.utcnow()
        filename = self._get_filename(date)
        
        with self._lock:
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(metrics, f, indent=2, ensure_ascii=False, default=str)
            except IOError as e:
                logger.error("Error saving metrics: %s", e)
    
    def load_daily_metrics(self, date: datetime) -> Optional[dict]:
        """Carrega métricas de um dia específico."""
        filename = self._get_filename(date)
        
        if not filename.exists():
            return None
        
        with self._lock:
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (IOError, json.JSONDecodeError) as e:
                logger.error("Error loading metrics: %s", e)
                return None
    
    def load_range(self, start_date: datetime, end_date: datetime) -> list[dict]:
        """Carrega métricas de um período."""
        result = []
        current = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        while current <= end:
            metrics = self.load_daily_metrics(current)
            if metrics:
                metrics["date"] = current.strftime("%Y-%m-%d")
                result.append(metrics)
            current += timedelta(days=1)
        
        return result
    
    def _get_filename(self, date: datetime) -> Path:
        """Gera nome do arquivo para uma data."""
        return self.storage_path / f"metrics_{date.strftime('%Y-%m-%d')}.json"
    
    def cleanup_old_files(self, keep_days: int = 90) -> int:
        """Remove arquivos de métricas antigas."""
        cutoff = datetime.utcnow() - timedelta(days=keep_days)
        removed = 0
        
        with self._lock:
            for file in self.storage_path.glob("metrics_*.json"):
                try:
                    # Extrair data do nome do arquivo
                    date_str = file.stem.replace("metrics_", "")
                    file_date = datetime.strptime(date_str, "%Y-%m-%d")
                    
                    if file_date < cutoff:
                        file.unlink()
                        removed += 1
                except (ValueError, IOError):
                    continue
        
        return removed
    
    def get_storage_info(self) -> dict:
        """Retorna informações sobre o armazenamento."""
        files = list(self.storage_path.glob("metrics_*.json"))
        total_size = sum(f.stat().st_size for f in files)
        
        return {
            "path": str(self.storage_path),
            "file_count": len(files),
            "total_size_bytes": total_size,
            "oldest_file": min((f.name for f in files), default=None),
            "newest_file": max((f.name for f in files), default=None),
        }
