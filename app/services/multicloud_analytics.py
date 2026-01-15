"""Analytics helpers dedicated to the FinOps Multicloud experience."""
from __future__ import annotations

from datetime import date
from typing import Optional, Tuple

import pandas as pd

CLOUD_ORDER = ["AWS", "OCI", "AZURE"]


def get_kpis(
    df_norm: pd.DataFrame,
    period_filter: Optional[Tuple[date, date]] = None,
    period_days: Optional[int] = None,
) -> dict:
    """Calcula KPIs principais do período."""

    df = _apply_period_filter(df_norm, period_filter)
    if df.empty:
        return {
            "total_cost": 0.0,
            "avg_daily": 0.0,
            "max_month": "-",
            "min_month": "-",
            "mom_delta_pct": 0.0,
            "forecast_next_month": 0.0,
        }

    df["usage_date"] = pd.to_datetime(df["usage_date"], errors="coerce")
    total_cost = float(df["cost_amount"].sum())

    if period_days is None:
        period_days = _days_from_filter(period_filter, df["usage_date"])
    avg_daily = float(total_cost / period_days) if period_days else float(total_cost)

    monthly_totals = _monthly_totals(df)
    max_month = monthly_totals.idxmax() if not monthly_totals.empty else "-"
    min_month = monthly_totals.idxmin() if not monthly_totals.empty else "-"

    mom_delta_pct = 0.0
    forecast_next_month = 0.0
    if not monthly_totals.empty:
        sorted_values = monthly_totals.sort_index()
        if len(sorted_values) >= 2:
            last = sorted_values.iloc[-1]
            previous = sorted_values.iloc[-2]
            if previous != 0:
                mom_delta_pct = float((last - previous) / previous * 100)
        forecast_window = sorted_values.tail(3)
        forecast_next_month = float(forecast_window.mean())

    return {
        "total_cost": round(total_cost, 2),
        "avg_daily": round(avg_daily, 2),
        "max_month": str(max_month) if max_month and max_month != "nan" else "-",
        "min_month": str(min_month) if min_month and min_month != "nan" else "-",
        "mom_delta_pct": round(mom_delta_pct, 2),
        "forecast_next_month": round(forecast_next_month, 2),
    }


def get_monthly_trend(df_norm: pd.DataFrame) -> pd.DataFrame:
    """Retorna dataframe com linhas por provedor e total."""

    if df_norm.empty:
        return pd.DataFrame(columns=["month"] + CLOUD_ORDER + ["total"])

    df = _prepare_monthly_frame(df_norm)
    trend = df.pivot_table(index="month", columns="cloud_provider", values="cost_amount", aggfunc="sum", fill_value=0)
    for cloud in CLOUD_ORDER:
        if cloud not in trend.columns:
            trend[cloud] = 0.0
    trend = trend[CLOUD_ORDER]
    trend["total"] = trend.sum(axis=1)
    ordering = (
        df[["month", "month_sort"]]
        .drop_duplicates()
        .sort_values("month_sort")
    )
    trend = trend.reset_index().merge(ordering, on="month", how="left")
    return trend.sort_values("month_sort").drop(columns=["month_sort"])


