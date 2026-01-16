"""Serviço de análises básicas: KPIs, rankings, distribuições."""
from __future__ import annotations

from typing import List, Optional

import pandas as pd

from app.data.schemas import KPISummary, ServiceStats
from app.data.repositories import (
    get_cost_ranking,
    get_highlights,
    get_monthly_totals,
    get_overall_metrics,
    get_percentual_distribution,
    get_service_totals,
)


def get_cost_ranking_by_service(
    df: pd.DataFrame, services: Optional[List[str]] = None, top_n: int = 10
) -> pd.DataFrame:
    """
    Retorna ranking de custos por serviço.

    Args:
        df: DataFrame de custos
        services: Lista de serviços (None = todos)
        top_n: Número de itens no ranking

    Returns:
        DataFrame com colunas: Serviço, Custo
    """
    return get_cost_ranking(df, services, top_n)


def get_percentual_distribution_by_service(
    df: pd.DataFrame, services: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Retorna distribuição percentual por serviço.

    Args:
        df: DataFrame de custos
        services: Lista de serviços (None = todos)

    Returns:
        DataFrame com colunas: Serviço, Custo, Percentual
    """
    return get_percentual_distribution(df, services)


def get_kpi_summary(df: pd.DataFrame, services: Optional[List[str]] = None) -> KPISummary:
    """
    Retorna resumo completo de KPIs.

    Args:
        df: DataFrame de custos
        services: Lista de serviços (None = todos)

    Returns:
        KPISummary com todas as métricas
    """
    metrics = get_overall_metrics(df)
    highlights = get_highlights(df, services)

    return KPISummary(
        total_cost=metrics.get("total", 0.0),
        average_cost=metrics.get("average", 0.0),
        max_cost=metrics.get("max", 0.0),
        min_cost=metrics.get("min", 0.0),
        peak_month=highlights.get("maior_mes"),
        lowest_month=highlights.get("menor_mes"),
        peak_service=highlights.get("maior_servico"),
        lowest_service=highlights.get("menor_servico"),
    )


def get_service_stats(df: pd.DataFrame, services: Optional[List[str]] = None) -> List[ServiceStats]:
    """
    Retorna estatísticas detalhadas por serviço.

    Args:
        df: DataFrame de custos
        services: Lista de serviços (None = todos)

    Returns:
        Lista de ServiceStats
    """
    service_totals = get_service_totals(df, services)
    total = service_totals.sum()

    stats = []
    for service, cost in service_totals.items():
        if service not in df.columns:
            continue
        service_df = df[[service]]
        stats.append(
            ServiceStats(
                service=service,
                total_cost=float(cost),
                average_cost=float(service_df[service].mean()) if service in service_df.columns else 0.0,
                max_cost=float(service_df[service].max()) if service in service_df.columns else 0.0,
                min_cost=float(service_df[service].min()) if service in service_df.columns else 0.0,
                percentage=float((cost / total * 100)) if total > 0 else 0.0,
                record_count=len(service_df),
            )
        )

    return stats


def get_monthly_evolution(df: pd.DataFrame, services: Optional[List[str]] = None) -> pd.DataFrame:
    """
    Retorna evolução mensal de custos.

    Args:
        df: DataFrame de custos
        services: Lista de serviços (None = usa TOTAL_COLUMN)

    Returns:
        DataFrame com colunas: Competência, [serviços...]
    """
    return get_monthly_totals(df, services)
