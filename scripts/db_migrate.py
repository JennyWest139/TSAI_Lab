#!/usr/bin/env python
"""CLI: Schema-Migration ausfuehren."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tslab.config_loader import load_dotenv_file
from tslab.db.engine import get_database_display_name, get_database_url
from tslab.db.migrate import migrate_schema


def main() -> None:
    load_dotenv_file()
    print(f"Datenbank: {get_database_url()} ({get_database_display_name()})")
    migrate_schema()
    print("Schema migration complete.")


if __name__ == "__main__":
    main()
