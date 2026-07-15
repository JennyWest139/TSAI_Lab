"""DB-Engine und Session-Factory."""

from __future__ import annotations

import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from tslab.config_loader import load_defaults
from tslab.db.models import Base

SETUP_HINT = """
Datenbank nicht erreichbar.

PostgreSQL (Standard fuer Web-Dashboard und Analysen):
  docker compose up -d
  python scripts/prepare_web_postgres.py

Oder lokale Installation (Windows):
  Dienst postgresql-x64-… starten (services.msc)
  python scripts/setup_postgres.py
  python scripts/db_init.py
  python scripts/db_seed_werte.py

Ohne DB (nur CSV):
  python scripts/db_load_series.py pdax --from-csv --start 1987-12-01 --end 2007-06-30
"""

_engines: dict[str, Engine] = {}


def reset_engine_cache() -> None:
    """Engine-Cache leeren (z. B. nach DB-URL-Wechsel)."""
    _engines.clear()


class DatabaseConnectionError(ConnectionError):
    """DB nicht erreichbar."""

    setup_hint = SETUP_HINT


def get_database_url() -> str:
    env = os.environ.get("TSLAB_DATABASE_URL")
    if env:
        return env.strip()

    cfg = load_defaults()
    db_cfg = cfg.get("database", {})
    return db_cfg.get("url", "postgresql+psycopg2://tslab:tslab@localhost:5432/tslab")


def get_database_kind() -> str:
    """postgresql | other"""
    url = get_database_url()
    if url.startswith("postgresql"):
        return "postgresql"
    return "other"


def get_database_display_name() -> str:
    kind = get_database_kind()
    if kind == "postgresql":
        return "PostgreSQL"
    return "Datenbank"


def get_engine() -> Engine:
    url = get_database_url()
    if url in _engines:
        return _engines[url]

    engine = create_engine(url, pool_pre_ping=True)
    _engines[url] = engine
    return engine


def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_session() -> Session:
    return get_session_factory()()


def check_connection() -> None:
    """Prueft DB-Verbindung; wirft DatabaseConnectionError mit Hinweisen."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
    except OperationalError as exc:
        raw = str(exc.args[0]) if exc.args else str(exc)
        try:
            detail = raw
        except Exception:
            detail = "Verbindung fehlgeschlagen (Details in pgAdmin pruefen)"
        msg = f"Datenbank nicht erreichbar: {get_database_url()}\n{detail}"
        err = DatabaseConnectionError(msg)
        err.__cause__ = exc
        raise err from exc


def init_db() -> None:
    """Legt alle Tabellen an (idempotent) und wendet Migrationen an."""
    get_database_url()
    from tslab.db.migrate import migrate_schema

    migrate_schema()
