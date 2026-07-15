#!/usr/bin/env python
"""
Kreuzkorrelation zweier Zeitreihen aus PostgreSQL (read-only auf observations).

Beispiele:
  python scripts/run_correlation.py --analysis-mode thesis pdax dax
  python scripts/run_correlation.py --analysis-mode thesis pdax dax --start-date 1987-12-01 --end-date 2007-06-30
  python scripts/run_correlation.py --analysis-mode extended pdax dowjones --max-lag 36
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tslab.db.engine import check_connection, get_session
from tslab.services.analysis_mode import (
    add_analysis_mode_argument,
    get_analysis_mode_config,
    resolve_study_dates_for_mode,
)
from tslab.services.correlation_job import run_correlation_job


def main() -> None:
    parser = argparse.ArgumentParser(description="Kreuzkorrelation (2 Zeitreihen)")
    add_analysis_mode_argument(parser, required=True)
    parser.add_argument("series_a", help="Slug erste Reihe, z. B. pdax")
    parser.add_argument("series_b", help="Slug zweite Reihe, z. B. dax")
    parser.add_argument(
        "--start-date",
        "--start",
        dest="start_date",
        default=None,
        help="Analyse-Start YYYY-MM-DD; sonst Modus-Default",
    )
    parser.add_argument(
        "--end-date",
        "--end",
        dest="end_date",
        default=None,
        help="Analyse-Ende YYYY-MM-DD; sonst Modus-Default",
    )
    parser.add_argument(
        "--max-lag",
        type=int,
        default=24,
        help="Lags von -max-lag bis +max-lag (Standard: 24)",
    )
    args = parser.parse_args()

    mode_config = get_analysis_mode_config(args.analysis_mode)
    eff_start, eff_end = resolve_study_dates_for_mode(
        mode_config, start_date=args.start_date, end_date=args.end_date
    )

    check_connection()

    with get_session() as session:
        job = run_correlation_job(
            session,
            args.series_a,
            args.series_b,
            mode_config=mode_config,
            start_date=eff_start,
            end_date=eff_end,
            max_lag=args.max_lag,
        )

    out = job.output_dir
    print(f"Analysemodus: {mode_config.slug} – {mode_config.label_de}")
    print(f"Fertig: {out}")
    print("  Tabelle: lag_correlations.csv")
    print("  Grafik:  cross_correlation.png, aligned_series.png")
    print("  Historie: correlation_history")


if __name__ == "__main__":
    main()
