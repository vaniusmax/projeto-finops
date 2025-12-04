"""Painel de previsão de custos - FinOps Multi-Cloud."""
from __future__ import annotations

from typing import List, Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.services.forecast_service import calculate_monthly_totals, make_forecast


def render_forecast_panel(cost_df: pd.DataFrame, services: Optional[List[str]] = None, horizon_months: int = 6) -> None:
    """Renderiza painel de previsão de custos conforme especificação."""
    # 4.1 Cabeçalho
    st.markdown("# Previsão de Custos – FinOps Multi-Cloud")
    
    # Obter nome do arquivo - será passado via parâmetro ou session_state
    # Por enquanto, usar um nome padrão ou tentar obter da sessão
    try:
        dataset_name = st.session_state.get("dataset_name", "Arquivo de custos")
    except:
        dataset_name = "Arquivo de custos"
    st.markdown(f"### {dataset_name}")
    
    st.markdown(
        "Previsão baseada no total mensal histórico usando análise de tendência linear e intervalo de confiança estatístico."
    )

    if cost_df.empty:
        st.error("Sem dados para gerar previsão. Importe um CSV primeiro.")
        return

    # Calcular totais mensais históricos
    historical_df = calculate_monthly_totals(cost_df)

    if historical_df.empty or len(historical_df) < 2:
        st.warning("Dados históricos insuficientes. É necessário pelo menos 2 meses de dados para gerar previsões.")
        return

    # Aviso se série histórica muito curta
    if len(historical_df) < 3:
        st.warning("⚠️ A série histórica é muito curta, portanto o forecast é meramente indicativo.")

    # Gerar forecast
    with st.spinner("Calculando previsões..."):
        forecast_df, stats = make_forecast(cost_df, horizon=horizon_months)

    if forecast_df is None or stats is None:
        st.error("Não foi possível gerar previsões. Verifique os dados.")
        return

    # 4.2 Cards de métricas
    st.markdown("---")
    
    mean_forecast = forecast_df["forecast"].mean()
    total_forecast = forecast_df["forecast"].sum()
    variation_pct = ((mean_forecast / stats.mean_cost - 1) * 100) if stats.mean_cost > 0 else 0

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Média Histórica", f"${stats.mean_cost:,.2f}")

    with col2:
        st.metric("Média Prevista (6 meses)", f"${mean_forecast:,.2f}")

    with col3:
        st.metric("Total Previsto (6 meses)", f"${total_forecast:,.2f}")

    with col4:
        # Variação com cor verde se positiva, vermelha se negativa
        delta_color = "normal" if variation_pct >= 0 else "inverse"
        st.metric("Variação Média (%)", f"{variation_pct:+.2f}%", delta=f"{variation_pct:+.2f}%", delta_color=delta_color)

    # 4.3 Gráfico principal
    st.markdown("---")
    st.markdown("### Evolução e Previsão de Custos Mensais")

    fig = go.Figure()

    # Linha azul sólida: custos históricos
    fig.add_trace(
        go.Scatter(
            x=historical_df["date"],
            y=historical_df["cost"],
            mode="lines+markers",
            name="Histórico Real",
            line=dict(color="#2563EB", width=3),
            marker=dict(size=8, color="#2563EB"),
        )
    )

    # Linha vermelha tracejada: previsões
    fig.add_trace(
        go.Scatter(
            x=forecast_df["month"],
            y=forecast_df["forecast"],
            mode="lines+markers",
            name="Previsão",
            line=dict(color="#DC2626", width=3, dash="dash"),
            marker=dict(size=8, color="#DC2626"),
        )
    )

    # Faixa de intervalo de confiança (área preenchida)
    fig.add_trace(
        go.Scatter(
            x=forecast_df["month"],
            y=forecast_df["upper"],
            mode="lines",
            name="Limite Superior",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=forecast_df["month"],
            y=forecast_df["lower"],
            mode="lines",
            name="Intervalo de Confiança",
            fill="tonexty",
            fillcolor="rgba(220, 38, 38, 0.15)",
            line=dict(width=0),
            hoverinfo="skip",
        )
    )

    # Linha vertical pontilhada marcando "Início da Previsão"
    last_historical_date = historical_df["date"].max()
    fig.add_shape(
        type="line",
        x0=last_historical_date,
        x1=last_historical_date,
        y0=0,
        y1=1,
        yref="paper",
        line=dict(dash="dot", color="gray", width=2),
    )
    fig.add_annotation(
        x=last_historical_date,
        y=1,
        yref="paper",
        text="Início da Previsão",
        showarrow=False,
        xanchor="center",
        yshift=10,
        font=dict(size=10, color="gray"),
    )

    fig.update_layout(
        title="",
        xaxis_title="Mês",
        yaxis_title="Custo Total ($)",
        height=450,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(showgrid=True, gridcolor="#E5E7EB"),
        yaxis=dict(showgrid=True, gridcolor="#E5E7EB", tickformat="$,.0f"),
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # 4.4 Tabela "Previsões detalhadas por mês"
    st.markdown("---")
    st.markdown("### Previsões Detalhadas por Mês")

    # Preparar tabela para exibição
    display_df = forecast_df.copy()
    display_df["Mês"] = display_df["month"].dt.strftime("%Y-%m")
    display_df["Previsão ($)"] = display_df["forecast"].apply(lambda x: f"${x:,.2f}")
    display_df["Limite Inferior ($)"] = display_df["lower"].apply(lambda x: f"${x:,.2f}")
    display_df["Limite Superior ($)"] = display_df["upper"].apply(lambda x: f"${x:,.2f}")

    # Selecionar apenas colunas de exibição
    display_df = display_df[["Mês", "Previsão ($)", "Limite Inferior ($)", "Limite Superior ($)"]]

    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # Informações adicionais
    st.caption("💡 Estatísticas: Média histórica = ${:.2f}, Desvio padrão = ${:.2f}, Mínimo = ${:.2f}, Máximo = ${:.2f}".format(
        stats.mean_cost, stats.std_cost, stats.min_cost, stats.max_cost
    ))
