"""Componentes de filtros na sidebar."""
from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional, Tuple

import streamlit as st

from app.data.loaders import ImportedFile


def render_sidebar(
    available_files: List[ImportedFile],
    selected_file_index: int,
    services: List[str],
    metric_columns: List[str],
    cloud_options: Optional[List[str]] = None,
    selected_cloud: Optional[str] = None,
    selected_services: Optional[List[str]] = None,
    period_range: Optional[Tuple[date, date]] = None,
    period_min: Optional[date] = None,
    period_max: Optional[date] = None,
    chart_column: Optional[str] = None,
) -> Dict:
    """
    Renderiza sidebar com filtros.

    Returns:
        Dict com filtros selecionados
    """
    cloud_options = cloud_options or ["AWS", "OCI"]
    selected_cloud = selected_cloud or cloud_options[0]

    st.sidebar.markdown("### Nuvem")
    cloud_choice = st.sidebar.selectbox("Selecione a nuvem", options=cloud_options, index=cloud_options.index(selected_cloud))
    st.sidebar.markdown("---")

    st.sidebar.markdown("### Upload & Fontes")
    uploaded_files = st.sidebar.file_uploader(
        "Adicionar CSVs de custos", type=["csv"], accept_multiple_files=True, help="Envie um ou mais CSVs para armazenar no SQLite."
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Dataset ativo")
    if available_files:
        display_options = [f"{f.filename} ({f.cloud_provider})" for f in available_files]
        safe_index = min(selected_file_index, len(display_options) - 1)
        selected_label = st.sidebar.selectbox("Selecione o arquivo", options=display_options, index=safe_index)
        selected_index = display_options.index(selected_label)
        st.sidebar.caption(f"SQLite • {len(available_files)} arquivo(s) importado(s)")
    else:
        st.sidebar.info("Nenhum arquivo importado. Faça upload para iniciar.")
        selected_index = 0

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Filtros")
    default_services = selected_services or services
    if services:
        default_services = [service for service in default_services if service in services] or services
    else:
        default_services = []
    selected_services_filter = st.sidebar.multiselect(
        "Serviços acompanhados", options=services, default=default_services, help="Selecione quais serviços alimentarão KPIs e tabelas.", disabled=not services
    )

    if period_min and period_max:
        default_start, default_end = _safe_date_range(period_range, period_min, period_max)
        start_col, end_col = st.sidebar.columns(2)
        start_date = start_col.date_input(
            "Data inicial",
            value=default_start,
            min_value=period_min,
            max_value=period_max,
        )
        end_date = end_col.date_input(
            "Data final",
            value=default_end,
            min_value=period_min,
            max_value=period_max,
        )
        if start_date > end_date:
            st.sidebar.warning("Data final deve ser maior ou igual a data inicial.")
            start_date, end_date = end_date, start_date
        period_range_filter = (start_date, end_date)
    else:
        period_range_filter = None
        st.sidebar.caption("Datas indisponíveis para filtrar.")

    chart_options = metric_columns or ["Custos totais($)"]
    default_chart = chart_column or chart_options[0]
    chart_index = chart_options.index(default_chart) if default_chart in chart_options else 0
    chart_column_filter = st.sidebar.selectbox("Coluna para gráficos", options=chart_options, index=chart_index)

    return {
        "uploaded_files": uploaded_files,
        "selected_file_index": selected_index,
        "selected_services": selected_services_filter,
        "period_range": period_range_filter,
        "chart_column": chart_column_filter,
        "selected_cloud": cloud_choice,
    }


def _safe_date_range(period_range: Optional[Tuple[Optional[date], Optional[date]]], min_date: date, max_date: date) -> Tuple[date, date]:
    """Garante que o range de datas seja válido."""
    if not period_range or not all(period_range):
        return (min_date, max_date)
    start, end = period_range
    start = max(start, min_date) if start else min_date
    end = min(end, max_date) if end else max_date
    if start > end:
        start, end = min_date, max_date
    return (start, end)
