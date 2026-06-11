#!/usr/bin/env python
"""
Phase 0: PDAX aus Werte.csv laden, Cutoff setzen, Kerngrafiken erzeugen.

Aufruf (im Projektroot):
  python scripts/run_phase0_pdax.py
  python scripts/run_phase0_pdax.py --cutoff 2005-12-31
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tslab.config_loader import load_defaults, resolve_output_dir
from tslab.plots import time_series_plots as plots
from tslab.plots.series_display import (
    PDAX_LOG,
    PDAX_LOG_RETURNS,
    PDAX_ORIGINAL,
    SeriesDisplay,
)
from tslab.db.engine import get_session
from tslab.services.analysis_window import prepare_tsa_split, resolve_study_dates
from tslab.services.forecast_context import build_forecast_plot_data
from tslab.services.ingest_werte import load_pdax_series
from tslab.services.timeseries_store import load_pdax_full
from tslab.services.models_ar import fit_ar
from tslab.services.models_arma import fit_arma
from tslab.services.transforms import log_levels, log_returns_detrended


def _run_variant(
    y_train: pd.Series,
    out_base: Path,
    variant_id: str,
    display: SeriesDisplay,
    *,
    do_decomp: bool = False,
    decomp_multiplicative: bool = True,
    do_exp: bool = False,
    ar_lags: list[int] | None = None,
) -> None:
    ar_lags = ar_lags or []
    print(f"  >> Grafiken: {display.short_name} ...", flush=True)

    if do_decomp:
        created = plots.plot_decompositions(
            y_train,
            out_base,
            variant_id,
            display,
            include_multiplicative=decomp_multiplicative,
        )
        print(f"     Zerlegung: {', '.join(created)}", flush=True)
    if do_exp:
        plots.plot_fitted_exponential(
            y_train, out_base / f"{variant_id}_exp_trend.png", display
        )

    plots.plot_histogram(y_train, out_base / f"{variant_id}_histogram.png", display)
    plots.plot_series(y_train, out_base / f"{variant_id}_series.png", display)
    plots.plot_acf(y_train, out_base / f"{variant_id}_acf.png", display)
    plots.plot_pacf(y_train, out_base / f"{variant_id}_pacf.png", display)
    plots.plot_spectral_density(
        y_train, out_base / f"{variant_id}_spectral.png", display
    )
    plots.plot_periodogram(y_train, out_base / f"{variant_id}_periodogram.png", display)

    for lag in ar_lags:
        if lag == 0:
            fitted = pd.Series(y_train.mean(), index=y_train.index, name="fitted")
            tag = "AR0"
        else:
            _, fitted = fit_ar(y_train, lag)
            tag = f"AR{lag}"
        resid_display = display.ar_residuals(lag)
        plots.plot_residuals(
            y_train.loc[fitted.index],
            fitted,
            out_base / f"{variant_id}_{tag}_residuals.png",
            resid_display,
        )


def main() -> None:
    cfg = load_defaults()
    parser = argparse.ArgumentParser(description="Phase 0 PDAX-Analyse")
    parser.add_argument(
        "--start-date",
        default=None,
        help="Analyse-Start (YYYY-MM-DD); Standard: erstes verfuegbares Datum",
    )
    parser.add_argument(
        "--end-date",
        default=None,
        help="Analyse-Ende = Cutoff (YYYY-MM-DD); Standard: letztes Datum",
    )
    parser.add_argument(
        "--forecast-end",
        default=None,
        help="TSA: Prognose bis (Standard: letztes verfuegbares Datum)",
    )
    parser.add_argument(
        "--from-db",
        action="store_true",
        help="PDAX aus PostgreSQL laden (slug pdax)",
    )
    parser.add_argument("--csv", default=None, help="Alternativer Pfad zu Werte.csv")
    args = parser.parse_args()

    if args.from_db:
        with get_session() as session:
            pdax_full = load_pdax_full(session, prefer_db=True)
    elif args.csv:
        pdax_full = load_pdax_series(args.csv)
    else:
        try:
            with get_session() as session:
                pdax_full = load_pdax_full(session, prefer_db=True)
        except Exception:
            pdax_full = load_pdax_series()

    study = resolve_study_dates(
        pdax_full,
        mode="tsa",
        start_date=args.start_date,
        end_date=args.end_date,
        forecast_end=args.forecast_end,
    )
    split = prepare_tsa_split(pdax_full, study)
    forecast_ctx = build_forecast_plot_data(pdax_full, study)
    train = split.train
    holdout = split.holdout_actual
    cutoff = str(study.cutoff.date())

    out = resolve_output_dir(cfg) / (
        f"phase0_{study.start_date.date()}_to_{cutoff}"
    )
    out.mkdir(parents=True, exist_ok=True)

    summary = {
        "mode": "tsa",
        "analysis": study.analysis_label,
        "cutoff": cutoff,
        "cutoff_equals_end": study.cutoff == study.end_date,
        "forecast_period": study.forecast_label,
        "rows_full_series": len(pdax_full),
        "train": len(train),
        "holdout_for_forecast_plots": len(holdout),
        "train_start": str(train.index.min().date()),
        "train_end": str(train.index.max().date()),
        "pdax_min": float(train.min()),
        "pdax_max": float(train.max()),
    }
    (out / "summary.txt").write_text(
        "\n".join(f"{k}: {v}" for k, v in summary.items()), encoding="utf-8"
    )

    print(f"Analyse: {study.analysis_label}", flush=True)
    print(f"Cutoff (= Ende): {cutoff}", flush=True)
    print(f"Prognosezeitraum: {study.forecast_label}", flush=True)
    print(f"Training: {len(train)} Punkte", flush=True)
    print(f"Ausgabe: {out}", flush=True)
    print("Erzeuge Plots (ca. 1-2 Min.) ...", flush=True)

    # 1) PDAX Niveau – AR(1), Zerlegung, Exponential
    _run_variant(
        train,
        out / "pdax_levels",
        "pdax_levels",
        PDAX_ORIGINAL,
        do_decomp=True,
        decomp_multiplicative=True,
        do_exp=True,
        ar_lags=[1],
    )

    # 2) log(PDAX) – AR(0), additive + multiplikative Zerlegung
    lg = log_levels(train)
    _run_variant(
        lg,
        out / "pdax_log",
        "pdax_log",
        PDAX_LOG,
        do_decomp=True,
        decomp_multiplicative=True,
        ar_lags=[0],
    )

    # 3) trendbereinigte log-Renditen – AR(0), AR(1); nur additive Zerlegung (neg. Werte)
    lr = log_returns_detrended(train)
    _run_variant(
        lr,
        out / "pdax_log_returns",
        "pdax_log_returns",
        PDAX_LOG_RETURNS,
        do_decomp=True,
        decomp_multiplicative=False,
        ar_lags=[0, 1],
    )
    _, arma_fitted = fit_arma(lr, order=(1, 1))
    arma_display = SeriesDisplay(
        short_name="Residuen nach ARMA(1,1)",
        value_axis="Residuen (ARMA(1,1))",
        data_basis=(
            "Modelloutput: Residuen aus ARMA(1,1), "
            f"angepasst an: {PDAX_LOG_RETURNS.data_basis}"
        ),
    )
    plots.plot_residuals(
        lr.loc[arma_fitted.index],
        arma_fitted,
        out / "pdax_log_returns" / "pdax_log_returns_ARMA11_residuals.png",
        arma_display,
    )

    n_png = len(list(out.rglob("*.png")))
    if forecast_ctx.has_actuals_for_comparison:
        print(
            f"Holdout-Istwerte fuer Prognoseplots: {len(holdout)} Monate "
            f"({holdout.index.min().date()} .. {holdout.index.max().date()})",
            flush=True,
        )
    print(f"Phase 0 fertig. ({n_png} PNG-Dateien in {out.name})", flush=True)


if __name__ == "__main__":
    main()
