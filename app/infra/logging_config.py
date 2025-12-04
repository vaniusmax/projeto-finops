"""Configuração de logging para o projeto."""
from __future__ import annotations

import logging
import sys

from app.config import LOG_LEVEL


def setup_logging() -> None:
    """Configura logging básico para o projeto."""
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def get_logger(name: str) -> logging.Logger:
    """Retorna um logger configurado."""
    return logging.getLogger(name)


