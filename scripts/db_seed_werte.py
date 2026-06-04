#!/usr/bin/env python
"""Werte.csv in PostgreSQL importieren (alle numerischen Spalten)."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tslab.db.engine import get_session, init_db
from tslab.services.timeseries_store import seed_werte_csv_columns


def main() -> None:
    parser = argparse.ArgumentParser(description="Werte.csv in PostgreSQL laden")
    parser.add_argument("--csv", default=None, help="Pfad zu Werte.csv")
    parser.add_argument(
        "--columns",
        nargs="*",
        default=None,
        help="Nur diese Spalten (Standard: alle numerischen)",
    )
    args = parser.parse_args()

    init_db()
    with get_session() as session:
        series_list = seed_werte_csv_columns(
            session, csv_path=args.csv, columns=args.columns
        )
    print(f"Importiert: {len(series_list)} Zeitreihen")
    for ts in series_list:
        print(
            f"  - {ts.name} (slug={ts.slug}): "
            f"{ts.observation_count} Werte, {ts.first_date} .. {ts.last_date}"
        )


if __name__ == "__main__":
    main()
