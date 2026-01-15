"""Componentes de gráficos."""
from __future__ import annotations

from typing import List, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from app.models.cost_model import DATE_COLUMN, TOTAL_COLUMN, get_service_columns


def render_ranking_chart(table_ranking: pd.DataFrame) -> None:
    """Renderiza gráfico de ranking de custos (barras horizontais) com tooltips interativos."""
    if table_ranking.empty:
        st.info("Sem dados para exibir o ranking.")
        return

    ranking_sorted = table_ranking.sort_values("Custo", ascending=False)
    
    # Calcular altura baseada no número de serviços
    height = max(6, len(ranking_sorted) * 0.4) * 100  # Converter para pixels
    
    # Criar gráfico de barras horizontais com Plotly para ter tooltips interativos
    fig = go.Figure()
    
    # Gerar cores distintas para cada barra
    colors = px.colors.qualitative.Set3[:len(ranking_sorted)]
    
    fig.add_trace(
        go.Bar(
            y=ranking_sorted["Serviço"],
            x=ranking_sorted["Custo"],
            orientation="h",
            marker=dict(color=colors),
            hovertemplate="<b>%{y}</b><br>Custo: $%{x:,.2f}<extra></extra>",
            text=[f"${x:,.0f}" for x in ranking_sorted["Custo"]],
            textposition="outside",
        )
    )
    
    fig.update_layout(
        xaxis=dict(
            title="Custo ($)",
            tickformat="$,.0f",
            gridcolor="rgba(0,0,0,0.1)",
            showgrid=True,
        ),
        yaxis=dict(
            title="Serviço",
            autorange="reversed",  # Inverter para mostrar maior no topo
        ),
        height=height,
        margin=dict(l=20, r=20, t=20, b=20),
        showlegend=False,
    )
    
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_distribution_chart(table_percentual: pd.DataFrame, ranking_count: int = 0) -> None:
    """
    Renderiza gráfico de distribuição percentual (pizza).
    
    Args:
        table_percentual: DataFrame com dados percentuais
        ranking_count: Número de itens no ranking (para ajustar altura)
    """
    if table_percentual.empty:
        st.info("Sem dados para exibir a distribuição.")
        return

    percentual_sorted = table_percentual.sort_values("Percentual", ascending=False)
    top_10 = percentual_sorted.head(10)

    if len(percentual_sorted) > 10:
        outros_percentual = percentual_sorted.iloc[10:]["Percentual"].sum()
        outros_row = pd.DataFrame({"Serviço": ["Outros"], "Custo": [0], "Percentual": [outros_percentual]})
        pie_data = pd.concat([top_10, outros_row], ignore_index=True)
    else:
        pie_data = top_10

    # Calcular altura baseada no número de itens no ranking para manter a mesma dimensão
    # O gráfico de ranking usa figsize=(10, max(6, len * 0.4)) em polegadas
    # Converter para pixels: 1 polegada ≈ 100 pixels no Plotly
    if ranking_count > 0:
        ranking_height_inches = max(6, ranking_count * 0.4)
        plot_height = int(ranking_height_inches * 100)
    else:
        # Altura padrão se não soubermos o número de itens
        plot_height = 600  # Equivalente a 6 polegadas
    
    fig = px.pie(pie_data, values="Percentual", names="Serviço", hole=0.4, title="")
    fig.update_traces(hovertemplate="<b>%{label}</b><br>Percentual: %{percent}<extra></extra>", textinfo="none")
    fig.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0), height=plot_height)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_evolution_chart(monthly_totals: pd.DataFrame, chart_column: str) -> None:
    """Renderiza gráfico de evolução mensal."""
    if monthly_totals.empty or chart_column not in monthly_totals.columns:
        st.info("Sem dados para exibir a evolução mensal.")
        return

    evolution_df = monthly_totals.set_index("Competência")[[chart_column]]
    st.line_chart(evolution_df, height=420)


