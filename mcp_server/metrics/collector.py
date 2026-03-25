# ══════════════════════════════════════════════════════════════════════════════
# MCP Server — Metrics Collector
# Coleta métricas de requests e providers
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass, field
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class RequestMetrics:
    """Métricas de uma única requisição."""
    request_id: str
    timestamp: datetime
    provider_id: str
    model: str
    
    # Tokens
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    
    # Bytes
    request_bytes: int = 0
    response_bytes: int = 0
    
    # Tempo
    latency_ms: float = 0
    time_to_first_token_ms: float = 0
    
    # Status
    success: bool = True
    error_type: Optional[str] = None
    status_code: int = 200
    
    # Metadados
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    is_streaming: bool = False
    is_fallback: bool = False
    retry_count: int = 0


@dataclass
class ProviderMetrics:
    """Métricas agregadas de um provider."""
    provider_id: str
    provider_name: str
    
    # Contadores
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    
    # Tokens
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    
    # Bytes
    total_request_bytes: int = 0
    total_response_bytes: int = 0
    
    # Latência
    avg_latency_ms: float = 0
    min_latency_ms: float = float('inf')
    max_latency_ms: float = 0
    p50_latency_ms: float = 0
    p95_latency_ms: float = 0
    p99_latency_ms: float = 0
    
    # TTFT (Time to First Token)
    avg_ttft_ms: float = 0
    
    # Taxa de erro
    error_rate: float = 0
    
    # Última atualização
    last_request_at: Optional[datetime] = None
    
    # Latências para cálculo de percentis
    _latencies: list[float] = field(default_factory=list)


@dataclass
class TimeWindowMetrics:
    """Métricas para uma janela de tempo."""
    window_start: datetime
    window_end: datetime
    window_size_minutes: int
    
    # Totais
    total_requests: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_request_bytes: int = 0
    total_response_bytes: int = 0
    
    # Por provider
    by_provider: dict[str, ProviderMetrics] = field(default_factory=dict)
    
    # Por modelo
    by_model: dict[str, dict] = field(default_factory=dict)
    
    # Erros
    total_errors: int = 0
    errors_by_type: dict[str, int] = field(default_factory=dict)


