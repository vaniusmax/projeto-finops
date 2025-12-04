"""Configurações globais do projeto FinOps AI Dashboard."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Se python-dotenv não estiver instalado, continuar sem carregar .env
    # As variáveis de ambiente ainda podem ser definidas manualmente
    pass

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "finops.db"

# LLM Configuration
OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE: Optional[str] = os.getenv("OPENAI_API_BASE")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Cache Configuration
ENABLE_CACHE: bool = os.getenv("ENABLE_CACHE", "true").lower() == "true"
CACHE_TTL: int = int(os.getenv("CACHE_TTL", "3600"))  # 1 hora

# Logging
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

