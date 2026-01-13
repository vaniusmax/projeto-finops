"""Serviço de geração de recomendações de otimização FinOps."""
from __future__ import annotations

from typing import Dict, List

import pandas as pd

from app.data.schemas import Recommendation
from app.data.repositories import get_percentual_distribution, get_service_totals
from app.infra.cache import cached
from app.infra.llm_client import LLMClient


@cached
def generate_recommendations(aggregated_data: Dict | pd.DataFrame) -> List[Recommendation]:
    """
    Gera recomendações de otimização FinOps.

    Args:
        aggregated_data: Dict com dados agregados ou DataFrame de custos

    Returns:
        Lista de Recommendation
    """
    recommendations = []

    # Se recebeu DataFrame, calcular agregações
    if isinstance(aggregated_data, pd.DataFrame):
        if aggregated_data.empty:
            return []

        service_totals = get_service_totals(aggregated_data)
        distribution = get_percentual_distribution(aggregated_data)
        total_cost = service_totals.sum()
    else:
        service_totals = aggregated_data.get("service_totals", pd.Series())
        distribution = aggregated_data.get("distribution", pd.DataFrame())
        total_cost = aggregated_data.get("total_cost", 0.0)

    if service_totals.empty:
        return []

    # Regra 1: RDS domina custos
    rds_services = [s for s in service_totals.index if "RDS" in str(s) or "Relational Database" in str(s)]
    if rds_services:
        rds_total = sum(service_totals[s] for s in rds_services if s in service_totals.index)
        rds_percent = (rds_total / total_cost * 100) if total_cost > 0 else 0

        if rds_percent > 20:  # Mais de 20% do total
            recommendations.append(
                Recommendation(
                    title="Otimizar RDS com Reserved Instances",
                    impact="alto",
                    estimated_saving_percent=20.0,
                    description=_generate_rds_recommendation(rds_total, rds_percent),
                    service="RDS",
                    category="reserved_instances",
                )
            )

    # Regra 2: S3-Standard com muitos dados antigos
    s3_services = [s for s in service_totals.index if "S3" in str(s) and "Glacier" not in str(s)]
    if s3_services:
        s3_total = sum(service_totals[s] for s in s3_services if s in service_totals.index)
        s3_percent = (s3_total / total_cost * 100) if total_cost > 0 else 0

        if s3_percent > 15:
            recommendations.append(
                Recommendation(
                    title="Otimizar armazenamento S3 com lifecycle policies",
                    impact="medio",
                    estimated_saving_percent=30.0,
                    description=_generate_s3_recommendation(s3_total, s3_percent),
                    service="S3",
                    category="storage_optimization",
                )
            )

    # Regra 3: Support Business muito alto
    support_services = [s for s in service_totals.index if "Support" in str(s)]
    if support_services:
        support_total = sum(service_totals[s] for s in support_services if s in service_totals.index)
        support_percent = (support_total / total_cost * 100) if total_cost > 0 else 0

        if support_percent > 5:
            recommendations.append(
                Recommendation(
                    title="Revisar nível de suporte AWS",
                    impact="medio",
                    estimated_saving_percent=50.0,
                    description=f"O custo de suporte ({support_percent:.1f}% do total) pode ser otimizado revisando o nível necessário.",
                    service="Support",
                    category="support_optimization",
                )
            )

    # Regra 4: EC2 sem otimização
    ec2_services = [s for s in service_totals.index if "EC2" in str(s)]
    if ec2_services:
        ec2_total = sum(service_totals[s] for s in ec2_services if s in service_totals.index)
        ec2_percent = (ec2_total / total_cost * 100) if total_cost > 0 else 0

        if ec2_percent > 25:
            recommendations.append(
                Recommendation(
                    title="Otimizar instâncias EC2",
                    impact="alto",
                    estimated_saving_percent=15.0,
                    description=_generate_ec2_recommendation(ec2_total, ec2_percent),
                    service="EC2",
                    category="compute_optimization",
                )
            )

    # Regra 5: Serviço dominante (>40% do total)
    if not distribution.empty:
        top_service = distribution.iloc[0]
        if top_service["Percentual"] > 40:
            recommendations.append(
                Recommendation(
                    title=f"Revisar concentração de custos em {top_service['Serviço']}",
                    impact="alto",
                    estimated_saving_percent=10.0,
                    description=f"O serviço {top_service['Serviço']} representa {top_service['Percentual']:.1f}% do total. Considere diversificar ou otimizar.",
                    service=top_service["Serviço"],
                    category="cost_concentration",
                )
            )

    return recommendations


def _generate_rds_recommendation(rds_total: float, rds_percent: float) -> str:
    """Gera descrição detalhada para recomendação RDS."""
    llm_client = LLMClient()
    prompt = f"""Gere uma recomendação FinOps em português sobre otimização de RDS.
RDS representa {rds_percent:.1f}% do custo total (${rds_total:,.2f}).
Mencione Reserved Instances, Savings Plans e right-sizing."""
    return llm_client.generate(
        "Você é um consultor FinOps. Seja objetivo e prático.", prompt, temperature=0.5
    ) or f"RDS representa {rds_percent:.1f}% dos custos. Considere Reserved Instances para economizar até 40%."


def _generate_s3_recommendation(s3_total: float, s3_percent: float) -> str:
    """Gera descrição detalhada para recomendação S3."""
    llm_client = LLMClient()
    prompt = f"""Gere uma recomendação FinOps em português sobre otimização de S3.
S3 representa {s3_percent:.1f}% do custo total (${s3_total:,.2f}).
Mencione lifecycle policies, S3-IA e Glacier."""
    return llm_client.generate(
        "Você é um consultor FinOps. Seja objetivo e prático.", prompt, temperature=0.5
    ) or f"S3 representa {s3_percent:.1f}% dos custos. Configure lifecycle policies para mover dados antigos para S3-IA ou Glacier."


def _generate_ec2_recommendation(ec2_total: float, ec2_percent: float) -> str:
    """Gera descrição detalhada para recomendação EC2."""
    llm_client = LLMClient()
    prompt = f"""Gere uma recomendação FinOps em português sobre otimização de EC2.
EC2 representa {ec2_percent:.1f}% do custo total (${ec2_total:,.2f}).
Mencione Reserved Instances, Savings Plans, Spot Instances e right-sizing."""
    return llm_client.generate(
        "Você é um consultor FinOps. Seja objetivo e prático.", prompt, temperature=0.5
    ) or f"EC2 representa {ec2_percent:.1f}% dos custos. Considere Reserved Instances ou Savings Plans para economizar."

