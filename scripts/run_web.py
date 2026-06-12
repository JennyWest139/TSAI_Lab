#!/usr/bin/env python
"""
TSLab Web-Dashboard (Flask, UI-Prototyp mit Mock-Daten).

  python scripts/run_web.py
  python scripts/run_web.py --port 5000 --debug
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tslab.web import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="TSLab Flask-Dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    app = create_app()
    print(f"TSLab UI: http://{args.host}:{args.port}/")
    print("Hinweis: Mock-Daten — Backend-Anbindung folgt.")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
