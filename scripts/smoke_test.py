"""Smoke test para a camada de normalização e agregações multicloud."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.data.normalize import CANONICAL_COLUMNS, normalize_costs
from app.services import multicloud_analytics as mc


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    sample_file = project_root / "cost_last_6_months_by_service.csv"
    if not sample_file.exists():
        raise SystemExit(f"Arquivo exemplo não encontrado em {sample_file}")

    raw_df = pd.read_csv(sample_file)
    normalized_df = normalize_costs(raw_df, "AWS")

    print("Normalização")
    print(f"Colunas: {list(normalized_df.columns)}")
    print(f"Registros: {len(normalized_df)}")
    missing_cols = [col for col in CANONICAL_COLUMNS if col not in normalized_df.columns]
    if missing_cols:
        raise SystemExit(f"Colunas canônicas ausentes: {missing_cols}")

    kpis = mc.get_kpis(normalized_df)
    monthly = mc.get_monthly_trend(normalized_df)
    top_services = mc.get_top_services(normalized_df, n=5)

    print("\nKPIs:", kpis)
    print(f"Tendência mensal: {monthly.shape}")
    print(f"Top serviços: {top_services[['service_name', 'cost_amount']].head()}")  # noqa: T201


if __name__ == "__main__":
    main()
