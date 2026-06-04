#!/usr/bin/env python
"""SQLite-Datenbank anlegen und Werte.csv importieren (ein Befehl)."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tslab.config_loader import project_root
from tslab.db.engine import check_connection, get_database_url, get_sqlite_file_path, init_db
from tslab.db.engine import get_session
from tslab.services.timeseries_store import seed_werte_csv_columns


def main() -> None:
    db_path = (project_root() / "data" / "tslab.db").resolve()
    os.environ["TSLAB_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"

    print(f"SQLite-Datei: {db_path}")
    init_db()
    check_connection()
    print("Verbindung: OK")

    with get_session() as session:
        series_list = seed_werte_csv_columns(session)
    print(f"Importiert: {len(series_list)} Zeitreihen")
    for ts in series_list:
        print(f"  - {ts.slug}: {ts.observation_count} Werte ({ts.first_date} .. {ts.last_date})")

    print()
    print("Dauerhaft in dieser PowerShell-Session:")
    print(f'  $env:TSLAB_DATABASE_URL = "{get_database_url()}"')
    print()
    print("Oder in config/defaults.yaml: database.use_sqlite: true")
    print()
    print("DB ansehen: DB Browser for SQLite ->", db_path)


if __name__ == "__main__":
    main()
