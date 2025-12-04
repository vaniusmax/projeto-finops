"""Layout principal do dashboard."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.data.models import KPISummary
from app.data.repositories import get_cost_ranking, get_monthly_totals, get_percentual_distribution
from app.ui import anomaly_panel, chat_panel, charts, forecast_panel, insights_panel, kpi_cards, recommendation_panel


def inject_global_css() -> None:
    """Injeta CSS global para estilização."""
    st.markdown(
        """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

            :root {
                --page-bg: #F9FAFB;
                --card-bg: #FFFFFF;
                --card-border: #E5E7EB;
                --text-primary: #111827;
                --text-secondary: #6B7280;
                --brand-primary: #1D4ED8;
                --muted-text: #9CA3AF;
            }

            .main, .block-container {
                font-family: 'Inter', sans-serif;
            }

            .block-container {
                padding: 2rem 3rem 3rem 3rem;
                background: var(--page-bg);
            }

            section[data-testid="stSidebar"] {
                background: #F3F4F6;
                color: #111827;
                padding: 1.5rem 1rem;
            }

            section[data-testid="stSidebar"] .stButton>button,
            section[data-testid="stSidebar"] .stDownloadButton>button {
                background: #1D4ED8;
                border: none;
                color: #FFFFFF;
            }

            section[data-testid="stSidebar"] h1,
            section[data-testid="stSidebar"] h2,
            section[data-testid="stSidebar"] h3,
            section[data-testid="stSidebar"] .stMarkdown,
            section[data-testid="stSidebar"] label,
            section[data-testid="stSidebar"] .stSelectbox label,
            section[data-testid="stSidebar"] .stMultiselect label,
            section[data-testid="stSidebar"] .stDateInput label {
                color: #111827;
            }

            section[data-testid="stSidebar"] .stSelectbox>div>div,
            section[data-testid="stSidebar"] .stMultiselect>div>div,
            section[data-testid="stSidebar"] .stDateInput>div>div {
                background-color: #FFFFFF;
            }

            .page-header {
                background: var(--card-bg);
                border: 1px solid var(--card-border);
                border-radius: 16px;
                padding: 1.5rem 2rem;
                margin-bottom: 1.5rem;
                box-shadow: 0 10px 30px rgba(17, 24, 39, 0.05);
                display: flex;
                justify-content: space-between;
                gap: 1rem;
            }

            .page-header h1 {
                margin: 0;
                font-size: 1.75rem;
                color: var(--text-primary);
            }

            .kpi-card {
                background: var(--card-bg);
                border: 1px solid var(--card-border);
                border-radius: 16px;
                padding: 1rem 1.2rem;
                box-shadow: 0 6px 18px rgba(15, 23, 42, 0.06);
                height: 100%;
            }

            .kpi-card h3 {
                text-transform: uppercase;
                font-size: 0.75rem;
                letter-spacing: 0.08em;
                color: var(--text-secondary);
                margin-bottom: 0.25rem;
            }

            .kpi-card .kpi-value {
                font-size: 1.8rem;
                font-weight: 600;
                color: var(--text-primary);
            }

            .kpi-card .kpi-footnote {
                font-size: 0.9rem;
                color: var(--text-secondary);
                margin-top: 0.3rem;
            }

            .section-title {
                font-size: 0.95rem;
                font-weight: 600;
                letter-spacing: 0.04em;
                text-transform: uppercase;
                color: var(--text-secondary);
                margin: 0 0 0.25rem 0;
            }

            .chart-caption {
                color: var(--muted-text);
                font-size: 0.85rem;
                margin-top: 0.2rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(dataset_name: str, data_source_label: str, period_label: str) -> None:
    """Renderiza cabeçalho da página."""
    st.markdown(
        f"""
        <div class="page-header">
            <div>
                <p style="text-transform: uppercase; letter-spacing: 0.08em; font-size: 0.75rem; color: var(--text-secondary); margin-bottom: 0.3rem;">FinOps • Custos Multi-Cloud</p>
                <h1>{dataset_name}</h1>
                <p style="font-size: 0.95rem; color: var(--text-secondary);">{data_source_label} · {period_label}</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_main_content(
    cost_df: pd.DataFrame,
    kpi_summary: KPISummary,
    services: list[str],
    chart_column: str,
) -> None:
    """Renderiza conteúdo principal com abas."""
    tabs = st.tabs(["Detalhes", "Tabelas", "Insights IA", "Previsão", "Anomalias", "Recomendações", "Chat IA"])

    with tabs[0]:  # Detalhes
        kpi_cards.render_kpi_row(kpi_summary)
        st.markdown("<br>", unsafe_allow_html=True)

        # Gráficos
        col1, col2 = st.columns(2, gap="large")

        with col1:
            with st.container(border=True):
                st.markdown('<p class="section-title">Ranking de Custos</p>', unsafe_allow_html=True)
                ranking_df = get_cost_ranking(cost_df, services)
                charts.render_ranking_chart(ranking_df)
                st.markdown('<p class="chart-caption">Ordena os serviços pelos maiores custos agregados.</p>', unsafe_allow_html=True)

        with col2:
            with st.container(border=True):
                st.markdown('<p class="section-title">Distribuição Percentual</p>', unsafe_allow_html=True)
                ranking_df = get_cost_ranking(cost_df, services)
                percentual_df = get_percentual_distribution(cost_df, services)
                # Passar número de itens do ranking para ajustar altura do gráfico de pizza
                ranking_count = len(ranking_df) if not ranking_df.empty else 0
                charts.render_distribution_chart(percentual_df, ranking_count=ranking_count)
                st.markdown('<p class="chart-caption">Mostra a participação relativa dos 10 principais serviços e demais agrupados como "Outros".</p>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        
        # Gráficos de evolução mensal em duas colunas
        col3, col4 = st.columns(2, gap="large")
        
        with col3:
            with st.container(border=True):
                st.markdown('<p class="section-title" style="margin-bottom:0.25rem;">Total Gasto por Mês</p>', unsafe_allow_html=True)
                charts.render_monthly_bar_chart(cost_df)
                st.markdown('<p class="chart-caption">Total gasto em cada mês dividido pelos 9 serviços com maior gasto e "Outros".</p>', unsafe_allow_html=True)
        
        with col4:
            with st.container(border=True):
                st.markdown('<p class="section-title" style="margin-bottom:0.25rem;">Evolução Mensal de Custos</p>', unsafe_allow_html=True)
                monthly_totals = get_monthly_totals(cost_df, services=[chart_column] if chart_column in cost_df.columns else None)
                charts.render_evolution_chart(monthly_totals, chart_column)
                st.markdown('<p class="chart-caption">Série temporal baseada na coluna selecionada para gráficos.</p>', unsafe_allow_html=True)

        # Dados filtrados
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### Dados filtrados")
        if cost_df.empty:
            st.info("Sem dados para exibir. Importe um CSV e ajuste os filtros.")
        else:
            st.dataframe(cost_df, use_container_width=True, height=420)

    with tabs[1]:  # Tabelas
        st.markdown("### Totais por serviço")
        service_totals = get_cost_ranking(cost_df, services)
        if service_totals.empty:
            st.caption("Nenhum total disponível.")
        else:
            st.dataframe(service_totals, use_container_width=True, height=320)

        st.markdown("### Distribuição percentual")
        percentual_df = get_percentual_distribution(cost_df, services)
        if percentual_df.empty:
            st.caption("Sem dados para percentuais.")
        else:
            st.dataframe(percentual_df, use_container_width=True, height=320)

    with tabs[2]:  # Insights IA
        insights_panel.render_insights_panel(cost_df, kpi_summary.dict())

    with tabs[3]:  # Previsão
        # Passar nome do dataset via session_state
        dataset_name = st.session_state.get("dataset_name", "Arquivo de custos")
        st.session_state["dataset_name"] = dataset_name
        forecast_panel.render_forecast_panel(cost_df, services)

    with tabs[4]:  # Anomalias
        anomaly_panel.render_anomaly_panel(cost_df)

    with tabs[5]:  # Recomendações
        recommendation_panel.render_recommendation_panel(cost_df)

    with tabs[6]:  # Chat IA
        chat_panel.render_chat_panel(cost_df)

