"""Painel de detecção de anomalias."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.data.repositories import get_monthly_totals
from app.services.anomaly_service import detect_anomalies


def render_anomaly_panel(cost_df: pd.DataFrame) -> None:
    """Renderiza painel de anomalias detectadas."""
    st.markdown("### Detecção de Anomalias")
    st.caption("Identificação automática de comportamentos fora do padrão nos custos")

    if cost_df.empty:
        st.info("Sem dados para detectar anomalias.")
        return

    monthly_data = get_monthly_totals(cost_df)

    if monthly_data.empty:
        st.warning("Dados insuficientes para detecção de anomalias. É necessário histórico mensal.")
        return

    with st.spinner("Detectando anomalias..."):
        anomalies = detect_anomalies(monthly_data)

    if not anomalies:
        st.success("✅ Nenhuma anomalia detectada nos dados analisados.")
        return

    st.warning(f"⚠️ {len(anomalies)} anomalia(s) detectada(s)")

    # Tabela de anomalias
    anomalies_df = pd.DataFrame([a.dict() for a in anomalies])
    st.dataframe(anomalies_df[["date", "service", "cost", "anomaly_score", "explanation"]], use_container_width=True)

    # Detalhes
    for anomaly in anomalies:
        with st.expander(f"🔍 {anomaly.service} - {anomaly.date}"):
            st.metric("Custo", f"${anomaly.cost:,.2f}")
            st.metric("Score de Anomalia", f"{anomaly.anomaly_score:.2f}")
            if anomaly.explanation:
                st.markdown(f"**Explicação:** {anomaly.explanation}")


