#!/usr/bin/env python
"""
TSAI_Lab Web-Dashboard (Flask) — PostgreSQL erforderlich.

  python scripts/prepare_web_postgres.py
  python scripts/run_web.py
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tslab.db.engine import SETUP_HINT, check_connection, get_database_display_name, get_database_url, init_db
from tslab.services.ai_providers import gemini_sdk_available
from tslab.web import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="TSAI_Lab Flask-Dashboard (PostgreSQL)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    try:
        check_connection()
        init_db()
    except Exception as exc:
        print(exc)
        print(SETUP_HINT)
        sys.exit(1)

    app = create_app()
    backend = app.extensions["tslab_backend"]

    if os.environ.get("GEMINI_API_KEY", "").strip() and not gemini_sdk_available():
        print(
            "Hinweis: GEMINI_API_KEY ist gesetzt, aber google-genai fehlt in dieser Python-Umgebung."
        )
        print("  .venv\\Scripts\\python.exe -m pip install google-genai")

    print(f"TSAI_Lab UI: http://{args.host}:{args.port}/")
    print(f"Backend: {backend.mode_label}")
    print(f"URL: {get_database_url()}")
    print(f"{get_database_display_name()} verbunden — Korrelation und TSA live aus der DB.")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
