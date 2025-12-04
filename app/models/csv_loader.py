"""Model layer responsible for reading CSV data with basic error handling."""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Union

import hashlib

import pandas as pd


class CSVLoadError(Exception):
    """Raised when a CSV file cannot be loaded."""


@dataclass
class CSVData:
    """Structure representing a loaded CSV dataset."""

    name: str
    dataframe: pd.DataFrame
    size: int
    checksum: str


def _reset_buffer(buffer: Union[BytesIO, "BinaryIO"]) -> None:
    """Return the file pointer to the beginning when possible."""

    if hasattr(buffer, "seek"):
        buffer.seek(0)


def load_csv(raw_content: bytes, filename: str) -> CSVData:
    """Load a CSV file content into a DataFrame, returning metadata for persistence."""

    buffer = BytesIO(raw_content)
    checksum = hashlib.sha256(raw_content).hexdigest()
    size = len(raw_content)

    for encoding in (None, "latin-1", "utf-8"):
        try:
            _reset_buffer(buffer)
            dataframe = pd.read_csv(buffer, encoding=encoding) if encoding else pd.read_csv(buffer)
            return CSVData(name=filename, dataframe=dataframe, size=size, checksum=checksum)
        except UnicodeDecodeError:
            continue
        except Exception as exc:  # pragma: no cover - streamlit runtime errors are surfaced to UI
            raise CSVLoadError(f"Falha ao ler o arquivo {filename}: {exc}") from exc

    raise CSVLoadError(f"Não foi possível determinar o encoding do arquivo {filename}.")
