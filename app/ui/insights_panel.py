"""Painel de insights automáticos gerados por IA."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.services.insights_service import generate_insights


def render_insights_panel(cost_df: pd.DataFrame, kpi_summary: dict) -> None:
    """Renderiza painel de insights automáticos."""
    st.markdown("### Insights Automáticos")
    st.caption("Análise executiva gerada automaticamente por IA sobre os custos do período")

    if cost_df.empty:
        st.info("Sem dados para gerar insights.")
        return

    with st.spinner("Gerando insights..."):
        insights_text = generate_insights(cost_df, kpi_summary)

    st.markdown(insights_text)


