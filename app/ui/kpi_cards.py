"""Componentes de cards de KPI."""
from __future__ import annotations

from typing import Dict

import streamlit as st

from app.data.models import KPISummary


def render_kpi_row(kpi_summary: KPISummary) -> None:
    """
    Renderiza cards de KPI em duas linhas.

    Args:
        kpi_summary: Resumo de KPIs
    """
    kpis = [
        ("Total geral", f"${kpi_summary.total_cost:,.2f}", "Soma de custos"),
        ("Média", f"${kpi_summary.average_cost:,.2f}", "Ticket médio"),
        ("Máximo", f"${kpi_summary.max_cost:,.2f}", "Maior gasto registrado"),
        ("Mínimo", f"${kpi_summary.min_cost:,.2f}", "Menor gasto registrado"),
        ("Serviço mais caro", kpi_summary.peak_service or "-", "Top spend"),
        ("Serviço mais barato", kpi_summary.lowest_service or "-", "Menor contribuição"),
        ("Mês com maior gasto", kpi_summary.peak_month or "-", "Pico mensal"),
        ("Mês com menor gasto", kpi_summary.lowest_month or "-", "Vale mensal"),
    ]

    for row in (kpis[:4], kpis[4:]):
        cols = st.columns(4)
        for col, (label, value, subtitle) in zip(cols, row):
            with col:
                st.markdown(
                    f"""
                    <div class="kpi-card">
                        <h3>{label.upper()}</h3>
                        <div class="kpi-value">{value}</div>
                        <div class="kpi-footnote">{subtitle}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


