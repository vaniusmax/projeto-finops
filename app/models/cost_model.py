"""Domain-specific helpers for cost dashboards (normalization, stats, rankings)."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import re
from typing import Dict, Iterable, List, Optional, Sequence

import pandas as pd

from app.models import db


DATE_COLUMN = "Serviço"  # Prompt requirement: field interpreted as data base para filtros
TOTAL_COLUMN = "Custos totais($)"

COST_COLUMNS: List[str] = [
    "Serviço",
    "Relational Database Service($)",
    "Redshift($)",
    "S3($)",
    "Tax($)",
    "EC2-Instâncias($)",
    "Glue($)",
    "VPC($)",
    "EC2-Outros($)",
    "Support (Business)($)",
    "Direct Connect($)",
    "CloudWatch($)",
    "Athena($)",
    "DynamoDB($)",
    "SNS($)",
    "SQS($)",
    "KMS($)",
    "Elastic Load Balancing($)",
    "S3-Glacier($)",
    "ECR($)",
    "ECS($)",
    "Lambda($)",
    "API Gateway($)",
    "Route 53($)",
    "Transfer($)",
    "CloudTrail($)",
    "IAM($)",
    "Guard Duty($)",
    "Keyspaces($)",
    "Compute Optimizer($)",
    "Secrets Manager($)",
    "SES($)",
    "Backup($)",
    "Detective($)",
    "Inspector($)",
    "RDS-Outros($)",
    "FSx($)",
    "EFS($)",
    "Config($)",
    "Resource Groups Tagging($)",
    "Systems Manager($)",
    "Megatron($)",
    "IAM Identity Center($)",
    "CloudWatch Logs($)",
    "CloudShell($)",
    "Organization($)",
    "Resource Explorer($)",
    "CloudWatch Events($)",
    "WAF($)",
    "CloudFormation($)",
    "CodeArtifact($)",
    "Certificate Manager($)",
    "Custos totais($)",
]

SERVICE_COST_COLUMNS = [column for column in COST_COLUMNS if column not in {DATE_COLUMN, TOTAL_COLUMN}]
NUMERIC_COLUMNS = SERVICE_COST_COLUMNS + [TOTAL_COLUMN]


def _normalize_db_column(name: str) -> str:
    """Convert column names to safe snake_case identifiers for SQLite."""

    slug = re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_").lower()
    slug = re.sub(r"_+", "_", slug)
    slug = slug or "col"
    return slug


def _build_db_column_map(columns: Sequence[str]) -> Dict[str, str]:
    """Ensure deterministic mapping from CSV columns to DB columns."""

    mapping: Dict[str, str] = {}
    used: Dict[str, int] = {}
    for column in columns:
        base = _normalize_db_column(column)
        candidate = base
        counter = 1
        while candidate in used:
            counter += 1
            candidate = f"{base}_{counter}"
        mapping[column] = candidate
        used[candidate] = 1
    return mapping


COLUMN_TO_DB = _build_db_column_map(COST_COLUMNS)
DB_TO_COLUMN = {value: key for key, value in COLUMN_TO_DB.items()}

DB_COLUMN_TYPES = OrderedDict(
    (
        COLUMN_TO_DB[column],
        "TEXT" if column == DATE_COLUMN else "REAL NOT NULL DEFAULT 0",
    )
    for column in COST_COLUMNS
)

DB_COLUMN_ORDER = list(DB_COLUMN_TYPES.keys())


@dataclass
class CostDataset:
    """Normalized dataset plus metadata ready for business logic."""

    name: str
    dataframe: pd.DataFrame
    numeric_columns: List[str]
    service_columns: List[str]
    has_dates: bool
    file_id: Optional[int] = None


def normalize_cost_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure columns exist, strip names and coerce numerics for all cost fields."""

    normalized = df.copy()
    normalized.columns = [str(col).strip() for col in normalized.columns]

    for column in COST_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = 0

    for column in NUMERIC_COLUMNS:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce").fillna(0.0)

    normalized[DATE_COLUMN] = pd.to_datetime(normalized[DATE_COLUMN], errors="coerce")
    return normalized


def build_cost_dataset(name: str, df: pd.DataFrame) -> CostDataset:
    normalized = normalize_cost_dataframe(df)
    service_columns = [column for column in SERVICE_COST_COLUMNS if column in normalized.columns]
    numeric_columns = service_columns + ([TOTAL_COLUMN] if TOTAL_COLUMN in normalized.columns else [])
    has_dates = normalized[DATE_COLUMN].notna().any()
    return CostDataset(
        name=name,
        dataframe=normalized,
        numeric_columns=numeric_columns,
        service_columns=service_columns,
        has_dates=has_dates,
    )


def ensure_storage() -> None:
    """Initialize SQLite tables for files and normalized costs."""

    db.initialize_database(DB_COLUMN_TYPES)


def persist_cost_dataframe(file_id: int, df: pd.DataFrame) -> None:
    """Store all rows from the normalized dataframe into the costs table."""

    if df.empty:
        return

    serializable = df[COST_COLUMNS].copy()
    if DATE_COLUMN in serializable.columns:
        serializable[DATE_COLUMN] = serializable[DATE_COLUMN].apply(
            lambda value: value.strftime("%Y-%m-%d") if pd.notna(value) else None
        )

    rows = list(serializable.itertuples(index=False, name=None))
    db_rows = [
        tuple(_serialize_value(column_name, value) for column_name, value in zip(COST_COLUMNS, row))
        for row in rows
    ]
    db.insert_cost_rows(file_id=file_id, columns=DB_COLUMN_ORDER, rows=db_rows)


