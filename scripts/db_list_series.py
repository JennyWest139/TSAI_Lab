#!/usr/bin/env python
"""Zeitreihen in PostgreSQL auflisten."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tslab.db.engine import get_session
from tslab.services.timeseries_store import list_series


def main() -> None:
    with get_session() as session:
        for ts in list_series(session):
            print(
                f"{ts.id:3d}  {ts.slug:20s}  {ts.name:15s}  "
                f"{ts.first_date} .. {ts.last_date}  ({ts.observation_count} Punkte)"
            )


if __name__ == "__main__":
    main()
