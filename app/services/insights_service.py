"""Serviço de geração de insights automáticos em linguagem natural."""
from __future__ import annotations

from typing import Dict, Optional

import pandas as pd

from app.infra.cache import cached
from app.infra.llm_client import LLMClient
from app.services.analytics_service import get_kpi_summary, get_percentual_distribution_by_service


@cached
def generate_insights(cost_df: pd.DataFrame, kpi_summary: Optional[Dict] = None) -> str:
    """
    Gera insights automáticos em linguagem natural sobre os custos.

    Args:
        cost_df: DataFrame de custos filtrado
        kpi_summary: Dict com KPIs (opcional, será calculado se não fornecido)

    Returns:
        Texto com insights em português
    """
    if cost_df.empty:
        return "⚠️ Sem dados disponíveis para gerar insights."

    # Calcular KPIs se não fornecidos
    if kpi_summary is None:
        kpi = get_kpi_summary(cost_df)
        kpi_summary = kpi.dict()

    # Calcular distribuição percentual
    distribution = get_percentual_distribution_by_service(cost_df)
    top_services = distribution.head(5) if not distribution.empty else pd.DataFrame()

    # Calcular variação mensal se houver coluna de data
    monthly_variation = ""
    if "Serviço" in cost_df.columns:  # DATE_COLUMN
        try:
            monthly = cost_df.groupby(cost_df["Serviço"].dt.to_period("M")).sum()
            if len(monthly) > 1:
                last_month = monthly.iloc[-1].sum()
                prev_month = monthly.iloc[-2].sum()
                if prev_month > 0:
                    variation = ((last_month - prev_month) / prev_month) * 100
                    monthly_variation = f"Variação mês a mês: {variation:+.1f}%"
        except Exception:
            pass

    # Montar contexto para o LLM
    context = f"""
Dados de custos para análise:
- Custo total: ${kpi_summary.get('total_cost', 0):,.2f}
- Custo médio: ${kpi_summary.get('average_cost', 0):,.2f}
- Custo máximo: ${kpi_summary.get('max_cost', 0):,.2f}
- Custo mínimo: ${kpi_summary.get('min_cost', 0):,.2f}
- Mês de maior gasto: {kpi_summary.get('peak_month', 'N/A')}
- Mês de menor gasto: {kpi_summary.get('lowest_month', 'N/A')}
- Serviço mais caro: {kpi_summary.get('peak_service', 'N/A')}
- Serviço mais barato: {kpi_summary.get('lowest_service', 'N/A')}
{monthly_variation}

Top 5 serviços por custo:
"""
    if not top_services.empty:
        for idx, row in top_services.iterrows():
            context += f"- {row['Serviço']}: ${row['Custo']:,.2f} ({row['Percentual']:.1f}%)\n"

    system_prompt = """Você é um analista FinOps experiente. Gere insights executivos em português brasileiro sobre custos de cloud.
Seja objetivo, use linguagem gerencial e destaque pontos importantes para tomada de decisão.
Estruture com: parágrafo inicial de resumo, bullet points com destaques, e seção "Riscos e Oportunidades"."""

    user_prompt = f"""Analise os seguintes dados de custos e gere um resumo executivo:

{context}

Gere insights focados em:
1. Resumo do período
2. Principais destaques (crescimento, redução, serviços dominantes)
3. Riscos e oportunidades de otimização
"""

    llm_client = LLMClient()
    return llm_client.generate(system_prompt, user_prompt, temperature=0.7)


