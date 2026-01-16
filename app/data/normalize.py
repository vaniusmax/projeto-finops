"""Canonical normalization helpers for multi-cloud cost analysis."""
from __future__ import annotations

from typing import Dict, Iterable, Optional, Sequence

import pandas as pd

from app.models.cost_model import DATE_COLUMN, SERVICE_COLUMN, TOTAL_COLUMN

CANONICAL_COLUMNS: Sequence[str] = (
    "usage_date",
    "month",
    "cloud_provider",
    "account_scope",
    "account_name",
    "service_name",
    "service_category",
    "cost_amount",
    "currency",
    "region",
    "tags",
)


_COLUMN_ALIASES: Dict[str, tuple[str, ...]] = {
    "usage_date": (
        "usage_date",
        "usage_start_date",
        "billing_period_start",
        "Data",
        DATE_COLUMN,
        "Start",
        "start",
        "lineitem/intervalusagestart",
        "invoice_date",
        "competencia",
        "competência",
        "month",
    ),
    "service_name": (
        "service_name",
        "service",
        SERVICE_COLUMN,
        "product/service",
        "productname",
        "serviço",
        "produto",
        "produto_serviço",
        "lineitem/lineitemdescription",
    ),
    "cost_amount": (
        "cost_amount",
        TOTAL_COLUMN,
        "amount",
        "cost",
        "costusd",
        "unblendedcost",
        "netamount",
        "usage_cost",
        "valor",
    ),
    "account_scope": (
        "account_scope",
        "account_id",
        "aws_account_id",
        "payeraccountid",
        "linkedaccountid",
        "subscription_id",
        "subscriptionguid",
        "subscription",
        "compartment_id",
        "compartment",
        "tenancy",
    ),
    "account_name": (
        "account_name",
        "account",
        "accountdescription",
        "account friendly name",
        "subscription_name",
        "subscriptionfriendlyname",
        "compartmentname",
    ),
    "currency": (
        "currency",
        "currencycode",
        "currency_code",
        "billing_currency_code",
    ),
    "region": (
        "region",
        "awsregion",
        "product/region",
        "resource_location",
        "localizacao",
    ),
    "tags": (
        "tags",
        "resource_tags",
        "lineitem/usagetype",
        "lineitem/usageaccounttags",
    ),
}

_CATEGORY_KEYWORDS: Dict[str, tuple[str, ...]] = {
    "compute": ("ec2", "compute", "vm", "virtual machine", "eks", "lambda", "fargate", "oke", "instance", "containers"),
    "storage": ("s3", "storage", "ebs", "efs", "fsx", "glacier", "bucket", "object", "blob", "volume", "backup"),
    "network": ("transfer", "bandwidth", "network", "direct connect", "cloudfront", "cdn", "route 53", "vpc", "nat", "gateway"),
    "managed": ("rds", "database", "sql", "dynamodb", "aurora", "redis", "elasticache", "managed", "api gateway", "kubernetes", "queue"),
}

_DEFAULT_ACCOUNT_SCOPE = {
    "AWS": "aws_account",
    "OCI": "oci_compartment",
    "AZURE": "azure_subscription",
}


def normalize_costs(df: pd.DataFrame, cloud_provider: str) -> pd.DataFrame:
    """
    Normaliza um DataFrame de custos em colunas canônicas.

    Args:
        df: DataFrame original, possivelmente com colunas diferentes por provedor.
        cloud_provider: Nome do provedor (AWS|OCI|Azure).

    Returns:
        DataFrame no formato canônico definido em CANONICAL_COLUMNS.
    """

    cloud = (cloud_provider or "unknown").strip().upper()
    if df is None or df.empty:
        return pd.DataFrame(columns=CANONICAL_COLUMNS)

    working_df = df.copy()

    usage_date_series = pd.to_datetime(_get_column_values(working_df, "usage_date"), errors="coerce")
    service_series = _get_column_values(working_df, "service_name").fillna("Serviço não informado").astype(str)
    cost_series = pd.to_numeric(_get_column_values(working_df, "cost_amount"), errors="coerce").fillna(0.0)
    account_scope_series = _get_column_values(working_df, "account_scope").fillna(_DEFAULT_ACCOUNT_SCOPE.get(cloud, "multicloud_scope"))
    account_name_series = _get_column_values(working_df, "account_name")
    currency_series = _get_column_values(working_df, "currency").fillna("USD").astype(str)
    region_series = _get_column_values(working_df, "region")
    tags_series = _get_column_values(working_df, "tags")

    account_name_clean = account_name_series.where(account_name_series.notna(), None)
    region_clean = region_series.where(region_series.notna(), None)
    tags_clean = tags_series.where(tags_series.notna(), None)

    normalized = pd.DataFrame(
        {
            "usage_date": usage_date_series,
            "cloud_provider": cloud,
            "account_scope": account_scope_series.astype(str),
            "account_name": account_name_clean,
            "service_name": service_series,
            "cost_amount": cost_series.astype(float),
            "currency": currency_series,
            "region": region_clean,
            "tags": tags_clean,
        }
    )

    month_period = normalized["usage_date"].dt.to_period("M")
    normalized["month"] = month_period.astype(str)
    normalized.loc[normalized["usage_date"].isna(), "month"] = "Sem data"
    normalized["service_category"] = normalized["service_name"].apply(lambda name: categorize_service(name, cloud))

    normalized = normalized[list(CANONICAL_COLUMNS)]
    return normalized


def categorize_service(service_name: str, cloud_provider: str) -> str:
    """
    Classifica um serviço em categorias macro FinOps.

    Args:
        service_name: Nome livre do serviço.
        cloud_provider: Provedor atual (usado para heurísticas específicas).

    Returns:
        Categoria canônica (compute|storage|network|managed|other).
    """

    if not service_name:
        return "other"

    name = str(service_name).lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(keyword in name for keyword in keywords):
            return category

    if "data" in name or "analytics" in name or "insight" in name:
        return "managed"
    if "backup" in name or "log" in name:
        return "storage"
    if cloud_provider.upper() == "AZURE" and "sql" in name:
        return "managed"
    return "other"


def _get_column_values(df: pd.DataFrame, canonical_name: str) -> pd.Series:
    aliases = _COLUMN_ALIASES.get(canonical_name, ())
    available = _match_columns(df.columns, aliases)
    if available:
        return df[available]
    if canonical_name == "usage_date" and "month" in df.columns:
        return pd.to_datetime(df["month"], errors="coerce")
    return pd.Series([None] * len(df))


def _match_columns(columns: Iterable[str], candidates: Sequence[str]) -> Optional[str]:
    normalized_map = {str(col).strip().lower(): col for col in columns}
    for candidate in candidates:
        lower = candidate.strip().lower()
        if lower in normalized_map:
            return normalized_map[lower]
    return None