class MetricsCollector:
    """
    Coletor central de métricas.
    Thread-safe com locks para contadores.
    """
    
    _instance: Optional["MetricsCollector"] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._data_lock = threading.RLock()
        
        # Contadores globais
        self._total_requests = 0
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_request_bytes = 0
        self._total_response_bytes = 0
        self._total_errors = 0
        
        # Por provider
        self._provider_metrics: dict[str, ProviderMetrics] = {}
        
        # Por modelo
        self._model_metrics: dict[str, dict] = defaultdict(lambda: {
            "requests": 0,
            "input_tokens": 0,
            "output_tokens": 0,
        })
        
        # Histórico de requests (últimas N horas)
        self._request_history: list[RequestMetrics] = []
        self._history_max_age_hours = 24
        
        # Time series (por minuto)
        self._time_series: dict[str, dict] = defaultdict(lambda: {
            "requests": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "errors": 0,
        })
        
        # Início da coleta
        self._start_time = datetime.utcnow()
        
        self._initialized = True
    
    def record_request(self, metrics: RequestMetrics) -> None:
        """Registra métricas de uma requisição."""
        with self._data_lock:
            # Globais
            self._total_requests += 1
            self._total_input_tokens += metrics.input_tokens
            self._total_output_tokens += metrics.output_tokens
            self._total_request_bytes += metrics.request_bytes
            self._total_response_bytes += metrics.response_bytes
            
            if not metrics.success:
                self._total_errors += 1
            
            # Por provider
            self._update_provider_metrics(metrics)
            
            # Por modelo
            self._model_metrics[metrics.model]["requests"] += 1
            self._model_metrics[metrics.model]["input_tokens"] += metrics.input_tokens
            self._model_metrics[metrics.model]["output_tokens"] += metrics.output_tokens
            
            # Histórico
            self._request_history.append(metrics)
            self._cleanup_history()
            
            # Time series
            ts_key = metrics.timestamp.strftime("%Y-%m-%d %H:%M")
            self._time_series[ts_key]["requests"] += 1
            self._time_series[ts_key]["input_tokens"] += metrics.input_tokens
            self._time_series[ts_key]["output_tokens"] += metrics.output_tokens
            if not metrics.success:
                self._time_series[ts_key]["errors"] += 1
    
    def _update_provider_metrics(self, req: RequestMetrics) -> None:
        """Atualiza métricas de um provider."""
        pid = req.provider_id
        
        if pid not in self._provider_metrics:
            self._provider_metrics[pid] = ProviderMetrics(
                provider_id=pid,
                provider_name=pid
            )
        
        pm = self._provider_metrics[pid]
        pm.total_requests += 1
        pm.total_input_tokens += req.input_tokens
        pm.total_output_tokens += req.output_tokens
        pm.total_request_bytes += req.request_bytes
        pm.total_response_bytes += req.response_bytes
        pm.last_request_at = req.timestamp
        
        if req.success:
            pm.successful_requests += 1
        else:
            pm.failed_requests += 1
        
        # Latência
        pm._latencies.append(req.latency_ms)
        if len(pm._latencies) > 1000:
            pm._latencies = pm._latencies[-1000:]
        
        pm.min_latency_ms = min(pm.min_latency_ms, req.latency_ms)
        pm.max_latency_ms = max(pm.max_latency_ms, req.latency_ms)
        pm.avg_latency_ms = sum(pm._latencies) / len(pm._latencies)
        
        # Percentis
        sorted_latencies = sorted(pm._latencies)
        n = len(sorted_latencies)
        pm.p50_latency_ms = sorted_latencies[int(n * 0.5)]
        pm.p95_latency_ms = sorted_latencies[int(n * 0.95)]
        pm.p99_latency_ms = sorted_latencies[min(int(n * 0.99), n - 1)]
        
        # TTFT
        if req.time_to_first_token_ms > 0:
            # Média móvel simples
            pm.avg_ttft_ms = (pm.avg_ttft_ms * 0.9) + (req.time_to_first_token_ms * 0.1)
        
        # Taxa de erro
        pm.error_rate = pm.failed_requests / pm.total_requests if pm.total_requests > 0 else 0
    
    def _cleanup_history(self) -> None:
        """Remove entradas antigas do histórico."""
        cutoff = datetime.utcnow() - timedelta(hours=self._history_max_age_hours)
        self._request_history = [
            r for r in self._request_history
            if r.timestamp > cutoff
        ]
    
    def get_global_metrics(self) -> dict:
        """Retorna métricas globais."""
        with self._data_lock:
            uptime = (datetime.utcnow() - self._start_time).total_seconds()
            return {
                "uptime_seconds": uptime,
                "total_requests": self._total_requests,
                "total_input_tokens": self._total_input_tokens,
                "total_output_tokens": self._total_output_tokens,
                "total_tokens": self._total_input_tokens + self._total_output_tokens,
                "total_request_bytes": self._total_request_bytes,
                "total_response_bytes": self._total_response_bytes,
                "total_bytes": self._total_request_bytes + self._total_response_bytes,
                "total_errors": self._total_errors,
                "error_rate": self._total_errors / self._total_requests if self._total_requests > 0 else 0,
                "requests_per_minute": (self._total_requests / uptime * 60) if uptime > 0 else 0,
                "tokens_per_minute": ((self._total_input_tokens + self._total_output_tokens) / uptime * 60) if uptime > 0 else 0,
            }
    
    def get_provider_metrics(self, provider_id: str = None) -> dict | list[dict]:
        """Retorna métricas de providers."""
        with self._data_lock:
            if provider_id:
                pm = self._provider_metrics.get(provider_id)
                if pm:
                    return self._provider_to_dict(pm)
                return {}
            
            return [self._provider_to_dict(pm) for pm in self._provider_metrics.values()]
    
    def _provider_to_dict(self, pm: ProviderMetrics) -> dict:
        """Converte ProviderMetrics para dict."""
        return {
            "provider_id": pm.provider_id,
            "provider_name": pm.provider_name,
            "total_requests": pm.total_requests,
            "successful_requests": pm.successful_requests,
            "failed_requests": pm.failed_requests,
            "total_input_tokens": pm.total_input_tokens,
            "total_output_tokens": pm.total_output_tokens,
            "total_tokens": pm.total_input_tokens + pm.total_output_tokens,
            "total_request_bytes": pm.total_request_bytes,
            "total_response_bytes": pm.total_response_bytes,
            "avg_latency_ms": round(pm.avg_latency_ms, 2),
            "min_latency_ms": round(pm.min_latency_ms, 2) if pm.min_latency_ms != float('inf') else 0,
            "max_latency_ms": round(pm.max_latency_ms, 2),
            "p50_latency_ms": round(pm.p50_latency_ms, 2),
            "p95_latency_ms": round(pm.p95_latency_ms, 2),
            "p99_latency_ms": round(pm.p99_latency_ms, 2),
            "avg_ttft_ms": round(pm.avg_ttft_ms, 2),
            "error_rate": round(pm.error_rate * 100, 2),
            "last_request_at": pm.last_request_at.isoformat() if pm.last_request_at else None,
        }
    
    def get_model_metrics(self) -> dict:
        """Retorna métricas por modelo."""
        with self._data_lock:
            return dict(self._model_metrics)
    
    def get_time_series(
        self,
        minutes: int = 60,
        resolution_minutes: int = 1
    ) -> list[dict]:
        """
        Retorna time series de métricas.
        
        Args:
            minutes: Últimos N minutos
            resolution_minutes: Resolução em minutos
        """
        with self._data_lock:
            now = datetime.utcnow()
            start = now - timedelta(minutes=minutes)
            
            result = []
            current = start.replace(second=0, microsecond=0)
            
            while current <= now:
                key = current.strftime("%Y-%m-%d %H:%M")
                data = self._time_series.get(key, {
                    "requests": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "errors": 0,
                })
                result.append({
                    "timestamp": current.isoformat(),
                    **data
                })
                current += timedelta(minutes=resolution_minutes)
            
            return result
    
    def get_recent_requests(self, limit: int = 100) -> list[dict]:
        """Retorna últimas N requisições."""
        with self._data_lock:
            recent = self._request_history[-limit:]
            return [
                {
                    "request_id": r.request_id,
                    "timestamp": r.timestamp.isoformat(),
                    "provider_id": r.provider_id,
                    "model": r.model,
                    "input_tokens": r.input_tokens,
                    "output_tokens": r.output_tokens,
                    "latency_ms": round(r.latency_ms, 2),
                    "success": r.success,
                    "error_type": r.error_type,
                    "is_streaming": r.is_streaming,
                }
                for r in reversed(recent)
            ]
    
    def get_dashboard_summary(self) -> dict:
        """Retorna resumo para dashboard."""
        with self._data_lock:
            global_m = self.get_global_metrics()
            providers = self.get_provider_metrics()
            models = self.get_model_metrics()
            
            # Últimos 60 minutos
            ts_60m = self.get_time_series(minutes=60)
            
            # Últimas 24 horas (resolução de 1h)
            ts_24h = []
            now = datetime.utcnow()
            for h in range(24):
                hour = now - timedelta(hours=h)
                hour_key = hour.strftime("%Y-%m-%d %H")
                # Agregar minutos dessa hora
                hour_data = {"requests": 0, "input_tokens": 0, "output_tokens": 0, "errors": 0}
                for m in range(60):
                    minute_key = f"{hour_key}:{m:02d}"
                    if minute_key in self._time_series:
                        for k, v in self._time_series[minute_key].items():
                            hour_data[k] += v
                ts_24h.append({
                    "timestamp": hour.replace(minute=0, second=0).isoformat(),
                    **hour_data
                })
            
            return {
                "global": global_m,
                "providers": providers,
                "models": models,
                "time_series_60m": ts_60m,
                "time_series_24h": list(reversed(ts_24h)),
                "recent_requests": self.get_recent_requests(20),
            }
    
    def reset(self) -> None:
        """Reseta todas as métricas."""
        with self._data_lock:
            self._total_requests = 0
            self._total_input_tokens = 0
            self._total_output_tokens = 0
            self._total_request_bytes = 0
            self._total_response_bytes = 0
            self._total_errors = 0
            self._provider_metrics.clear()
            self._model_metrics.clear()
            self._request_history.clear()
            self._time_series.clear()
            self._start_time = datetime.utcnow()


def get_metrics() -> MetricsCollector:
    """Obtém instância do coletor de métricas."""
    return MetricsCollector()
