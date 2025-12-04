"""Serviço de detecção de anomalias em custos."""
from __future__ import annotations

from typing import List, Optional

import numpy as np
import pandas as pd

from app.data.models import AnomalyDetection
from app.data.repositories import get_monthly_totals
from app.infra.cache import cached
from app.infra.llm_client import LLMClient


@cached
def detect_anomalies(
    monthly_service_costs: pd.DataFrame, method: str = "zscore", threshold: float = 3.0
) -> List[AnomalyDetection]:
    """
    Detecta anomalias em custos mensais por serviço.

    Args:
        monthly_service_costs: DataFrame com colunas Competência e colunas de serviços
        method: Método de detecção ('zscore' ou 'isolation_forest')
        threshold: Threshold para z-score (padrão: 3.0)

    Returns:
        Lista de AnomalyDetection
    """
    if monthly_service_costs.empty or "Competência" not in monthly_service_costs.columns:
        return []

    anomalies = []

    # Colunas de serviços (todas exceto Competência)
    service_columns = [col for col in monthly_service_costs.columns if col != "Competência"]

    for service_col in service_columns:
        service_data = monthly_service_costs[["Competência", service_col]].copy()
        service_data = service_data.dropna()

        if len(service_data) < 3:  # Precisa de pelo menos 3 pontos
            continue

        values = service_data[service_col].values

        if method == "isolation_forest":
            anomaly_flags = _detect_with_isolation_forest(values)
        else:  # zscore
            anomaly_flags = _detect_with_zscore(values, threshold)

        # Criar detecções
        for idx, (date, cost, is_anomaly) in enumerate(
            zip(service_data["Competência"], service_data[service_col], anomaly_flags)
        ):
            if is_anomaly:
                score = _calculate_anomaly_score(values, idx)
                explanation = _explain_anomaly(date, service_col, cost, values, score)

                anomalies.append(
                    AnomalyDetection(
                        date=pd.to_datetime(date).date() if isinstance(date, str) else date,
                        service=service_col,
                        cost=float(cost),
                        is_anomaly=True,
                        anomaly_score=float(score),
                        explanation=explanation,
                    )
                )

    return anomalies


def _detect_with_zscore(values: np.ndarray, threshold: float = 3.0) -> np.ndarray:
    """Detecção usando z-score."""
    mean = np.mean(values)
    std = np.std(values)

    if std == 0:
        return np.zeros(len(values), dtype=bool)

    z_scores = np.abs((values - mean) / std)
    return z_scores > threshold


def _detect_with_isolation_forest(values: np.ndarray) -> np.ndarray:
    """Detecção usando Isolation Forest."""
    try:
        from sklearn.ensemble import IsolationForest

        # Reshape para formato esperado
        X = values.reshape(-1, 1)

        model = IsolationForest(contamination=0.1, random_state=42)
        predictions = model.fit_predict(X)

        # -1 = anomalia, 1 = normal
        return predictions == -1
    except ImportError:
        # Fallback para z-score se sklearn não disponível
        return _detect_with_zscore(values)


def _calculate_anomaly_score(values: np.ndarray, idx: int) -> float:
    """Calcula score de anomalia (0-1, onde 1 é mais anômalo)."""
    mean = np.mean(values)
    std = np.std(values)

    if std == 0:
        return 0.0

    z_score = abs((values[idx] - mean) / std)
    # Normalizar para 0-1
    return min(1.0, z_score / 5.0)


def _explain_anomaly(date, service: str, cost: float, values: np.ndarray, score: float) -> str:
    """Gera explicação da anomalia usando LLM."""
    mean = np.mean(values)
    std = np.std(values)
    deviation = ((cost - mean) / mean * 100) if mean > 0 else 0

    context = f"""
Anomalia detectada em custos:
- Data: {date}
- Serviço: {service}
- Custo: ${cost:,.2f}
- Média histórica: ${mean:,.2f}
- Desvio: {deviation:+.1f}%
- Score de anomalia: {score:.2f}
"""

    system_prompt = """Você é um analista FinOps. Explique anomalias de custo de forma clara e objetiva em português.
Mencione possíveis causas e recomendações breves."""

    llm_client = LLMClient()
    explanation = llm_client.generate(system_prompt, f"Explique esta anomalia:\n{context}", temperature=0.5)

    return explanation if explanation and not explanation.startswith("⚠️") else f"Anomalia detectada: custo {deviation:+.1f}% acima da média"


