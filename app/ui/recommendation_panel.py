"""Painel de recomendações de otimização."""
from __future__ import annotations

from typing import Dict

import pandas as pd
import streamlit as st

from app.data.repositories import get_percentual_distribution, get_service_totals
from app.services.recommendation_service import generate_recommendations


def render_recommendation_panel(cost_df: pd.DataFrame) -> None:
    """Renderiza painel de recomendações FinOps."""
    st.markdown("### Recomendações de Otimização")
    st.caption("Sugestões automáticas para reduzir custos baseadas em melhores práticas FinOps")

    if cost_df.empty:
        st.info("Sem dados para gerar recomendações.")
        return

    service_totals = get_service_totals(cost_df)
    distribution = get_percentual_distribution(cost_df)
    total_cost = service_totals.sum()

    aggregated_data = {
        "service_totals": service_totals,
        "distribution": distribution,
        "total_cost": total_cost,
    }

    with st.spinner("Gerando recomendações..."):
        recommendations = generate_recommendations(aggregated_data)

    if not recommendations:
        st.info("Nenhuma recomendação específica no momento. Continue monitorando os custos.")
        return

    # Agrupar por impacto
    impact_colors = {"alto": "🔴", "medio": "🟡", "baixo": "🟢"}

    for rec in recommendations:
        impact_icon = impact_colors.get(rec.impact, "⚪")
        with st.container(border=True):
            st.markdown(f"#### {impact_icon} {rec.title}")
            st.caption(f"Impacto: {rec.impact.upper()} | Economia estimada: {rec.estimated_saving_percent:.0f}%")
            st.markdown(rec.description)
            if rec.service:
                st.caption(f"Serviço: {rec.service}")


