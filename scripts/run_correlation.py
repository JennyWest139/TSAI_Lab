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

from tslab.config_loader import resolve_output_dir
from tslab.db.engine import check_connection, get_session
from tslab.db.models import CorrelationHistory
from tslab.plots.correlation_plots import plot_aligned_series, plot_cross_correlation_bars
from tslab.services.analysis_mode import (
    add_analysis_mode_argument,
    get_analysis_mode_config,
    resolve_study_dates_for_mode,
)
from tslab.services.correlation import run_correlation


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
        result = run_correlation(
            session,
            args.series_a,
            args.series_b,
            mode_config=mode_config,
            start_date=eff_start,
            end_date=eff_end,
            max_lag=args.max_lag,
        )

    label = f"{result.study.start_date.date()}_to_{result.study.end_date.date()}"
    out = (
        resolve_output_dir()
        / f"correlation_{mode_config.slug}_{result.series_a}_vs_{result.series_b}_{label}"
    )
    out.mkdir(parents=True, exist_ok=True)

    csv_path = out / "lag_correlations.csv"
    result.table.to_csv(csv_path, index=False, encoding="utf-8-sig")

    plot_cross_correlation_bars(result, out / "cross_correlation.png")
    plot_aligned_series(
        result,
        result.series_a_values,
        result.series_b_values,
        out / "aligned_series.png",
    )

    summary_lines = [
        f"Analysemodus: {mode_config.slug} ({mode_config.label_de})",
        f"Datenbasis: {result.data_basis}",
        f"Serie A: {result.series_a}",
        f"Serie B: {result.series_b}",
        f"Analysefenster: {result.study.analysis_label}",
        f"Gemeinsame Beobachtungen: {result.aligned_observations}",
        f"Lags: -{args.max_lag} .. +{args.max_lag}",
        result.lag_definition,
        "",
        "Top 5 |Korrelation|:",
    ]
    top = (
        result.table.dropna(subset=["correlation"])
        .assign(abs_r=lambda d: d["correlation"].abs())
        .sort_values("abs_r", ascending=False)
        .head(5)
    )
    for _, row in top.iterrows():
        summary_lines.append(
            f"  lag={int(row['lag']):4d}  r={row['correlation']:+.4f}  n={int(row['n_obs'])}"
        )
    if result.best_lag is not None:
        br = result.table.loc[result.table["lag"] == result.best_lag].iloc[0]
        summary_lines.append(
            f"\nStaerkstes |r|: lag={result.best_lag}, r={br['correlation']:+.4f}"
        )

    summary_path = out / "summary.txt"
    summary_path.write_text("\n".join(summary_lines), encoding="utf-8")

    best_r = None
    if result.best_lag is not None:
        best_r = float(
            result.table.loc[result.table["lag"] == result.best_lag, "correlation"].iloc[0]
        )

    with get_session() as session:
        session.add(
            CorrelationHistory(
                series_a_slug=result.series_a,
                series_b_slug=result.series_b,
                start_date=result.study.start_date.date(),
                end_date=result.study.end_date.date(),
                max_lag=args.max_lag,
                aligned_observations=result.aligned_observations,
                best_lag=result.best_lag,
                best_correlation=best_r,
                output_dir=str(out),
            )
        )
        session.commit()

    print(f"Analysemodus: {mode_config.slug} – {mode_config.label_de}")
    print(f"Fertig: {out}")
    print(f"  Tabelle: {csv_path.name}")
    print(f"  Grafik:  cross_correlation.png, aligned_series.png")
    print(f"  Historie: correlation_history (PostgreSQL)")


if __name__ == "__main__":
    main()
