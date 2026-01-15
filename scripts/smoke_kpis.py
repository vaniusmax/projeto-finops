"""Smoke test focusing on KPI daily average calculations."""
from __future__ import annotations

from datetime import date, timedelta
from math import isclose

import pandas as pd

from app.services import multicloud_analytics as mc
from app.services.date_window import compute_date_window


def build_df(total_cost: float, start: date, days: int, rows: int) -> pd.DataFrame:
    if rows <= 1:
        usage_dates = [pd.Timestamp(start)]
        values = [total_cost]
    else:
        end = start + timedelta(days=days - 1)
        usage_dates = pd.to_datetime([start, end]) if rows == 2 else pd.date_range(start, periods=rows, freq="D")
        values = [total_cost / rows] * rows
    return pd.DataFrame(
        {
            "usage_date": usage_dates,
            "cost_amount": values,
            "cloud_provider": ["AWS"] * rows,
            "service_name": ["EC2"] * rows,
        }
    )


def main() -> None:
    total_cost = 66830.57
    days = 30
    start = date(2025, 1, 1)
    period = (start, start + timedelta(days=days - 1))

    df_daily = build_df(total_cost, start, days=days, rows=days)
    kpis_daily = mc.get_kpis(df_daily, period, period_days=days)

    df_sparse = build_df(total_cost, start, days=days, rows=2)
    kpis_sparse = mc.get_kpis(df_sparse, period, period_days=days)

    expected_avg = round(total_cost / days, 2)
    assert isclose(kpis_daily["avg_daily"], expected_avg, rel_tol=1e-9)
    assert isclose(kpis_sparse["avg_daily"], expected_avg, rel_tol=1e-9)
    print("Smoke KPIs OK", kpis_daily["avg_daily"])  # noqa: T201

    # Monthly aggregated case (6 meses)
    monthly_costs = [20678.40, 18884.92, 18954.13, 22435.84, 15452.05, 22561.25]
    df_monthly = pd.DataFrame(
        {
            "usage_date": pd.date_range("2025-07-01", periods=len(monthly_costs), freq="MS"),
            "cost_amount": monthly_costs,
            "cloud_provider": ["AWS"] * len(monthly_costs),
            "service_name": ["EC2"] * len(monthly_costs),
        }
    )
    start_date, end_date, days_count = compute_date_window("6m", df_monthly["usage_date"])
    assert days_count == 184
    kpis_monthly = mc.get_kpis(df_monthly, (start_date, end_date), period_days=days_count)
    expected_semester_avg = round(sum(monthly_costs) / days_count, 2)
    assert isclose(kpis_monthly["avg_daily"], expected_semester_avg, rel_tol=1e-9)
    print("Monthly window OK", kpis_monthly["avg_daily"])  # noqa: T201


if __name__ == "__main__":
    main()
