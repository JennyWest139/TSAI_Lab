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
    ("time_series", "category_id", "category_id INTEGER REFERENCES categories(id)", "category_id INTEGER"),
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
    _seed_categories()
    _backfill_entity_categories()


def _backfill_entity_categories() -> None:
    try:
        from sqlalchemy.orm import Session

        from tslab.services.entity_categories import backfill_series_from_primary

        with Session(get_engine()) as session:
            n = backfill_series_from_primary(session)
            if n:
                _log.info("Schema migration: %s series category links backfilled", n)
    except Exception as exc:
        _log.warning("Entity-Category-Backfill uebersprungen: %s", exc)


def _seed_categories() -> None:
    try:
        from sqlalchemy.orm import Session

        from tslab.services.category_service import seed_default_categories

        with Session(get_engine()) as session:
            seed_default_categories(session)
    except Exception as exc:
        _log.warning("Kategorie-Seed uebersprungen: %s", exc)
