"""Pydantic models for cost data and statistics."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CostRecord(BaseModel):
    """Modelo para um registro de custo individual."""

    id: Optional[int] = None
    date: Optional[date] = None
    provider: Optional[str] = Field(None, description="AWS, AZURE, OCI, GCP")
    account_id: Optional[str] = None
    service: Optional[str] = None
    usage_type: Optional[str] = None
    region: Optional[str] = None
    project: Optional[str] = Field(None, description="Business unit ou projeto")
    tags: Optional[Dict[str, str]] = None
    cost_amount: float = Field(0.0, description="Valor do custo")
    currency: str = Field("USD", description="Moeda")

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat() if v else None,
            datetime: lambda v: v.isoformat() if v else None,
        }


class ServiceStats(BaseModel):
    """Estatísticas agregadas por serviço."""

    service: str
    total_cost: float
    average_cost: float
    max_cost: float
    min_cost: float
    percentage: float = Field(0.0, description="Percentual do total")
    record_count: int = 0


class KPISummary(BaseModel):
    """Resumo de KPIs globais."""

    total_cost: float
    average_cost: float
    max_cost: float
    min_cost: float
    peak_month: Optional[str] = None
    lowest_month: Optional[str] = None
    peak_service: Optional[str] = None
    lowest_service: Optional[str] = None


class ForecastResult(BaseModel):
    """Resultado de previsão de custos."""

    date: date
    service: Optional[str] = None
    cost_forecast: float
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None


class AnomalyDetection(BaseModel):
    """Detecção de anomalia em custos."""

    date: date
    service: str
    cost: float
    is_anomaly: bool
    anomaly_score: Optional[float] = None
    explanation: Optional[str] = None


class Recommendation(BaseModel):
    """Recomendação de otimização FinOps."""

    title: str
    impact: str = Field(..., description="alto, medio, baixo")
    estimated_saving_percent: float = Field(0.0, ge=0, le=100)
    description: str
    service: Optional[str] = None
    category: Optional[str] = Field(None, description="reserved_instances, storage_optimization, etc.")


class ChatResponse(BaseModel):
    """Resposta do chat NLQ."""

    answer_text: str
    dataframe: Optional[List[Dict[str, Any]]] = None  # Lista de dicionários (JSON serializable)
    chart_spec: Optional[Dict[str, Any]] = None


