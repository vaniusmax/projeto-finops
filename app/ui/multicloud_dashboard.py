"""Streamlit layout for the FinOps Multicloud view."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional, Tuple

import pandas as pd
import plotly.express as px
import streamlit as st

from app.data.normalize import CANONICAL_COLUMNS
from app.services import multicloud_analytics as mc
from app.services.date_window import compute_date_window

CLOUD_COLORS = {
    "AWS": "#F7931A",
    "OCI": "#F80000",
    "AZURE": "#0078D4",
    "total": "#111827",
}


def render_multicloud_dashboard(df_norm: pd.DataFrame) -> None:
    """Renderiza a página multicloud completa."""

    st.markdown("### 🌐 FinOps Multicloud")

    if df_norm is None or df_norm.empty:
        st.info("Nenhum dado multicloud disponível. Importe arquivos AWS/OCI para habilitar esta visão.")
        return

    filters = _render_global_header()
    filtered_df, period_tuple, days_count = _apply_filters(df_norm, filters)

    filters["date_start"] = period_tuple[0]
    filters["date_end"] = period_tuple[1]
    filters["days_count"] = days_count

    if filtered_df.empty:
        st.warning("Nenhum registro encontrado para os filtros informados.")
        return

    aggregations = _compute_multicloud_aggregations(filtered_df, period_tuple, days_count)

    _render_overview_section(aggregations)
    _render_distribution_section(aggregations)
    _render_finops_breakdown(filtered_df, aggregations)
    _render_comparativo_section(aggregations)
    _render_anomalies_section(aggregations)
    _render_operational_table(filtered_df)


def _render_global_header() -> dict:
    state = st.session_state.setdefault(
        "multicloud_filters",
        {"cloud": "Todos", "period": "3m", "view": "Executiva", "custom_range": None},
    )

    with st.container(border=True):
        col1, col2, col3 = st.columns(3)
        cloud_options = ["Todos", "AWS", "OCI", "AZURE"]
        period_options = ["30d", "3m", "6m", "Custom"]
        view_options = ["Executiva", "FinOps", "Técnica"]
        cloud_index = cloud_options.index(state["cloud"]) if state["cloud"] in cloud_options else 0
        period_index = period_options.index(state["period"]) if state["period"] in period_options else 1
        view_index = view_options.index(state["view"]) if state["view"] in view_options else 0
        state["cloud"] = col1.selectbox("Cloud", cloud_options, index=cloud_index)
        state["period"] = col2.selectbox("Período", period_options, index=period_index)
        state["view"] = col3.selectbox("View", view_options, index=view_index)

        custom_range = state.get("custom_range")
        if state["period"] == "Custom":
            default_start = custom_range[0] if custom_range else date.today() - timedelta(days=30)
            default_end = custom_range[1] if custom_range else date.today()
            custom_value = st.date_input("Período customizado", value=(default_start, default_end))
            state["custom_range"] = custom_value
        else:
            state["custom_range"] = None

    return state


def _apply_filters(df: pd.DataFrame, filters: dict) -> tuple[pd.DataFrame, Tuple[Optional[date], Optional[date]], Optional[int]]:
    filtered = df.copy()
    if "cloud_provider" not in filtered.columns:
        for column in CANONICAL_COLUMNS:
            if column not in filtered.columns:
                filtered[column] = None

    if filters["cloud"] != "Todos":
        filtered = filtered[filtered["cloud_provider"] == filters["cloud"]]

    filtered["usage_date"] = pd.to_datetime(filtered["usage_date"], errors="coerce")
    start_date, end_date, days_count = compute_date_window(
        filters.get("period", "3m"),
        filtered["usage_date"],
        filters.get("custom_range"),
    )

    if start_date:
        filtered = filtered[filtered["usage_date"] >= pd.to_datetime(start_date)]
    if end_date:
        filtered = filtered[filtered["usage_date"] <= pd.to_datetime(end_date)]

    return filtered, (start_date, end_date), days_count


@st.cache_data(show_spinner=False)
def _compute_multicloud_aggregations(
    df: pd.DataFrame,
    period_tuple: Tuple[Optional[date], Optional[date]],
    days_count: Optional[int],
) -> dict:
    # O cache considera o dataframe + range selecionado
    kpis = mc.get_kpis(df, period_tuple, period_days=days_count)
    anomalies = mc.detect_anomalies(df)
    return {
        "kpis": kpis,
        "monthly_trend": mc.get_monthly_trend(df),
        "top_services": mc.get_top_services(df),
        "treemap": mc.get_treemap_data(df),
        "stacked": {
            "cloud": mc.get_monthly_stacked(df, "cloud"),
            "category": mc.get_monthly_stacked(df, "category"),
        },
        "cloud_share": mc.get_cloud_share(df),
        "category_matrix": mc.get_category_cloud_matrix(df),
        "category_summary": mc.get_treemap_summary(df),
        "anomalies": anomalies,
        "insights": mc.generate_insights(df, anomalies),
    }


def _render_overview_section(aggregations: dict) -> None:
    kpis = aggregations["kpis"]
    cloud_share = aggregations["cloud_share"]
    monthly_trend = aggregations["monthly_trend"]

    st.subheader("Overview multicloud")
    metric_cols = st.columns(5)
    metric_cols[0].metric("Total gasto", f"USD {kpis['total_cost']:,.2f}")
    metric_cols[1].metric("Δ M/M", f"{kpis['mom_delta_pct']:,.1f}%", help="Variação percentual mês contra mês")
    metric_cols[2].metric("Média diária", f"USD {kpis['avg_daily']:,.2f}")
    metric_cols[3].metric("Pico mensal", kpis["max_month"])
    metric_cols[4].metric("Forecast próximo mês", f"USD {kpis['forecast_next_month']:,.2f}")

    cloud_cols = st.columns(3)
    for idx, cloud in enumerate(["AWS", "OCI", "AZURE"]):
        entry = cloud_share[cloud_share["cloud_provider"] == cloud]
        value = float(entry["cost_amount"].iloc[0]) if not entry.empty else 0.0
        pct = float(entry["pct"].iloc[0]) if not entry.empty else 0.0
        cloud_cols[idx].metric(cloud, f"USD {value:,.2f}", f"{pct:.1f}% do total")

    st.markdown("#### Tendência mensal")
    if monthly_trend.empty:
        st.caption("Sem dados suficientes para tendência.")
    else:
        value_columns = [col for col in monthly_trend.columns if col not in {"month"}]
        fig = px.line(
            monthly_trend,
            x="month",
            y=value_columns,
            markers=True,
            color_discrete_map={**CLOUD_COLORS},
        )
        fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)


def _render_distribution_section(aggregations: dict) -> None:
    treemap_df = aggregations["treemap"]
    top_services = aggregations["top_services"]

    st.subheader("Distribuição de custos")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("##### Treemap Serviço → Cloud")
        if treemap_df.empty:
            st.caption("Sem dados para treemap.")
        else:
            fig = px.treemap(
                treemap_df,
                path=["cloud_provider", "service_category", "service_name"],
                values="cost_amount",
                color="cloud_provider",
                color_discrete_map=CLOUD_COLORS,
            )
            fig.update_layout(margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with col2:
        st.markdown("##### Top serviços")
        if top_services.empty:
            st.caption("Sem serviços ranqueados.")
        else:
            fig = px.bar(
                top_services.sort_values("cost_amount"),
                x="cost_amount",
                y="service_name",
                orientation="h",
                color="cloud_provider",
                color_discrete_map=CLOUD_COLORS,
            )
            fig.update_layout(margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _render_finops_breakdown(filtered_df: pd.DataFrame, aggregations: dict) -> None:
    st.subheader("FinOps Breakdown")
    stack_option = st.radio("Stack por", ["Cloud", "Categoria"], horizontal=True)
    key = "category" if stack_option == "Categoria" else "cloud"
    stacked_df = aggregations["stacked"][key]

    if stacked_df.empty:
        st.caption("Sem dados para composição empilhada.")
    else:
        value_columns = [col for col in stacked_df.columns if col not in {"month"}]
        melted = stacked_df.melt(id_vars="month", value_vars=value_columns, var_name="Serie", value_name="Custo")
        fig = px.bar(
            melted,
            x="month",
            y="Custo",
            color="Serie",
            barmode="stack",
        )
        fig.update_layout(margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig, use_container_width=True)

    summary = aggregations["category_summary"]
    if summary.empty:
        st.caption("Sem dados para distribuição por categoria.")
    else:
        total = summary["cost_amount"].sum()
        cols = st.columns(min(4, len(summary)))
        for idx, (_, row) in enumerate(summary.iterrows()):
            pct = (row["cost_amount"] / total * 100) if total else 0
            cols[idx % len(cols)].metric(row["service_category"].title(), f"{pct:.1f}%", f"USD {row['cost_amount']:,.0f}")


def _render_comparativo_section(aggregations: dict) -> None:
    st.subheader("Comparativo Multicloud")
    matrix_df = aggregations["category_matrix"]
    if matrix_df.empty:
        st.caption("Sem dados para matriz categoria x cloud.")
        return

    display_df = matrix_df.copy()
    for cloud in ["AWS", "OCI", "AZURE"]:
        if cloud in display_df.columns:
            display_df[cloud] = display_df[cloud].map(lambda value: f"USD {value:,.0f}")
    st.dataframe(display_df, use_container_width=True)

    heatmap_source = matrix_df.set_index("service_category")
    if not heatmap_source.empty:
        heatmap_source = heatmap_source.reindex(columns=["AWS", "OCI", "AZURE"], fill_value=0)
        fig = px.imshow(
            heatmap_source,
            aspect="auto",
            text_auto=".0f",
            color_continuous_scale="Blues",
            labels=dict(color="USD"),
        )
        fig.update_layout(margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)


def _render_anomalies_section(aggregations: dict) -> None:
    st.subheader("Anomalias & Insights")
    anomalies = aggregations["anomalies"]
    insights = aggregations["insights"]

    col1, col2 = st.columns((2, 1))
    with col1:
        st.markdown("##### Tabela de anomalias")
        if anomalies.empty:
            st.caption("Nenhuma anomalia identificada pelas regras atuais.")
        else:
            data = anomalies.copy()
            data["variation_pct"] = data["variation_pct"].map(lambda v: f"{v:.1f}%")
            data["cost_amount"] = data["cost_amount"].map(lambda v: f"USD {v:,.0f}")
            st.dataframe(data, use_container_width=True, height=240)

    with col2:
        st.markdown("##### Insights")
        for insight in insights:
            st.info(f"💡 {insight}")


def _render_operational_table(df: pd.DataFrame) -> None:
    st.subheader("Detalhamento Operacional")
    col1, col2, col3, col4 = st.columns(4)

    services = sorted(df["service_name"].dropna().unique())
    categories = sorted(df["service_category"].dropna().unique())
    accounts = sorted(df["account_scope"].dropna().unique())
    regions = sorted(df["region"].dropna().unique())

    selected_services = col1.multiselect("Serviço", services)
    selected_categories = col2.multiselect("Categoria", categories)
    selected_accounts = col3.multiselect("Account / Compartment", accounts)
    selected_regions = col4.multiselect("Região", regions)

    filtered = df.copy()
    if selected_services:
        filtered = filtered[filtered["service_name"].isin(selected_services)]
    if selected_categories:
        filtered = filtered[filtered["service_category"].isin(selected_categories)]
    if selected_accounts:
        filtered = filtered[filtered["account_scope"].isin(selected_accounts)]
    if selected_regions:
        filtered = filtered[filtered["region"].isin(selected_regions)]

    filtered = filtered.sort_values("usage_date")
    display = filtered.copy()
    display["usage_date"] = pd.to_datetime(display["usage_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    display["cost_amount"] = display["cost_amount"].map(lambda v: f"USD {v:,.2f}")
    st.dataframe(display, use_container_width=True, height=420)
