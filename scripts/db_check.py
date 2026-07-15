#!/usr/bin/env python
"""Prueft die Datenbankverbindung und gibt Setup-Hinweise."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tslab.db.engine import SETUP_HINT, check_connection, get_database_url


def main() -> None:
    url = get_database_url()
    print(f"Datenbank-URL: {url}")
    try:
        check_connection()
    except Exception as exc:
        print("Status: FEHLER")
        print(exc)
        print(SETUP_HINT)
        sys.exit(1)

    print("Status: OK – Verbindung erfolgreich")
    print("Naechste Schritte:")
    print("  python scripts/prepare_web_postgres.py")
    print("  python scripts/run_web.py")
    print("  python scripts/db_init.py      (falls noch nicht geschehen)")
    print("  python scripts/db_seed_werte.py")
    print("  python scripts/db_list_series.py")


if __name__ == "__main__":
    main()