def get_top_services(df_norm: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Top serviços por custo."""

    if df_norm.empty:
        return pd.DataFrame(columns=["cloud_provider", "service_name", "cost_amount"])
    grouped = (
        df_norm.groupby(["cloud_provider", "service_name"])["cost_amount"].sum().reset_index().sort_values("cost_amount", ascending=False)
    )
    return grouped.head(n)


def get_treemap_data(df_norm: pd.DataFrame, top_k: int = 30) -> pd.DataFrame:
    """Dados hierárquicos (cloud -> categoria -> serviço) para treemap."""

    if df_norm.empty:
        return pd.DataFrame(columns=["cloud_provider", "service_category", "service_name", "cost_amount"])

    service_totals = (
        df_norm.groupby(["cloud_provider", "service_category", "service_name"])["cost_amount"].sum().reset_index()
    )
    top_services = service_totals.sort_values("cost_amount", ascending=False).head(top_k)["service_name"]
    treemap_df = service_totals.copy()
    treemap_df.loc[~treemap_df["service_name"].isin(top_services), "service_name"] = "Outros"
    treemap_df = treemap_df.groupby(["cloud_provider", "service_category", "service_name"])["cost_amount"].sum().reset_index()
    return treemap_df


def get_monthly_stacked(df_norm: pd.DataFrame, stack_by: str = "cloud") -> pd.DataFrame:
    """Retorna dados empilhados por mês."""

    if df_norm.empty:
        return pd.DataFrame(columns=["month"])

    df = _prepare_monthly_frame(df_norm)
    if stack_by == "category":
        pivot = df.pivot_table(index="month", columns="service_category", values="cost_amount", aggfunc="sum", fill_value=0)
    else:
        pivot = df.pivot_table(index="month", columns="cloud_provider", values="cost_amount", aggfunc="sum", fill_value=0)

    ordering = (
        df[["month", "month_sort"]]
        .drop_duplicates()
        .sort_values("month_sort")
    )
    pivot = pivot.reset_index().merge(ordering, on="month", how="left")
    return pivot.sort_values("month_sort").drop(columns=["month_sort"])


def get_cloud_share(df_norm: pd.DataFrame) -> pd.DataFrame:
    """Participação percentual por provedor."""

    totals = df_norm.groupby("cloud_provider")["cost_amount"].sum() if not df_norm.empty else pd.Series(dtype=float)
    records = []
    grand_total = totals.sum()
    for cloud in CLOUD_ORDER:
        cost_value = float(totals.get(cloud, 0.0))
        pct = float((cost_value / grand_total * 100) if grand_total else 0.0)
        records.append({"cloud_provider": cloud, "cost_amount": round(cost_value, 2), "pct": round(pct, 2)})
    return pd.DataFrame(records)


def get_category_cloud_matrix(df_norm: pd.DataFrame) -> pd.DataFrame:
    """Tabela categoria x cloud."""

    if df_norm.empty:
        return pd.DataFrame(columns=["service_category"] + CLOUD_ORDER)
    pivot = df_norm.pivot_table(
        index="service_category",
        columns="cloud_provider",
        values="cost_amount",
        aggfunc="sum",
        fill_value=0,
    )
    for cloud in CLOUD_ORDER:
        if cloud not in pivot.columns:
            pivot[cloud] = 0.0
    return pivot.reset_index()


def detect_anomalies(df_norm: pd.DataFrame, threshold: float = 100.0, pct_change: float = 40.0) -> pd.DataFrame:
    """Detecção simples baseada em variação mensal por serviço."""

    if df_norm.empty:
        return pd.DataFrame(columns=["month", "cloud_provider", "service_name", "cost_amount", "variation_pct"])

    df = _prepare_monthly_frame(df_norm)
    grouped = (
        df.groupby(["cloud_provider", "service_name", "month", "month_sort"])["cost_amount"]
        .sum()
        .reset_index()
        .sort_values(["cloud_provider", "service_name", "month_sort"])
    )

    grouped["prev_cost"] = grouped.groupby(["cloud_provider", "service_name"])["cost_amount"].shift(1)
    grouped["variation_pct"] = ((grouped["cost_amount"] - grouped["prev_cost"]) / grouped["prev_cost"]) * 100
    anomalies = grouped[
        (grouped["prev_cost"] > 0)
        & (grouped["cost_amount"] >= threshold)
        & (grouped["variation_pct"].abs() >= pct_change)
    ].copy()
    anomalies["month"] = anomalies["month"].astype(str)
    return anomalies[["month", "cloud_provider", "service_name", "cost_amount", "variation_pct"]]


def get_treemap_summary(df_norm: pd.DataFrame) -> pd.DataFrame:
    """Resumo auxiliar com totais por categoria."""

    if df_norm.empty:
        return pd.DataFrame(columns=["service_category", "cost_amount"])
    return df_norm.groupby("service_category")["cost_amount"].sum().reset_index()


def generate_insights(df_norm: pd.DataFrame, anomalies_df: pd.DataFrame) -> list[str]:
    """Gera insights textuais simples."""

    insights: list[str] = []
    if df_norm.empty:
        return ["Nenhum dado disponível. Importe arquivos AWS/OCI para iniciar a análise."]

    totals = df_norm.groupby("cloud_provider")["cost_amount"].sum().sort_values(ascending=False)
    grand_total = totals.sum()
    if not totals.empty and grand_total > 0:
        top_cloud = totals.idxmax()
        pct = totals.iloc[0] / grand_total * 100
        insights.append(f"{top_cloud} responde por {pct:.1f}% do custo total no período analisado.")

    category_totals = df_norm.groupby("service_category")["cost_amount"].sum().sort_values(ascending=False)
    if not category_totals.empty:
        cat, value = category_totals.index[0], category_totals.iloc[0]
        insights.append(f"A categoria {cat.title()} consumiu USD {value:,.0f}, liderando a composição.")

    monthly = _monthly_totals(df_norm)
    if len(monthly) >= 2:
        trend = monthly.tail(2)
        delta = trend.iloc[-1] - trend.iloc[-2]
        direction = "aumentou" if delta > 0 else "reduziu"
        insights.append(f"O custo total {direction} USD {abs(delta):,.0f} em relação ao mês anterior.")

    if not anomalies_df.empty:
        anomaly = anomalies_df.sort_values("variation_pct", key=lambda s: s.abs(), ascending=False).iloc[0]
        insights.append(
            f"Anomalia: {anomaly['service_name']} em {anomaly['cloud_provider']} variou {anomaly['variation_pct']:.1f}% "
            f"no mês {anomaly['month']}."
        )

    top_services = get_top_services(df_norm, n=1)
    if not top_services.empty:
        top_service = top_services.iloc[0]
        insights.append(
            f"O serviço {top_service['service_name']} ({top_service['cloud_provider']}) concentra USD {top_service['cost_amount']:,.0f}."
        )

    while len(insights) < 5:
        insights.append("Continue acompanhando os custos para descobrir novas oportunidades de otimização.")
    return insights[:5]


# Auxiliares -----------------------------------------------------------------


def _days_from_filter(
    period_filter: Optional[Tuple[date, date]],
    usage_dates: pd.Series,
) -> Optional[int]:
    if period_filter and period_filter[0] and period_filter[1]:
        span = (period_filter[1] - period_filter[0]).days + 1
        if span > 0:
            return span

    normalized = pd.to_datetime(usage_dates, errors="coerce").dropna()
    if normalized.empty:
        return None

    span = (normalized.max() - normalized.min()).days + 1
    return span if span > 0 else None


def _apply_period_filter(df_norm: pd.DataFrame, period_filter: Optional[Tuple[date, date]]) -> pd.DataFrame:
    if df_norm.empty or not period_filter:
        return df_norm.copy()
    start, end = period_filter
    df = df_norm.copy()
    df["usage_date"] = pd.to_datetime(df["usage_date"], errors="coerce")
    if start:
        df = df[df["usage_date"] >= pd.to_datetime(start)]
    if end:
        df = df[df["usage_date"] <= pd.to_datetime(end)]
    return df


def _prepare_monthly_frame(df_norm: pd.DataFrame) -> pd.DataFrame:
    df = df_norm.copy()
    df["usage_date"] = pd.to_datetime(df["usage_date"], errors="coerce")
    month_labels = df["usage_date"].dt.to_period("M").astype(str)
    na_mask = month_labels.isna() | (month_labels == "NaT")
    if "month" in df.columns:
        month_labels.loc[na_mask] = df.loc[na_mask, "month"].fillna("Sem data").astype(str)
    month_sort = pd.to_datetime(month_labels, errors="coerce")
    df["month"] = month_labels
    df["month_sort"] = month_sort
    return df


def _monthly_totals(df_norm: pd.DataFrame) -> pd.Series:
    df = _prepare_monthly_frame(df_norm)
    totals = (
        df.groupby("month")["cost_amount"]
        .sum()
        .reset_index()
        .merge(df[["month", "month_sort"]].drop_duplicates(), on="month", how="left")
        .sort_values("month_sort")
    )
    return totals.set_index("month")["cost_amount"]
