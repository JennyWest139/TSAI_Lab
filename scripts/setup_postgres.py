#!/usr/bin/env python
"""
PostgreSQL fuer TSAI_Lab vorbereiten (User + DB) und Werte.csv importieren.

Voraussetzung: PostgreSQL-Dienst laeuft.

Standard-Zugang in config/defaults.yaml: tslab / tslab
Falls Ihr postgres-Superuser anderes Passwort hat, einmalig:

  $env:TSLAB_PG_ADMIN_URL = "postgresql+psycopg2://postgres:IHR_POSTGRES_PASSWORT@localhost:5432/postgres"

Dann:
  python scripts/setup_postgres.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError

from tslab.config_loader import load_defaults
from tslab.db.engine import check_connection, get_database_url, init_db, get_session
from tslab.services.timeseries_store import seed_werte_csv_columns


def _admin_url() -> str:
    return os.environ.get(
        "TSLAB_PG_ADMIN_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres",
    )


def ensure_role_and_database() -> None:
    """Legt User tslab und DB tslab an (idempotent soweit moeglich)."""
    engine = create_engine(_admin_url(), isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        try:
            conn.execute(
                text("CREATE USER tslab WITH PASSWORD 'tslab' LOGIN")
            )
            print("User tslab angelegt.")
        except ProgrammingError as e:
            if "already exists" in str(e).lower():
                print("User tslab existiert bereits.")
            else:
                raise

        try:
            conn.execute(text("CREATE DATABASE tslab OWNER tslab"))
            print("Datenbank tslab angelegt.")
        except ProgrammingError as e:
            if "already exists" in str(e).lower():
                print("Datenbank tslab existiert bereits.")
            else:
                raise

        conn.execute(text("GRANT ALL PRIVILEGES ON DATABASE tslab TO tslab"))


def main() -> None:
    os.environ.pop("TSLAB_DATABASE_URL", None)
    cfg = load_defaults()
    cfg["database"]["use_sqlite"] = False

    target = cfg.get("database", {}).get(
        "url", "postgresql+psycopg2://tslab:tslab@localhost:5432/tslab"
    )
    print("Ziel-URL:", target)

    try:
        check_connection()
        print("Verbindung zu tslab: bereits OK")
    except Exception:
        print("Versuche User/DB anzulegen (Admin:", _admin_url().split("@")[0], "@...)")
        try:
            ensure_role_and_database()
        except OperationalError as exc:
            print("\nAdmin-Verbindung fehlgeschlagen.")
            print("Setzen Sie Ihr postgres-Passwort:")
            print(
                '  $env:TSLAB_PG_ADMIN_URL = '
                '"postgresql+psycopg2://postgres:IHR_PASSWORT@localhost:5432/postgres"'
            )
            raise SystemExit(1) from exc

        from tslab.db import engine as eng_mod

        eng_mod._engines.clear()
        check_connection()
        print("Verbindung zu tslab: OK")

    init_db()
    with get_session() as session:
        series_list = seed_werte_csv_columns(session)
    print(f"Importiert: {len(series_list)} Zeitreihen")
    for ts in series_list[:5]:
        print(f"  - {ts.slug}: {ts.observation_count} Werte")
    if len(series_list) > 5:
        print(f"  ... und {len(series_list) - 5} weitere")


if __name__ == "__main__":
    main()
