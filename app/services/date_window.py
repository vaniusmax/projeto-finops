"""Shared helpers to compute date windows for FinOps dashboards."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional, Tuple

import pandas as pd
from dateutil.relativedelta import relativedelta


def compute_date_window(
    period_key: str,
    usage_dates: pd.Series,
    custom_range: Optional[Tuple[date, date]] = None,
) -> tuple[Optional[date], Optional[date], Optional[int]]:
    """
    Calcula (start_date, end_date, days_count) para o período informado.

    Args:
        period_key: 30d|3m|6m|Custom
        usage_dates: Series com datas disponíveis
        custom_range: quando period_key == Custom
    """

    normalized = pd.to_datetime(usage_dates, errors="coerce").dropna()

    period_key = (period_key or "3m").lower()
    if period_key == "custom" and custom_range:
        start, end = custom_range
        if start and end:
            if start > end:
                start, end = end, start
            days = (end - start).days + 1
            return start, end, max(days, 1)
        return start, end, None

    if normalized.empty:
        return None, None, None

    end_anchor = normalized.max().date()

    if period_key == "30d":
        end_date = end_anchor
        start_date = end_date - timedelta(days=29)
    elif period_key == "6m":
        start_date, end_date = _calendar_month_window(end_anchor, months=6)
    else:  # default inclui 3m
        start_date, end_date = _calendar_month_window(end_anchor, months=3)

    days_count = (end_date - start_date).days + 1
    return start_date, end_date, days_count


def _calendar_month_window(end_date_ref: date, months: int) -> tuple[date, date]:
    """Retorna o range cobrindo `months` inteiros até o mês de end_date_ref."""

    end_month_first = end_date_ref.replace(day=1)
    start_month = end_month_first - relativedelta(months=months - 1)
    start_date = start_month
    end_date = _end_of_month(end_date_ref)
    return start_date, end_date


def _end_of_month(anchor: date) -> date:
    next_month = anchor.replace(day=28) + timedelta(days=4)
    return next_month - timedelta(days=next_month.day)
