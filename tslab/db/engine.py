"""DB-Engine und Session-Factory."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from tslab.config_loader import load_defaults, project_root
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

SQLite (nur Fallback / Tests):
  python scripts/setup_sqlite.py

Ohne DB (nur CSV):
  python scripts/db_load_series.py pdax --from-csv --start 1987-12-01 --end 2007-06-30
  python scripts/run_web.py --mock
"""

_engines: dict[str, Engine] = {}


class DatabaseConnectionError(ConnectionError):
    """DB nicht erreichbar."""

    setup_hint = SETUP_HINT


def _normalize_sqlite_url(url: str) -> str:
    """Relative sqlite:///data/tslab.db -> absoluter Pfad im Projektordner."""
    if not url.startswith("sqlite"):
        return url
    if url.startswith("sqlite:////"):
        return url

    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return url

    path_part = url[len(prefix) :]
    p = Path(path_part)
    if not p.is_absolute():
        p = (project_root() / p).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{p.as_posix()}"


def get_database_url() -> str:
    env = os.environ.get("TSLAB_DATABASE_URL")
    if env:
        return _normalize_sqlite_url(env.strip())

    if os.environ.get("TSLAB_USE_SQLITE", "").lower() in ("1", "true", "yes"):
        return _sqlite_url()

    cfg = load_defaults()
    db_cfg = cfg.get("database", {})
    if db_cfg.get("use_sqlite"):
        return _sqlite_url()
    return db_cfg.get("url", "postgresql+psycopg2://tslab:tslab@localhost:5432/tslab")


def _sqlite_url() -> str:
    rel = load_defaults().get("database", {}).get("sqlite_path", "data/tslab.db")
    path = (project_root() / rel).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path.as_posix()}"


def get_database_kind() -> str:
    """postgresql | sqlite"""
    url = get_database_url()
    if url.startswith("sqlite"):
        return "sqlite"
    if url.startswith("postgresql"):
        return "postgresql"
    return "other"


def get_database_display_name() -> str:
    kind = get_database_kind()
    if kind == "postgresql":
        return "PostgreSQL"
    if kind == "sqlite":
        return "SQLite"
    return "Datenbank"


def get_sqlite_file_path() -> Path | None:
    """Absoluter Pfad zur .db-Datei, falls SQLite aktiv."""
    url = get_database_url()
    if not url.startswith("sqlite"):
        return None
    prefix = "sqlite:///"
    if url.startswith(prefix):
        return Path(url[len(prefix) :])
    return None


def get_engine() -> Engine:
    url = get_database_url()
    if url in _engines:
        return _engines[url]

    connect_args: dict = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
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
