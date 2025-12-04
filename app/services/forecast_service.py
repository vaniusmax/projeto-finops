"""Serviço de previsão de custos usando regressão linear e estatísticas básicas."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from app.data.models import ForecastResult
from app.infra.cache import cached
from app.models.cost_model import DATE_COLUMN, TOTAL_COLUMN


@dataclass
class ForecastStats:
    """Estatísticas básicas para o forecast."""

    mean_cost: float
    std_cost: float
    min_cost: float
    max_cost: float
    lower_bound: float
    upper_bound: float


@cached
def compute_stats(df: pd.DataFrame) -> Optional[ForecastStats]:
    """
    Calcula estatísticas básicas do histórico.

    Args:
        df: DataFrame com colunas 'date' e 'cost'

    Returns:
        ForecastStats ou None se dados insuficientes
    """
    if df.empty or "cost" not in df.columns:
        return None

    mean_cost = float(df["cost"].mean())
    std_cost = float(df["cost"].std())
    min_cost = float(df["cost"].min())
    max_cost = float(df["cost"].max())

    # Intervalo de confiança: mean ± 2*std
    lower_bound = max(mean_cost - 2 * std_cost, 0)
    upper_bound = mean_cost + 2 * std_cost

    return ForecastStats(
        mean_cost=mean_cost,
        std_cost=std_cost,
        min_cost=min_cost,
        max_cost=max_cost,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
    )


def calculate_monthly_totals(cost_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula o total mensal de custos, filtrando apenas meses válidos.

    Args:
        cost_df: DataFrame de custos

    Returns:
        DataFrame com colunas: date, cost
    """
    if DATE_COLUMN not in cost_df.columns:
        return pd.DataFrame()

    # Converter coluna de data
    cost_df = cost_df.copy()
    cost_df[DATE_COLUMN] = pd.to_datetime(cost_df[DATE_COLUMN], errors="coerce")
    cost_df = cost_df.dropna(subset=[DATE_COLUMN])

    if cost_df.empty:
        return pd.DataFrame()

    # Filtrar apenas linhas que sejam meses válidos (ignorar totais, etc)
    # Assumir que linhas válidas têm data válida e custo numérico
    if TOTAL_COLUMN in cost_df.columns:
        # Filtrar linhas com valores válidos e positivos
        cost_df = cost_df[cost_df[TOTAL_COLUMN].notna()]
        cost_df = cost_df[cost_df[TOTAL_COLUMN] > 0]  # Ignorar zeros
        if cost_df.empty:
            return pd.DataFrame()
        monthly = cost_df.groupby(cost_df[DATE_COLUMN].dt.to_period("M"))[TOTAL_COLUMN].sum().reset_index()
    else:
        # Somar todas as colunas numéricas
        numeric_cols = cost_df.select_dtypes(include=["number"]).columns
        if len(numeric_cols) == 0:
            return pd.DataFrame()
        # Filtrar linhas com pelo menos um valor numérico positivo
        cost_df["_temp_sum"] = cost_df[numeric_cols].sum(axis=1)
        cost_df = cost_df[cost_df["_temp_sum"] > 0]
        if cost_df.empty:
            return pd.DataFrame()
        monthly = cost_df.groupby(cost_df[DATE_COLUMN].dt.to_period("M"))["_temp_sum"].sum().reset_index()
        monthly.columns = [DATE_COLUMN, "total"]

    monthly.columns = ["date", "cost"]
    monthly["date"] = pd.to_datetime(monthly["date"].astype(str))
    monthly = monthly.sort_values("date")

    # Garantir que custos sejam floats
    monthly["cost"] = pd.to_numeric(monthly["cost"], errors="coerce")
    monthly = monthly.dropna(subset=["cost"])
    monthly = monthly[monthly["cost"] > 0]  # Remover zeros

    return monthly[["date", "cost"]]


@cached
def make_forecast(cost_df: pd.DataFrame, horizon: int = 6) -> Tuple[Optional[pd.DataFrame], Optional[ForecastStats]]:
    """
    Gera forecast usando regressão linear simples.

    Args:
        cost_df: DataFrame de custos histórico
        horizon: Número de meses para prever

    Returns:
        Tupla (forecast_df, stats) ou (None, None) se dados insuficientes
    """
    # Calcular totais mensais
    df = calculate_monthly_totals(cost_df)

    if df.empty or len(df) < 2:
        return None, None

    # Ordenar por data
    df = df.sort_values("date").reset_index(drop=True)

    # Calcular estatísticas
    stats = compute_stats(df)
    if stats is None:
        return None, None

    # Preparar dados para regressão linear
    # Criar índice temporal (0, 1, 2, ...)
    df["t"] = np.arange(len(df))

    # Treinar modelo de regressão linear
    X = df[["t"]]
    y = df["cost"]

    model = LinearRegression()
    model.fit(X, y)

    # Gerar previsões para os próximos meses
    n_history = len(df)
    last_date = df["date"].max()

    future_t = np.arange(n_history, n_history + horizon)
    y_pred = model.predict(future_t.reshape(-1, 1))

    # Gerar datas futuras
    forecast_dates = []
    for i in range(horizon):
        future_date = last_date + pd.DateOffset(months=i + 1)
        forecast_dates.append(future_date)

    # Aplicar validações e clamp de valores
    forecast_values = []
    for i, pred_value in enumerate(y_pred):
        # Clamp entre lower_bound e upper_bound
        clamped = np.clip(pred_value, stats.lower_bound, stats.upper_bound)

        # Validação 1: Nunca permitir valores negativos
        clamped = max(clamped, 0)

        # Validação 2: Se média histórica > 0, não permitir zero
        if stats.mean_cost > 0 and clamped == 0:
            clamped = stats.lower_bound

        # Validação 3: Não ultrapassar 3x o máximo histórico
        max_allowed = min(3 * stats.max_cost, stats.upper_bound)
        clamped = min(clamped, max_allowed)

        # Garantir que seja pelo menos lower_bound se muito baixo
        if clamped < stats.lower_bound and stats.lower_bound > 0:
            clamped = stats.lower_bound

        forecast_values.append(float(clamped))

    # Criar DataFrame de forecast
    forecast_df = pd.DataFrame(
        {
            "month": forecast_dates,
            "forecast": forecast_values,
            "lower": [stats.lower_bound] * horizon,
            "upper": [stats.upper_bound] * horizon,
        }
    )

    return forecast_df, stats


def forecast_costs(cost_df: pd.DataFrame, horizon_months: int = 6) -> List[ForecastResult]:
    """
    Wrapper para compatibilidade com código existente.

    Args:
        cost_df: DataFrame de custos histórico
        horizon_months: Número de meses para prever

    Returns:
        Lista de ForecastResult
    """
    forecast_df, stats = make_forecast(cost_df, horizon_months)

    if forecast_df is None or stats is None:
        return []

    results = []
    for _, row in forecast_df.iterrows():
        results.append(
            ForecastResult(
                date=row["month"].date(),
                service=None,
                cost_forecast=row["forecast"],
                lower_bound=row["lower"],
                upper_bound=row["upper"],
            )
        )

    return results
