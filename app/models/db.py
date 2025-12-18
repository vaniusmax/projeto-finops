"""SQLite helpers for persisting imported CSV files and normalized costs."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional, Sequence


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "finops.db"


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection ensuring the data directory exists."""

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database() -> None:
    """Create base tables (files_imports, costs_normalized) and useful indexes."""

    files_table_sql = """
    CREATE TABLE IF NOT EXISTS files_imports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        filesize INTEGER NOT NULL,
        checksum TEXT NOT NULL UNIQUE,
        imported_at TEXT NOT NULL,
        cloud_provider TEXT NOT NULL DEFAULT 'AWS'
    );
    """

    costs_table_sql = """
    CREATE TABLE IF NOT EXISTS costs_normalized (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id INTEGER NOT NULL REFERENCES files_imports(id) ON DELETE CASCADE,
        usage_date TEXT,
        service TEXT NOT NULL,
        amount REAL NOT NULL DEFAULT 0
    );
    """

    with get_connection() as conn:
        conn.execute(files_table_sql)
        conn.execute(costs_table_sql)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_costs_file_id ON costs_normalized(file_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_costs_service ON costs_normalized(service);")
        # Adicionar coluna cloud_provider se o banco já existir sem ela
        try:
            conn.execute("ALTER TABLE files_imports ADD COLUMN cloud_provider TEXT NOT NULL DEFAULT 'AWS';")
        except sqlite3.OperationalError:
            # Coluna já existe
            pass
        conn.commit()


def insert_file_import(filename: str, filesize: int, checksum: str, imported_at: str, cloud_provider: str) -> int:
    """Persist a record in files_imports and return its id."""

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO files_imports (filename, filesize, checksum, imported_at, cloud_provider)
            VALUES (?, ?, ?, ?, ?);
            """,
            (filename, filesize, checksum, imported_at, cloud_provider),
        )
        conn.commit()
        return int(cursor.lastrowid)


def get_file_by_checksum(checksum: str) -> Optional[sqlite3.Row]:
    """Return file metadata for a given checksum."""

    with get_connection() as conn:
        row = conn.execute("SELECT * FROM files_imports WHERE checksum = ?;", (checksum,)).fetchone()
        return row


def get_file_by_id(file_id: int) -> Optional[sqlite3.Row]:
    """Retrieve metadata for a stored file import."""

    with get_connection() as conn:
        row = conn.execute("SELECT * FROM files_imports WHERE id = ?;", (file_id,)).fetchone()
        return row


def list_imported_files() -> Sequence[sqlite3.Row]:
    """List imported files ordered by most recent."""

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, filename, filesize, checksum, imported_at, cloud_provider
            FROM files_imports
            ORDER BY imported_at DESC;
            """
        ).fetchall()
        return rows


def insert_cost_rows(file_id: int, rows: Sequence[Sequence[object]]) -> None:
    """Insert multiple rows into the normalized costs table."""

    if not rows:
        return

    with get_connection() as conn:
        conn.executemany(
            'INSERT INTO costs_normalized (file_id, usage_date, service, amount) VALUES (?, ?, ?, ?);',
            [(file_id, *row) for row in rows],
        )
        conn.commit()


def fetch_cost_rows(file_id: int, table: str = "costs_normalized") -> Sequence[sqlite3.Row]:
    """Fetch all stored cost rows for a file."""

    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT usage_date, service, amount
            FROM {table}
            WHERE file_id = ?
            ORDER BY usage_date;
            """,
            (file_id,),
        ).fetchall()
        return rows


def fetch_legacy_cost_rows(file_id: int, columns: Iterable[str]) -> Sequence[sqlite3.Row]:
    """Fetch rows from legacy costs table."""

    column_sql = ", ".join(f'"{column}"' for column in columns)
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT {column_sql} FROM costs WHERE file_id = ? ORDER BY id;",
            (file_id,),
        ).fetchall()
        return rows


def table_exists(name: str) -> bool:
    with get_connection() as conn:
        row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (name,)).fetchone()
        return bool(row)
