"""Funções para carregar dados de CSV e SQLite."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from app.models import db
from app.models.cost_model import CostDataset, build_cost_dataset, ensure_storage, fetch_cost_dataframe, persist_cost_dataframe
from app.models.csv_loader import CSVData, CSVLoadError, load_csv


@dataclass
class ImportedFile:
    """Metadata de arquivo importado."""

    id: int
    filename: str
    filesize: int
    checksum: str
    imported_at: str
    cloud_provider: str


def import_csv_to_db(uploaded_file, cloud_provider: Optional[str] = None) -> tuple[Optional[int], Optional[str]]:
    """
    Importa um CSV para o banco SQLite.

    Args:
        uploaded_file: Arquivo enviado via st.file_uploader
        cloud_provider: Provedor selecionado (AWS, OCI)

    Returns:
        Tupla (file_id, error_message). Se file_id é None, houve erro.
    """
    if not uploaded_file:
        return None, None

    try:
        raw_content = uploaded_file.getvalue()
        csv_data: CSVData = load_csv(raw_content, uploaded_file.name)

        # Verificar se já existe
        existing = db.get_file_by_checksum(csv_data.checksum)
        if existing:
            return None, f"Arquivo {uploaded_file.name} já foi importado anteriormente"

        # Criar dataset e persistir
        dataset = build_cost_dataset(csv_data.name, csv_data.dataframe, provider_hint=cloud_provider)
        from datetime import datetime, timezone

        imported_at = datetime.now(tz=timezone.utc).isoformat()

        ensure_storage()
        file_id = db.insert_file_import(
            filename=csv_data.name,
            filesize=csv_data.size,
            checksum=csv_data.checksum,
            imported_at=imported_at,
            cloud_provider=dataset.provider,
        )

        persist_cost_dataframe(file_id=file_id, df=dataset.dataframe)

        return file_id, None
    except CSVLoadError as e:
        return None, str(e)
    except Exception as e:
        return None, f"Erro ao importar: {str(e)}"


def list_imported_files() -> list[ImportedFile]:
    """
    Lista arquivos importados no banco.

    Returns:
        Lista de ImportedFile
    """
    rows = db.list_imported_files()
    return [
        ImportedFile(
            id=int(row["id"]),
            filename=row["filename"],
            filesize=int(row["filesize"]),
            checksum=row["checksum"],
            imported_at=row["imported_at"],
            cloud_provider=row["cloud_provider"],
        )
        for row in rows
    ]


def load_dataset_from_db(file_id: int) -> Optional[pd.DataFrame]:
    """
    Carrega um dataset do banco SQLite.

    Args:
        file_id: ID do arquivo importado

    Returns:
        DataFrame com os dados ou None se não encontrado
    """
    file_row = db.get_file_by_id(file_id)
    if not file_row:
        return None

    dataframe = fetch_cost_dataframe(file_id=file_id)
    dataset = build_cost_dataset(file_row["filename"], dataframe, provider_hint=file_row["cloud_provider"])
    return dataset.dataframe


def load_cost_dataset(file_id: int) -> Optional[CostDataset]:
    """
    Carrega um dataset normalizado completo do banco SQLite.

    Args:
        file_id: ID do arquivo importado

    Returns:
        CostDataset ou None se não encontrado
    """
    file_row = db.get_file_by_id(file_id)
    if not file_row:
        return None

    dataframe = fetch_cost_dataframe(file_id=file_id)
    return build_cost_dataset(file_row["filename"], dataframe, provider_hint=file_row["cloud_provider"])
