"""SQLite helpers for persisting imported CSV files and normalized costs."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "finops.db"


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection ensuring the data directory exists."""

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database(cost_columns: Mapping[str, str]) -> None:
    """Create base tables (files_imports, costs) and useful indexes."""

    files_table_sql = """
    CREATE TABLE IF NOT EXISTS files_imports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        filesize INTEGER NOT NULL,
        checksum TEXT NOT NULL UNIQUE,
        imported_at TEXT NOT NULL
    );
    """

    cost_fields_sql = ",\n        ".join(f'"{name}" {definition}' for name, definition in cost_columns.items())
    costs_table_sql = f"""
    CREATE TABLE IF NOT EXISTS costs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id INTEGER NOT NULL REFERENCES files_imports(id) ON DELETE CASCADE,
        {cost_fields_sql}
    );
    """

    with get_connection() as conn:
        conn.execute(files_table_sql)
        conn.execute(costs_table_sql)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_costs_file_id ON costs(file_id);")
        if "servico" in cost_columns:
            conn.execute('CREATE INDEX IF NOT EXISTS idx_costs_servico ON costs("servico");')
        conn.commit()


def insert_file_import(filename: str, filesize: int, checksum: str, imported_at: str) -> int:
    """Persist a record in files_imports and return its id."""

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO files_imports (filename, filesize, checksum, imported_at)
            VALUES (?, ?, ?, ?);
            """,
            (filename, filesize, checksum, imported_at),
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
            SELECT id, filename, filesize, checksum, imported_at
            FROM files_imports
            ORDER BY imported_at DESC;
            """
        ).fetchall()
        return rows


def insert_cost_rows(file_id: int, columns: Iterable[str], rows: Sequence[Sequence[object]]) -> None:
    """Insert multiple rows into the costs table."""

    if not rows:
        return

    placeholders = ", ".join("?" for _ in columns)
    column_sql = ", ".join(f'"{column}"' for column in columns)
    sql = f'INSERT INTO costs (file_id, {column_sql}) VALUES (?, {placeholders});'

    with get_connection() as conn:
        conn.executemany(sql, [(file_id, *row) for row in rows])
        conn.commit()


def fetch_cost_rows(file_id: int, columns: Iterable[str]) -> Sequence[sqlite3.Row]:
    """Fetch all stored cost rows for a file."""

    column_sql = ", ".join(f'"{column}"' for column in columns)
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT {column_sql} FROM costs WHERE file_id = ? ORDER BY id;",
            (file_id,),
        ).fetchall()
        return rows