def fetch_cost_dataframe(file_id: int) -> pd.DataFrame:
    """Retrieve all cost rows associated with a file_id."""

    rows = db.fetch_cost_rows(file_id=file_id, columns=DB_COLUMN_ORDER)
    if not rows:
        return pd.DataFrame(columns=COST_COLUMNS)

    records = []
    for row in rows:
        record = {DB_TO_COLUMN[column]: row[column] for column in DB_COLUMN_ORDER}
        records.append(record)
    dataframe = pd.DataFrame(records)
    if DATE_COLUMN in dataframe.columns:
        dataframe[DATE_COLUMN] = pd.to_datetime(dataframe[DATE_COLUMN], errors="coerce")
    for column in NUMERIC_COLUMNS:
        if column in dataframe.columns:
            dataframe[column] = pd.to_numeric(dataframe[column], errors="coerce").fillna(0.0)
    return dataframe


def _serialize_value(column_name: str, value):
    """Adapt pandas values to SQLite friendly types."""

    if column_name == DATE_COLUMN:
        return value if value else None
    return float(value) if value is not None else 0.0


def aggregate_service_totals(df: pd.DataFrame, services: Optional[Sequence[str]] = None) -> pd.Series:
    columns = list(services) if services else [col for col in SERVICE_COST_COLUMNS if col in df.columns]
    if not columns:
        return pd.Series(dtype=float)
    totals = df[columns].sum().sort_values(ascending=False)
    return totals


def calculate_overall_metrics(df: pd.DataFrame) -> Dict[str, float]:
    overall = float(df[TOTAL_COLUMN].sum()) if TOTAL_COLUMN in df.columns else float(df.select_dtypes("number").sum().sum())
    avg = float(df[TOTAL_COLUMN].mean()) if TOTAL_COLUMN in df.columns else float(df.select_dtypes("number").mean().mean())
    max_value = float(df[TOTAL_COLUMN].max()) if TOTAL_COLUMN in df.columns else float(df.select_dtypes("number").max().max())
    min_value = float(df[TOTAL_COLUMN].min()) if TOTAL_COLUMN in df.columns else float(df.select_dtypes("number").min().min())
    return {
        "total": round(overall, 2),
        "average": round(avg, 2),
        "max": round(max_value, 2),
        "min": round(min_value, 2),
    }


def build_service_percentages(service_totals: pd.Series) -> pd.DataFrame:
    if service_totals.empty:
        return pd.DataFrame(columns=["Serviço", "Custo", "Percentual"])
    total = service_totals.sum()
    df = service_totals.reset_index()
    df.columns = ["Serviço", "Custo"]
    df["Percentual"] = (df["Custo"] / total * 100).round(2)
    return df


def aggregate_monthly_totals(df: pd.DataFrame, services: Optional[Sequence[str]] = None) -> pd.DataFrame:
    if DATE_COLUMN not in df.columns:
        return pd.DataFrame()
    subset = df.copy()
    subset = subset[subset[DATE_COLUMN].notna()]
    if subset.empty:
        return pd.DataFrame()
    columns = list(services) if services else [TOTAL_COLUMN]
    columns = [col for col in columns if col in subset.columns]
    if not columns:
        return pd.DataFrame()
    grouped = (
        subset.set_index(DATE_COLUMN)[columns]
        .resample("M")
        .sum()
        .reset_index()
        .rename(columns={DATE_COLUMN: "Competência"})
    )
    return grouped


def build_rankings(service_totals: pd.Series, top_n: int = 10) -> pd.DataFrame:
    if service_totals.empty:
        return pd.DataFrame(columns=["Serviço", "Custo"])
    df = service_totals.reset_index()
    df.columns = ["Serviço", "Custo"]
    return df.head(top_n)


def build_statistics_table(df: pd.DataFrame, services: Iterable[str]) -> pd.DataFrame:
    available = [col for col in services if col in df.columns]
    if not available:
        return pd.DataFrame()
    stats = df[available].agg(["sum", "mean", "max", "min"])
    stats.index = ["Soma", "Média", "Máximo", "Mínimo"]
    return stats


def build_highlights(service_totals: pd.Series, monthly_totals: pd.DataFrame) -> Dict[str, Optional[str]]:
    highlights = {"maior_servico": None, "menor_servico": None, "maior_mes": None, "menor_mes": None}
    if not service_totals.empty:
        highlights["maior_servico"] = service_totals.idxmax()
        highlights["menor_servico"] = service_totals.idxmin()
    if not monthly_totals.empty:
        total_column = next((col for col in monthly_totals.columns if col != "Competência"), None)
        if total_column:
            idxmax = monthly_totals[total_column].idxmax()
            idxmin = monthly_totals[total_column].idxmin()
            if pd.notna(idxmax):
                highlights["maior_mes"] = monthly_totals.loc[idxmax, "Competência"].strftime("%Y-%m")
            if pd.notna(idxmin):
                highlights["menor_mes"] = monthly_totals.loc[idxmin, "Competência"].strftime("%Y-%m")
    return highlights
