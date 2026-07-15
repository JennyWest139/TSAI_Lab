#!/usr/bin/env python
"""PostgreSQL-Tabellen anlegen."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tslab.db.engine import get_database_url, init_db


def main() -> None:
    url = get_database_url()
    print(f"Datenbank: {url}")
    init_db()
    print("Tabellen erstellt / Migrationen angewendet.")


if __name__ == "__main__":
    main()
