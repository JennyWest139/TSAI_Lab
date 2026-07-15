#!/usr/bin/env python
"""
Zeitreihe laden und Datumslogik testen.

Korrelation (nur Start/Ende):
  python scripts/db_load_series.py pdax --mode correlation --from-csv --start 1987-12-01 --end 2007-06-30

TSA (Ende = Cutoff; Prognose bis letztes verfuegbares Datum):
  python scripts/db_load_series.py pdax --mode tsa --from-csv --start 1987-12-01 --end 2007-06-30
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tslab.db.engine import SETUP_HINT, DatabaseConnectionError, check_connection, get_session
from tslab.services.analysis_window import (
    prepare_correlation_series,
    prepare_tsa_split,
    resolve_study_dates,
)
from tslab.services.ingest_werte import load_pdax_series
from tslab.services.timeseries_store import load_series_full_pandas


def _load_full(series_name: str, from_csv: bool, session) -> pd.Series:
    if from_csv:
        if series_name.lower() != "pdax":
            raise SystemExit("--from-csv aktuell nur fuer pdax.")
        return load_pdax_series()
    return load_series_full_pandas(session, series_name)


def main() -> None:
    parser = argparse.ArgumentParser(description="ZR laden + Datumslogik")
    parser.add_argument("series", help="Slug, z. B. pdax")
    parser.add_argument(
        "--mode",
        choices=("correlation", "tsa"),
        default="tsa",
        help="correlation: nur Start/Ende; tsa: Ende = Cutoff",
    )
    parser.add_argument("--start", default=None, help="Analyse-Start (YYYY-MM-DD)")
    parser.add_argument(
        "--end",
        default=None,
        help="Analyse-Ende; bei TSA gleich Cutoff (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--cutoff",
        default=None,
        help="Nur wenn --end fehlt: Stichtag TSA (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--forecast-end",
        default=None,
        help="TSA: Prognose bis (Standard: letztes verfuegbares Datum)",
    )
    parser.add_argument("--from-csv", action="store_true", help="Werte.csv statt DB")
    args = parser.parse_args()

    if args.from_csv:
        full = _load_full(args.series, True, None)
        source = "Werte.csv"
    else:
        try:
            check_connection()
        except DatabaseConnectionError as exc:
            print(exc, file=sys.stderr)
            print(SETUP_HINT, file=sys.stderr)
            sys.exit(1)
        with get_session() as session:
            full = _load_full(args.series, False, session)
        source = "Datenbank"

    study = resolve_study_dates(
        full,
        mode=args.mode,
        start_date=args.start,
        end_date=args.end,
        cutoff=args.cutoff,
        forecast_end=args.forecast_end,
    )

    print(f"Quelle: {source}")
    print(f"Modus: {study.mode}")
    print(f"Verfuegbar: {study.available_start.date()} .. {study.available_end.date()}")
    print(f"Analyse:    {study.analysis_label}")

    if study.mode == "correlation":
        s = prepare_correlation_series(full, study)
        print(f"Punkte (Corr): {len(s)}")
    else:
        print(f"Cutoff (= Ende): {study.cutoff.date()}")
        print(f"Prognosezeitraum: {study.forecast_label}")
        split = prepare_tsa_split(full, study)
        print(f"Training: {len(split.train)} Punkte")
        print(
            f"Holdout-Istwerte fuer Prognoseplots: {len(split.holdout_actual)} Punkte"
        )
        if split.has_holdout:
            print(
                f"  Ist von {split.holdout_actual.index.min().date()} "
                f"bis {split.holdout_actual.index.max().date()}"
            )


if __name__ == "__main__":
    main()
