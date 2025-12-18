"""Domain-specific helpers for cost dashboards (normalization, stats, rankings)."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence

import pandas as pd

from app.models import db

# Colunas internas normalizadas
DATE_COLUMN = "Data"
SERVICE_COLUMN = "Serviço"
TOTAL_COLUMN = "Custos totais($)"

AWS_PROVIDER = "AWS"
OCI_PROVIDER = "OCI"
GENERIC_PROVIDER = "GENERIC"

DATE_KEYWORDS = ("date", "period", "periodo", "competencia", "competência", "month", "mes", "billing_period")
TOTAL_KEYWORDS = ("total", "amount", "grand_total", "valor_total", "custostotais", "custos_totais")
SERVICE_KEYWORDS = ("service", "servico", "serviço", "product", "produto", "resource", "recurso")

# Colunas do schema legacy (tabela costs em formato wide)
LEGACY_COST_COLUMNS: List[str] = [
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


@dataclass
class CostDataset:
    """Normalized dataset plus metadata ready for business logic."""

    name: str
    dataframe: pd.DataFrame  # formato wide (datas + colunas por serviço + total)
    service_columns: List[str]
    has_dates: bool
    provider: str
    long_dataframe: Optional[pd.DataFrame] = None
    file_id: Optional[int] = None


def _detect_provider(df: pd.DataFrame, hint: Optional[str] = None) -> str:
    """Detect provider based on known columns."""

    if hint:
        return hint

    normalized_cols = {str(col).strip().lower() for col in df.columns}
    if "lineitem/intervalusagestart" in normalized_cols and "product/service" in normalized_cols:
        return OCI_PROVIDER
    if {"start", "end", "service", "amount"}.issubset(normalized_cols):
        return AWS_PROVIDER
    return GENERIC_PROVIDER


def _normalize_aws(df: pd.DataFrame) -> pd.DataFrame:
    normalized = pd.DataFrame()
    start_col = df["Start"] if "Start" in df.columns else df.get("start")
    service_col = df["Service"] if "Service" in df.columns else df.get("service")
    amount_col = df["Amount"] if "Amount" in df.columns else df.get("amount")

    start_series = _ensure_series(start_col)
    service_series = _ensure_series(service_col)
    amount_series = _ensure_series(amount_col)

    normalized[DATE_COLUMN] = pd.to_datetime(start_series, errors="coerce")
    normalized[SERVICE_COLUMN] = service_series
    normalized[TOTAL_COLUMN] = pd.to_numeric(amount_series, errors="coerce").fillna(0.0)
    return normalized


def _normalize_oci(df: pd.DataFrame) -> pd.DataFrame:
    normalized = pd.DataFrame()

    start_series = _ensure_series(df.get("lineItem/intervalUsageStart"))
    service_series = _ensure_series(df.get("product/service"))

    consumed_series = _ensure_series(df.get("usage/consumedQuantity"))
    units_series = _ensure_series(df.get("usage/consumedQuantityUnits"))
    measure_series = _ensure_series(df.get("usage/consumedQuantityMeasure"))
    amount_series = _convert_oci_consumed(consumed_series, units_series, measure_series)

    normalized[DATE_COLUMN] = pd.to_datetime(start_series, errors="coerce")
    normalized[SERVICE_COLUMN] = service_series
    normalized[TOTAL_COLUMN] = pd.to_numeric(amount_series, errors="coerce").fillna(0.0)
    return normalized


def _normalize_generic(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]

    date_col = _get_date_column(df)
    if date_col and date_col != DATE_COLUMN:
        df = df.rename(columns={date_col: DATE_COLUMN})

    service_col = _get_service_column(df)
    if service_col and service_col != SERVICE_COLUMN:
        df = df.rename(columns={service_col: SERVICE_COLUMN})

    total_col = _get_total_column(df)
    if total_col and total_col != TOTAL_COLUMN:
        df = df.rename(columns={total_col: TOTAL_COLUMN})
    normalized = pd.DataFrame()
    normalized[DATE_COLUMN] = pd.to_datetime(df[DATE_COLUMN], errors="coerce") if DATE_COLUMN in df else pd.Series(dtype="datetime64[ns]")

    service_series = _ensure_series(df[SERVICE_COLUMN] if SERVICE_COLUMN in df else None).fillna("Serviço desconhecido")
    amount_series = _ensure_series(df[TOTAL_COLUMN] if TOTAL_COLUMN in df else None)

    normalized[SERVICE_COLUMN] = service_series
    normalized[TOTAL_COLUMN] = pd.to_numeric(amount_series, errors="coerce").fillna(0.0)
    return normalized


def _normalize_to_long(df: pd.DataFrame, provider_hint: Optional[str] = None) -> tuple[pd.DataFrame, str]:
    """Normalize raw dataframe into long format with (Data, Serviço, Custos totais)."""

    if df.empty:
        provider = provider_hint or _detect_provider(df, provider_hint)
        empty_df = pd.DataFrame(columns=[DATE_COLUMN, SERVICE_COLUMN, TOTAL_COLUMN])
        return empty_df, provider

    provider = _detect_provider(df, provider_hint)
    if provider == AWS_PROVIDER and _has_aws_columns(df):
        normalized = _normalize_aws(df)
    elif provider == OCI_PROVIDER and _has_oci_columns(df):
        normalized = _normalize_oci(df)
    else:
        normalized = _normalize_generic(df)

    # Sanitizar colunas obrigatórias
    normalized[SERVICE_COLUMN] = normalized[SERVICE_COLUMN].fillna("Serviço não informado").astype(str)
    normalized[TOTAL_COLUMN] = pd.to_numeric(normalized[TOTAL_COLUMN], errors="coerce").fillna(0.0)
    normalized[DATE_COLUMN] = pd.to_datetime(normalized[DATE_COLUMN], errors="coerce")

    normalized = normalized.dropna(subset=[SERVICE_COLUMN])
    return normalized, provider


def _is_wide_format(df: pd.DataFrame) -> bool:
    """Detect if dataframe is already in wide format (colunas por serviço)."""

    date_col = _get_date_column(df)
    if not date_col:
        return False

    columns = [col for col in df.columns if col not in {date_col, SERVICE_COLUMN}]
    total_col = _get_total_column(df)
    if total_col:
        columns = [col for col in columns if col != total_col]
    return len(columns) > 0


def _wide_to_long(df: pd.DataFrame) -> pd.DataFrame:
    """Converte dataframe wide (colunas por serviço) para formato longo."""

    date_col = _get_date_column(df)
    if not date_col:
        return pd.DataFrame(columns=[DATE_COLUMN, SERVICE_COLUMN, TOTAL_COLUMN])

    working_df = df.copy()
    if date_col != DATE_COLUMN:
        working_df = working_df.rename(columns={date_col: DATE_COLUMN})

    total_col = _get_total_column(working_df)
    drop_cols: List[str] = []
    if total_col:
        if total_col != TOTAL_COLUMN:
            working_df = working_df.rename(columns={total_col: TOTAL_COLUMN})
        drop_cols.append(TOTAL_COLUMN)

    # Remover coluna de total original para recalcular após o pivot
    working_df = working_df.drop(columns=drop_cols, errors="ignore")

    service_columns = get_service_columns(working_df)
    if not service_columns:
        service_columns = [col for col in working_df.columns if col != DATE_COLUMN]
    if not service_columns:
        return pd.DataFrame(columns=[DATE_COLUMN, SERVICE_COLUMN, TOTAL_COLUMN])

    melted = working_df.melt(id_vars=[DATE_COLUMN], value_vars=service_columns, var_name=SERVICE_COLUMN, value_name=TOTAL_COLUMN)
    melted[DATE_COLUMN] = pd.to_datetime(melted[DATE_COLUMN], errors="coerce")
    melted[TOTAL_COLUMN] = pd.to_numeric(melted[TOTAL_COLUMN], errors="coerce").fillna(0.0)
    melted = melted.dropna(subset=[DATE_COLUMN])
    melted = melted[melted[TOTAL_COLUMN] > 0]
    return melted


def _ensure_series(value) -> pd.Series:
    """Garantir que o valor seja uma Series para evitar erros de atributo em escalares."""

    if isinstance(value, pd.Series):
        return value
    if value is None:
        return pd.Series(dtype=float)
    return pd.Series(value)


def _convert_oci_consumed(consumed: pd.Series, units: pd.Series, measure: pd.Series) -> pd.Series:
    """
    Converte quantidade consumida OCI para unidades mais compreensíveis, evitando números inflados.
    Heurísticas:
    - MS -> horas
    - GB_MS -> GB-mês aproximado (divide por 1000*60*60*24*30)
    - BYTES -> GB
    Caso contrário, retorna valor original.
    """

    result = pd.to_numeric(consumed, errors="coerce")
    units_upper = units.astype(str).str.upper().fillna("")
    measure_upper = measure.astype(str).str.upper().fillna("")

    ms_mask = units_upper.str.contains("MS")
    result.loc[ms_mask] = result[ms_mask] / (1000 * 60 * 60)  # ms -> horas

    gb_ms_mask = units_upper.str.contains("GB_MS") | measure_upper.str.contains("GB_MS")
    result.loc[gb_ms_mask] = result[gb_ms_mask] / (1000 * 60 * 60 * 24 * 30)  # ms -> meses aproximados

    bytes_mask = units_upper.str.contains("BYTE")
    result.loc[bytes_mask] = result[bytes_mask] / (1024**3)  # bytes -> GB

    return result


def _legacy_column_mapping() -> Dict[str, str]:
    """Mapear colunas normalizadas antigas (snake case) para nomes exibidos."""

    def _normalize_db_column(name: str) -> str:
        import re as _re

        slug = _re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_").lower()
        slug = _re.sub(r"_+", "_", slug)
        return slug or "col"

    mapping: Dict[str, str] = {}
    for col in LEGACY_COST_COLUMNS:
        mapping[_normalize_db_column(col)] = col
    return mapping


def _slugify_column(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(name).strip())
    ascii_string = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^0-9a-z]+", "_", ascii_string.lower()).strip("_")


def _find_column_by_keywords(columns: Iterable[str], keywords: Sequence[str]) -> Optional[str]:
    normalized_keywords = [_slugify_column(keyword) for keyword in keywords if keyword]
    for col in columns:
        slug = _slugify_column(col)
        tokens = set(filter(None, slug.split("_")))
        for keyword in normalized_keywords:
            if keyword == "data":
                if slug == "data" or slug.startswith("data_"):
                    return col
                continue
            if "_" in keyword:
                if keyword in slug:
                    return col
            elif keyword in tokens:
                return col
    return None


def _get_date_column(df: pd.DataFrame) -> Optional[str]:
    if DATE_COLUMN in df.columns:
        return DATE_COLUMN
    lower_map = {str(col).strip().lower(): col for col in df.columns}
    if "data" in lower_map:
        return lower_map["data"]
    keyword_match = _find_column_by_keywords(df.columns, DATE_KEYWORDS)
    if keyword_match:
        return keyword_match
    inferred = _infer_date_column_by_values(df)
    return inferred


def _get_total_column(df: pd.DataFrame) -> Optional[str]:
    if TOTAL_COLUMN in df.columns:
        return TOTAL_COLUMN
    return _find_column_by_keywords(df.columns, TOTAL_KEYWORDS)


def _get_service_column(df: pd.DataFrame) -> Optional[str]:
    if SERVICE_COLUMN in df.columns:
        return SERVICE_COLUMN
    return _find_column_by_keywords(df.columns, SERVICE_KEYWORDS)


def _has_aws_columns(df: pd.DataFrame) -> bool:
    normalized = {str(col).strip().lower() for col in df.columns}
    return {"start", "service", "amount"}.issubset(normalized)


def _has_oci_columns(df: pd.DataFrame) -> bool:
    normalized = {str(col).strip().lower() for col in df.columns}
    return "lineitem/intervalusagestart" in normalized and "product/service" in normalized


def _infer_date_column_by_values(df: pd.DataFrame) -> Optional[str]:
    """Tenta identificar uma coluna de datas analisando os valores."""

    threshold = max(1, int(len(df) * 0.6))
    for col in df.columns:
        series = df[col]
        if pd.api.types.is_datetime64_any_dtype(series):
            return col
        if not (pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)):
            continue
        try:
            parsed = pd.to_datetime(series, errors="coerce")
        except Exception:
            continue
        if parsed.notna().sum() >= threshold:
            return col
    return None


def _load_legacy_costs(file_id: int) -> Optional[pd.DataFrame]:
    """Ler dados da tabela legacy 'costs' e converter para formato wide compatível."""

    legacy_map = _legacy_column_mapping()
    legacy_columns = list(legacy_map.keys())
    if not legacy_columns:
        return None

    rows = db.fetch_legacy_cost_rows(file_id=file_id, columns=legacy_columns)
    if not rows:
        return None

    legacy_df = pd.DataFrame(rows, columns=legacy_columns)
    legacy_df = legacy_df.rename(columns=legacy_map)

    if "Serviço" in legacy_df.columns:
        legacy_df = legacy_df.rename(columns={"Serviço": DATE_COLUMN})
        legacy_df[DATE_COLUMN] = pd.to_datetime(legacy_df[DATE_COLUMN], errors="coerce")

    # Converter numéricos e preencher NaT
    for col in legacy_df.columns:
        if col == DATE_COLUMN:
            continue
        legacy_df[col] = pd.to_numeric(legacy_df[col], errors="coerce").fillna(0.0)

    if TOTAL_COLUMN not in legacy_df.columns:
        service_cols = [c for c in legacy_df.columns if c != DATE_COLUMN]
        legacy_df[TOTAL_COLUMN] = legacy_df[service_cols].sum(axis=1) if service_cols else 0.0

    return legacy_df


def _long_to_wide(long_df: pd.DataFrame) -> pd.DataFrame:
    """Converte dataset longo em formato wide usado na UI."""

    pivot = (
        long_df.pivot_table(index=DATE_COLUMN, columns=SERVICE_COLUMN, values=TOTAL_COLUMN, aggfunc="sum", fill_value=0)
        .reset_index()
        .sort_values(DATE_COLUMN)
    )
    service_columns = [col for col in pivot.columns if col != DATE_COLUMN]
    if service_columns:
        pivot[TOTAL_COLUMN] = pivot[service_columns].sum(axis=1)
    else:
        pivot[TOTAL_COLUMN] = 0.0
    return pivot


def build_cost_dataset(name: str, df: pd.DataFrame, provider_hint: Optional[str] = None) -> CostDataset:
    if _is_wide_format(df):
        long_df = _wide_to_long(df)
        provider = provider_hint or GENERIC_PROVIDER
    else:
        long_df, provider = _normalize_to_long(df, provider_hint)
    wide_df = _long_to_wide(long_df) if not long_df.empty else pd.DataFrame(columns=[DATE_COLUMN, TOTAL_COLUMN])
    service_columns = [col for col in wide_df.columns if col not in {DATE_COLUMN, TOTAL_COLUMN}]
    has_dates = DATE_COLUMN in wide_df.columns and wide_df[DATE_COLUMN].notna().any()
    return CostDataset(
        name=name,
        dataframe=wide_df,
        service_columns=service_columns,
        has_dates=has_dates,
        provider=provider,
        long_dataframe=long_df,
    )


def ensure_storage() -> None:
    """Initialize SQLite tables for files and normalized costs."""

    db.initialize_database()


def _serialize_rows(df: pd.DataFrame, service_columns: Sequence[str]) -> List[tuple]:
    """Converte dataframe wide para linhas (data, service, amount) para armazenar no SQLite."""

    if df.empty or DATE_COLUMN not in df.columns:
        return []

    rows: List[tuple] = []
    for _, row in df.iterrows():
        date_value = row[DATE_COLUMN]
        date_str = date_value.strftime("%Y-%m-%d") if pd.notna(date_value) else None
        for service in service_columns:
            amount = float(row.get(service, 0.0) or 0.0)
            rows.append((date_str, service, amount))
    return rows


def persist_cost_dataframe(file_id: int, df: pd.DataFrame) -> None:
    """Store all rows from the normalized dataframe into the normalized costs table."""

    service_columns = [col for col in df.columns if col not in {DATE_COLUMN, TOTAL_COLUMN}]
    rows = _serialize_rows(df, service_columns)
    db.insert_cost_rows(file_id=file_id, rows=rows)


def fetch_cost_dataframe(file_id: int) -> pd.DataFrame:
    """Retrieve all cost rows associated with a file_id."""

    rows = db.fetch_cost_rows(file_id=file_id)
    if not rows:
        # Fallback para dados antigos (tabela costs no formato wide)
        if db.table_exists("costs"):
            legacy_df = _load_legacy_costs(file_id)
            if legacy_df is not None:
                return legacy_df
        return pd.DataFrame(columns=[DATE_COLUMN, TOTAL_COLUMN])

    long_df = pd.DataFrame(rows, columns=[DATE_COLUMN, SERVICE_COLUMN, TOTAL_COLUMN])
    long_df[DATE_COLUMN] = pd.to_datetime(long_df[DATE_COLUMN], errors="coerce")
    long_df[TOTAL_COLUMN] = pd.to_numeric(long_df[TOTAL_COLUMN], errors="coerce").fillna(0.0)
    wide_df = _long_to_wide(long_df)
    return wide_df


def get_service_columns(df: pd.DataFrame) -> List[str]:
    """Return service columns (exclude date and total)."""

    return [col for col in df.columns if col not in {DATE_COLUMN, TOTAL_COLUMN}]


def aggregate_service_totals(df: pd.DataFrame, services: Optional[Sequence[str]] = None) -> pd.Series:
    columns = list(services) if services else get_service_columns(df)
    columns = [col for col in columns if col in df.columns]
    if not columns:
        return pd.Series(dtype=float)
    totals = df[columns].sum().sort_values(ascending=False)
    return totals


def calculate_overall_metrics(df: pd.DataFrame) -> Dict[str, float]:
    if df.empty:
        return {"total": 0.0, "average": 0.0, "max": 0.0, "min": 0.0}

    if TOTAL_COLUMN in df.columns:
        overall = float(df[TOTAL_COLUMN].sum())
        avg = float(df[TOTAL_COLUMN].mean())
        max_value = float(df[TOTAL_COLUMN].max())
        min_value = float(df[TOTAL_COLUMN].min())
    else:
        numeric_df = df.select_dtypes("number")
        overall = float(numeric_df.sum().sum())
        avg = float(numeric_df.mean().mean())
        max_value = float(numeric_df.max().max())
        min_value = float(numeric_df.min().min())

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
    df["Percentual"] = (df["Custo"] / total * 100).round(2) if total > 0 else 0.0
    return df


def aggregate_monthly_totals(df: pd.DataFrame, services: Optional[Sequence[str]] = None) -> pd.DataFrame:
    if DATE_COLUMN not in df.columns:
        return pd.DataFrame()
    subset = df.copy()
    subset[DATE_COLUMN] = pd.to_datetime(subset[DATE_COLUMN], errors="coerce")
    subset = subset.dropna(subset=[DATE_COLUMN])
    if subset.empty:
        return pd.DataFrame()

    service_columns = [col for col in (services or get_service_columns(subset)) if col in subset.columns]
    if not service_columns and TOTAL_COLUMN in subset.columns:
        service_columns = [TOTAL_COLUMN]
    if not service_columns:
        return pd.DataFrame()

    monthly = (
        subset.set_index(DATE_COLUMN)[service_columns]
        .resample("M")
        .sum()
        .reset_index()
        .rename(columns={DATE_COLUMN: "Competência"})
    )
    return monthly


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
