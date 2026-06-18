"""Idempotente Schema-Migrationen (ohne Alembic)."""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text

from tslab.db.engine import get_database_kind, get_engine
from tslab.db.models import Base

_log = logging.getLogger(__name__)

# (table, column, postgres_ddl, sqlite_ddl)
_COLUMN_MIGRATIONS: tuple[tuple[str, str, str, str], ...] = (
    ("time_series", "hidden_at", "hidden_at TIMESTAMPTZ", "hidden_at DATETIME"),
    ("correlation_history", "analysis_mode", "analysis_mode VARCHAR(32)", "analysis_mode VARCHAR(32)"),
    ("correlation_history", "run_name", "run_name VARCHAR(256)", "run_name VARCHAR(256)"),
    ("correlation_history", "hidden_at", "hidden_at TIMESTAMPTZ", "hidden_at DATETIME"),
)


def _column_names(table: str) -> set[str]:
    insp = inspect(get_engine())
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _add_column_if_missing(table: str, column: str, ddl: str) -> bool:
    if column in _column_names(table):
        return False
    with get_engine().begin() as conn:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
    _log.info("Schema migration: %s.%s added", table, column)
    return True


def migrate_columns() -> list[str]:
    """ALTER TABLE fuer fehlende Spalten an bestehenden Tabellen."""
    kind = get_database_kind()
    applied: list[str] = []
    for table, column, pg_ddl, sqlite_ddl in _COLUMN_MIGRATIONS:
        if table not in inspect(get_engine()).get_table_names():
            continue
        ddl = pg_ddl if kind == "postgresql" else sqlite_ddl
        if _add_column_if_missing(table, column, ddl):
            applied.append(f"{table}.{column}")
    return applied


def migrate_schema() -> None:
    """Neue Tabellen anlegen + fehlende Spalten nachziehen."""
    engine = get_engine()
    Base.metadata.create_all(engine)
    migrate_columns()
