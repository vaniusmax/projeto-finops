"""Repositórios para consultas e agregações de dados."""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional, Tuple

import pandas as pd

from app.models.cost_model import (
    DATE_COLUMN,
    TOTAL_COLUMN,
    aggregate_monthly_totals,
    aggregate_service_totals,
    build_highlights,
    build_rankings,
    build_service_percentages,
    calculate_overall_metrics,
    get_service_columns,
)


def filter_dataframe(
    df: pd.DataFrame,
    date_range: Optional[Tuple[date, date]] = None,
    services: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Filtra DataFrame por período e serviços.

    Args:
        df: DataFrame de custos
        date_range: Tupla (data_inicial, data_final)
        services: Lista de serviços para incluir

    Returns:
        DataFrame filtrado
    """
    filtered_df = df.copy()

    # Filtro por data
    if date_range and DATE_COLUMN in filtered_df.columns:
        start, end = date_range
        if start:
            filtered_df = filtered_df[filtered_df[DATE_COLUMN] >= pd.to_datetime(start)]
        if end:
            filtered_df = filtered_df[filtered_df[DATE_COLUMN] <= pd.to_datetime(end)]

    # Filtro por serviços
    if services:
        service_columns = [col for col in services if col in filtered_df.columns]
        if service_columns:
            # Manter apenas colunas de data, total e serviços selecionados
            columns_to_keep = [DATE_COLUMN] if DATE_COLUMN in filtered_df.columns else []
            columns_to_keep.extend(service_columns)
            if TOTAL_COLUMN in filtered_df.columns:
                columns_to_keep.append(TOTAL_COLUMN)
            filtered_df = filtered_df[columns_to_keep]
    else:
        # Se nenhum serviço for informado, manter apenas colunas relevantes
        columns_to_keep = [DATE_COLUMN] + get_service_columns(filtered_df)
        if TOTAL_COLUMN in filtered_df.columns:
            columns_to_keep.append(TOTAL_COLUMN)
        filtered_df = filtered_df[[col for col in columns_to_keep if col in filtered_df.columns]]

    return filtered_df


def get_service_totals(df: pd.DataFrame, services: Optional[List[str]] = None) -> pd.Series:
    """
    Retorna totais agregados por serviço.

    Args:
        df: DataFrame de custos
        services: Lista de serviços (None = todos)

    Returns:
        Series com totais por serviço
    """
    return aggregate_service_totals(df, services)


def get_percentual_distribution(df: pd.DataFrame, services: Optional[List[str]] = None) -> pd.DataFrame:
    """
    Retorna distribuição percentual por serviço.

    Args:
        df: DataFrame de custos
        services: Lista de serviços (None = todos)

    Returns:
        DataFrame com colunas: Serviço, Custo, Percentual
    """
    service_totals = get_service_totals(df, services)
    return build_service_percentages(service_totals)


def get_cost_ranking(df: pd.DataFrame, services: Optional[List[str]] = None, top_n: int = 10) -> pd.DataFrame:
    """
    Retorna ranking de custos por serviço.

    Args:
        df: DataFrame de custos
        services: Lista de serviços (None = todos)
        top_n: Número de itens no ranking

    Returns:
        DataFrame com colunas: Serviço, Custo
    """
    service_totals = get_service_totals(df, services)
    return build_rankings(service_totals, top_n=top_n)


def get_monthly_totals(df: pd.DataFrame, services: Optional[List[str]] = None) -> pd.DataFrame:
    """
    Retorna totais agregados por mês.

    Args:
        df: DataFrame de custos
        services: Lista de serviços para agregar (None = usa TOTAL_COLUMN)

    Returns:
        DataFrame com colunas: Competência, [serviços...]
    """
    if services:
        return aggregate_monthly_totals(df, services=services)
    else:
        return aggregate_monthly_totals(df, services=[TOTAL_COLUMN])


def get_overall_metrics(df: pd.DataFrame) -> dict:
    """
    Retorna métricas globais (total, média, máximo, mínimo).

    Args:
        df: DataFrame de custos

    Returns:
        Dict com métricas: total, average, max, min
    """
    return calculate_overall_metrics(df)


def get_highlights(df: pd.DataFrame, services: Optional[List[str]] = None) -> dict:
    """
    Retorna destaques (maior/menor serviço, maior/menor mês).

    Args:
        df: DataFrame de custos
        services: Lista de serviços (None = todos)

    Returns:
        Dict com: maior_servico, menor_servico, maior_mes, menor_mes
    """
    service_totals = get_service_totals(df, services)
    monthly_totals = get_monthly_totals(df, services)
    return build_highlights(service_totals, monthly_totals)

