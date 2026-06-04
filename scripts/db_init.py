#!/usr/bin/env python
"""PostgreSQL-Tabellen anlegen."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tslab.db.engine import get_database_url, get_sqlite_file_path, init_db


def main() -> None:
    url = get_database_url()
    print(f"Datenbank: {url}")
    db_file = get_sqlite_file_path()
    if db_file:
        print(f"SQLite-Datei: {db_file}")
    init_db()
    print("Tabellen erstellt: time_series, observations, upload_history")


if __name__ == "__main__":
    main()
