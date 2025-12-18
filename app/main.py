"""Aplicação principal FinOps AI Dashboard."""
from __future__ import annotations

from datetime import date
from typing import Optional, Tuple

import pandas as pd
import streamlit as st

from app.config import DB_PATH
from app.data.loaders import ImportedFile, import_csv_to_db, list_imported_files, load_dataset_from_db
from app.data.repositories import filter_dataframe
from app.infra.logging_config import setup_logging
from app.models.cost_model import DATE_COLUMN, TOTAL_COLUMN, build_cost_dataset, ensure_storage, get_service_columns
from app.services.analytics_service import get_kpi_summary
from app.ui import filters_sidebar, layout

# Configurar logging
setup_logging()


def main() -> None:
    """Função principal do aplicativo."""
    st.set_page_config(page_title="FinOps AI Dashboard", layout="wide", initial_sidebar_state="expanded")
    layout.inject_global_css()

    # Inicializar storage
    ensure_storage()

    # Listar arquivos importados
    imported_files = list_imported_files()
    cloud_options = ["AWS", "OCI"]
    selected_cloud = st.session_state.get("selected_cloud", cloud_options[0])
    selected_cloud_files = [f for f in imported_files if f.cloud_provider.upper() == selected_cloud.upper()]

    selected_index = st.session_state.get("selected_file_index", 0)
    if selected_cloud_files:
        selected_index = min(selected_index, len(selected_cloud_files) - 1)
    else:
        selected_index = 0

    # Carregar dataset
    dataset_df: Optional[pd.DataFrame] = None
    dataset_name = "Nenhum dataset selecionado"
    services: list[str] = []
    metric_columns: list[str] = []

    if selected_cloud_files:
        selected_file = selected_cloud_files[selected_index]
        dataset_df = load_dataset_from_db(selected_file.id)
        if dataset_df is not None:
            dataset_name = selected_file.filename
            dataset = build_cost_dataset(selected_file.filename, dataset_df, provider_hint=selected_file.cloud_provider)
            services = dataset.service_columns
            metric_columns = [TOTAL_COLUMN] + services

    # Sidebar
    stored_filters = st.session_state.get("sidebar_filters", {})
    period_min = None
    period_max = None
    if dataset_df is not None and DATE_COLUMN in dataset_df.columns:
        date_series = pd.to_datetime(dataset_df[DATE_COLUMN], errors="coerce").dropna()
        if not date_series.empty:
            period_min = date_series.min().date()
            period_max = date_series.max().date()

    sidebar_inputs = filters_sidebar.render_sidebar(
        available_files=selected_cloud_files,
        selected_file_index=selected_index,
        services=services,
        metric_columns=metric_columns,
        cloud_options=cloud_options,
        selected_cloud=selected_cloud,
        selected_services=stored_filters.get("services"),
        period_range=stored_filters.get("date_range"),
        period_min=period_min,
        period_max=period_max,
        chart_column=stored_filters.get("chart_column"),
    )

    # Processar uploads
    uploaded_files = sidebar_inputs.get("uploaded_files") or []
    if uploaded_files:
        for uploaded_file in uploaded_files:
            file_id, error = import_csv_to_db(uploaded_file, cloud_provider=sidebar_inputs.get("selected_cloud"))
            if error:
                st.sidebar.error(error)
            else:
                st.sidebar.success(f"Arquivo {uploaded_file.name} importado com sucesso!")
                st.rerun()

    # Atualizar índice selecionado
    new_index = sidebar_inputs.get("selected_file_index", selected_index)
    new_cloud = sidebar_inputs.get("selected_cloud", selected_cloud)
    if new_cloud != selected_cloud:
        st.session_state["selected_cloud"] = new_cloud
        st.session_state["selected_file_index"] = 0
        st.session_state["sidebar_filters"] = {}
        st.rerun()

    if new_index != selected_index:
        st.session_state["selected_file_index"] = new_index
        st.session_state["sidebar_filters"] = {}
        st.rerun()

    # Aplicar filtros
    filtered_df = dataset_df.copy() if dataset_df is not None else pd.DataFrame()
    selected_services = sidebar_inputs.get("selected_services") or services
    period_range = sidebar_inputs.get("period_range")
    chart_column = sidebar_inputs.get("chart_column") or TOTAL_COLUMN

    if not filtered_df.empty:
        filtered_df = filter_dataframe(filtered_df, date_range=period_range, services=selected_services)

    # Salvar filtros na sessão
    st.session_state["sidebar_filters"] = {
        "services": selected_services,
        "date_range": period_range,
        "chart_column": chart_column,
    }

    # Calcular KPIs
    if filtered_df.empty:
        kpi_summary = get_kpi_summary(pd.DataFrame(), selected_services)
    else:
        kpi_summary = get_kpi_summary(filtered_df, selected_services)

    # Renderizar UI
    period_label = _format_period_label(period_range) if period_range else "-"
    data_source_label = f"SQLite • {DB_PATH.name}"

    # Armazenar nome do dataset na sessão para uso em outros componentes
    st.session_state["dataset_name"] = dataset_name

    layout.render_header(dataset_name, data_source_label, period_label)
    layout.render_main_content(filtered_df, kpi_summary, selected_services, chart_column)


def _format_period_label(period_range: Optional[Tuple[date, date]]) -> str:
    """Formata label do período."""
    if not period_range:
        return "-"
    start, end = period_range
    if start and end:
        return f"{start.strftime('%b %Y')} - {end.strftime('%b %Y')}"
    if start:
        return f"A partir de {start.strftime('%b %Y')}"
    if end:
        return f"Até {end.strftime('%b %Y')}"
    return "-"


if __name__ == "__main__":
    main()
