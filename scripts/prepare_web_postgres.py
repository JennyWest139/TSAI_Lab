#!/usr/bin/env python
"""
PostgreSQL fuer das Web-Dashboard vorbereiten (Tabellen, Seed, Verbindungstest).

Voraussetzung: PostgreSQL laeuft (Docker oder lokale Installation).

  docker compose up -d
  python scripts/prepare_web_postgres.py
  python scripts/run_web.py --no-mock-fallback
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import func, select

from tslab.db.engine import check_connection, get_database_url, get_session, init_db
from tslab.db.models import TimeSeries
from tslab.services.timeseries_store import list_series, seed_werte_csv_columns


def main() -> None:
    url = get_database_url()
    if not url.startswith("postgresql"):
        print(f"Hinweis: Aktive URL ist nicht PostgreSQL: {url}")
        print("Setzen Sie in config/defaults.yaml: database.use_sqlite: false")
        print("Oder: $env:TSLAB_DATABASE_URL = 'postgresql+psycopg2://tslab:tslab@localhost:5432/tslab'")
        sys.exit(1)

    print(f"PostgreSQL: {url}")
    check_connection()
    print("Verbindung: OK")

    init_db()
    print("Tabellen: OK")

    with get_session() as session:
        count = session.scalar(select(func.count()).select_from(TimeSeries)) or 0
        if count == 0:
            print("Keine Zeitreihen — importiere Werte.csv …")
            imported = seed_werte_csv_columns(session)
            print(f"Importiert: {len(imported)} Reihen")
        else:
            series = list_series(session)
            print(f"Zeitreihen in DB: {len(series)}")
            for ts in series[:5]:
                print(f"  {ts.slug:12} {ts.first_date} .. {ts.last_date}  ({ts.observation_count} n)")
            if len(series) > 5:
                print(f"  … und {len(series) - 5} weitere")

    print()
    print("Web-Dashboard starten:")
    print("  python scripts/run_web.py --no-mock-fallback")


if __name__ == "__main__":
    main()
