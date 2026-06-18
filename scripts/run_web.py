#!/usr/bin/env python
"""
TSLab Web-Dashboard (Flask) — Standard: PostgreSQL.

  python scripts/prepare_web_postgres.py
  python scripts/run_web.py
  python scripts/run_web.py --no-mock-fallback
  python scripts/run_web.py --mock
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tslab.db.engine import SETUP_HINT, get_database_display_name, get_database_url
from tslab.web import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="TSLab Flask-Dashboard (PostgreSQL)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Immer Mock-Daten (ohne DB)",
    )
    parser.add_argument(
        "--no-mock-fallback",
        action="store_true",
        help="PostgreSQL erforderlich — bei DB-Fehler abbrechen",
    )
    args = parser.parse_args()

    if args.no_mock_fallback and not args.mock:
        from tslab.db.engine import check_connection, init_db

        try:
            check_connection()
            init_db()
        except Exception as exc:
            print(exc)
            print(SETUP_HINT)
            sys.exit(1)

    app = create_app(use_mock=args.mock)
    backend = app.extensions["tslab_backend"]

    print(f"TSLab UI: http://{args.host}:{args.port}/")
    print(f"Backend: {backend.mode_label}")
    if not args.mock and backend.database_url:
        print(f"URL: {backend.database_url}")
    if backend.uses_mock and not args.mock:
        print(f"Hinweis: {get_database_display_name()} nicht erreichbar — Mock-Fallback aktiv.")
        print("  python scripts/prepare_web_postgres.py")
        print("  python scripts/run_web.py --no-mock-fallback")
    elif not backend.uses_mock and backend.database_kind == "postgresql":
        print("PostgreSQL verbunden — Korrelation und TSA live aus der DB.")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