def render_monthly_bar_chart(cost_df: pd.DataFrame, services: Optional[List[str]] = None, chart_column: Optional[str] = None) -> None:
    """
    Renderiza gráfico de barras empilhadas com total gasto em cada mês.
    
    Comportamento:
    - Se apenas um serviço estiver selecionado (ou chart_column for um serviço específico),
      mostra apenas esse serviço ao longo dos meses.
    - Se múltiplos serviços ou "Custos Totais" estiverem selecionados,
      mostra gráfico empilhado com os 9 principais serviços e "Outros".
    
    Args:
        cost_df: DataFrame de custos (já filtrado)
        services: Lista de serviços para incluir (None = todos os serviços disponíveis)
        chart_column: Coluna selecionada para gráficos (pode ser TOTAL_COLUMN ou um serviço específico)
    """
    if cost_df.empty:
        st.info("Sem dados para exibir o total mensal.")
        return

    # Verificar se há coluna de data
    if DATE_COLUMN not in cost_df.columns:
        st.info("Sem coluna de data para exibir.")
        return

    # Preparar dados: converter data e filtrar
    df = cost_df.copy()
    df[DATE_COLUMN] = pd.to_datetime(df[DATE_COLUMN], errors="coerce")
    df = df.dropna(subset=[DATE_COLUMN])

    if df.empty:
        st.info("Sem dados válidos para exibir.")
        return

    # Determinar modo de exibição baseado no filtro
    # Se chart_column for um serviço específico (não TOTAL_COLUMN), mostrar apenas esse serviço
    show_single_service = False
    single_service_col = None
    
    if chart_column and chart_column != TOTAL_COLUMN:
        if chart_column in df.columns:
            show_single_service = True
            single_service_col = chart_column
    elif services and len(services) == 1:
        if services[0] in df.columns:
            show_single_service = True
            single_service_col = services[0]
    
    # Modo: gráfico empilhado completo
    if not show_single_service:
        # Identificar colunas de serviços disponíveis
        available_service_cols = [col for col in (services or get_service_columns(df)) if col in df.columns]
        
        if not available_service_cols:
            st.info("Sem colunas de serviços para exibir.")
            return
    else:
        # Modo de serviço único: usar apenas a coluna do serviço selecionado
        available_service_cols = [single_service_col]

    # Agregar por mês
    df["Mês"] = df[DATE_COLUMN].dt.to_period("M")
    
    # Modo de serviço único: exibir apenas esse serviço
    if show_single_service:
        monthly_data = []
        for month in df["Mês"].unique():
            month_df = df[df["Mês"] == month]
            month_str = str(month)
            
            total = month_df[single_service_col].sum() if single_service_col in month_df.columns else 0
            if pd.notna(total):
                monthly_data.append({
                    "Mês": month_str,
                    single_service_col: float(total)
                })
        
        if not monthly_data:
            st.info("Sem dados para exibir.")
            return
        
        chart_df = pd.DataFrame(monthly_data)
        chart_df = chart_df.fillna(0)
        
        # Criar gráfico de barras simples (não empilhado) para serviço único
        plot_data = []
        for _, row in chart_df.iterrows():
            month = row["Mês"]
            value = float(row[single_service_col]) if pd.notna(row[single_service_col]) else 0.0
            if value > 0:
                plot_data.append({
                    "Mês": month,
                    "Serviço": single_service_col.replace("($)", "").strip(),
                    "Custo": value
                })
        
        if not plot_data:
            st.info("Sem dados para exibir.")
            return
        
        plot_df = pd.DataFrame(plot_data)
        plot_df["Mês"] = pd.to_datetime(plot_df["Mês"]).dt.strftime("%Y-%m")
        months_sorted = sorted(plot_df["Mês"].unique())
        plot_df["Mês"] = pd.Categorical(plot_df["Mês"], categories=months_sorted, ordered=True)
        plot_df = plot_df.sort_values("Mês")
        
        # Criar gráfico de barras simples
        fig = px.bar(
            plot_df,
            x="Mês",
            y="Custo",
            title="",
            labels={"Custo": "Custo ($)", "Mês": "Mês"},
            color="Serviço",
        )
        
        fig.update_traces(
            hovertemplate="<b>%{fullData.name}</b><br>Mês: %{x}<br>Custo: $%{y:,.2f}<extra></extra>",
        )
        
        fig.update_layout(
            height=400,
            xaxis=dict(title="Mês", tickangle=-45),
            yaxis=dict(title="Custo ($)", tickformat="$,.0f"),
            margin=dict(l=20, r=20, t=20, b=80),
            showlegend=False,
            barmode="group",
        )
        
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        return
    
    # Modo empilhado: calcular totais por serviço por mês
    monthly_data = []
    for month in df["Mês"].unique():
        month_df = df[df["Mês"] == month]
        month_str = str(month)
        
        service_totals = {"Mês": month_str}
        for service_col in available_service_cols:
            if service_col in month_df.columns:
                total = month_df[service_col].sum()
                if pd.notna(total) and total > 0:
                    service_totals[service_col] = float(total)
        
        # Adicionar mesmo se não houver serviços (para manter todos os meses)
        monthly_data.append(service_totals)

    if not monthly_data:
        st.info("Sem dados para exibir.")
        return

    # Criar DataFrame com totais por mês e serviço
    chart_df = pd.DataFrame(monthly_data)
    chart_df = chart_df.fillna(0)

    # Calcular totais por serviço em todo o período para identificar os top 9
    service_totals_period = {}
    for service_col in available_service_cols:
        if service_col in chart_df.columns:
            service_totals_period[service_col] = chart_df[service_col].sum()

    # Ordenar serviços por total e pegar os top 9
    sorted_services = sorted(service_totals_period.items(), key=lambda x: x[1], reverse=True)
    top_9_services = [service for service, _ in sorted_services[:9]]

    # Preparar dados para o gráfico empilhado
    plot_data = []
    for _, row in chart_df.iterrows():
        month = row["Mês"]
        others_total = 0
        
        # Adicionar os top 9 serviços
        for service in top_9_services:
            if service in row:
                plot_data.append({
                    "Mês": month,
                    "Serviço": service.replace("($)", "").strip(),
                    "Custo": float(row[service]) if pd.notna(row[service]) else 0.0
                })
        
        # Calcular "Outros" (todos os serviços não incluídos nos top 9)
        for service_col in available_service_cols:
            if service_col not in top_9_services and service_col in row:
                if pd.notna(row[service_col]):
                    others_total += float(row[service_col])
        
        if others_total > 0:
            plot_data.append({
                "Mês": month,
                "Serviço": "Outros",
                "Custo": others_total
            })

    if not plot_data:
        st.info("Sem dados para exibir.")
        return

    plot_df = pd.DataFrame(plot_data)
    
    # Ordenar meses
    plot_df["Mês"] = pd.to_datetime(plot_df["Mês"]).dt.strftime("%Y-%m")
    months_sorted = sorted(plot_df["Mês"].unique())
    plot_df["Mês"] = pd.Categorical(plot_df["Mês"], categories=months_sorted, ordered=True)
    plot_df = plot_df.sort_values("Mês")

    # Criar gráfico de barras empilhadas
    fig = px.bar(
        plot_df,
        x="Mês",
        y="Custo",
        color="Serviço",
        title="",
        labels={"Custo": "Custo ($)", "Mês": "Mês"},
    )
    
    # Personalizar cores e tooltips
    fig.update_traces(
        hovertemplate="<b>%{fullData.name}</b><br>Mês: %{x}<br>Custo: $%{y:,.2f}<extra></extra>",
    )
    
    fig.update_layout(
        height=400,
        xaxis=dict(title="Mês", tickangle=-45),
        yaxis=dict(title="Custo Total ($)", tickformat="$,.0f"),
        margin=dict(l=20, r=20, t=20, b=80),
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02,
            font=dict(size=10)
        ),
        barmode="stack",
    )
    
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
