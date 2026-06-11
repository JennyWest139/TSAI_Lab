#!/usr/bin/env python
"""
Phase 1 (TSA): ARMA auf trendbereinigten log-Renditen, Prognose vs. Holdout.

Beispiel:
  python scripts/run_tsa.py --end-date 2007-06-30
  python scripts/run_tsa.py --from-db --end-date 2007-06-30 --order 1,1
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tslab.config_loader import resolve_output_dir
from tslab.db.engine import check_connection, get_session
from tslab.plots.time_series_plots import plot_residuals, plot_series
from tslab.plots.series_display import SeriesDisplay
from tslab.services.analysis_window import prepare_tsa_split, resolve_study_dates
from tslab.services.forecast_context import build_forecast_plot_data
from tslab.services.models_arma import fit_arma
from tslab.services.timeseries_store import load_pdax_full
from tslab.services.transforms import log_returns, log_returns_detrended

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image


def _save_forecast_plot(
    train: pd.Series,
    forecast: pd.Series,
    holdout: pd.Series,
    path: Path,
    *,
    title: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    train.plot(ax=ax, color="#1f4e79", lw=1.0, label="Training")
    if not forecast.empty:
        forecast.plot(ax=ax, color="#c55a11", lw=1.5, label="Prognose")
    if not holdout.empty:
        holdout.plot(ax=ax, color="#548235", lw=1.2, ls="--", label="Ist (Holdout)")
    ax.axvline(train.index.max(), color="gray", ls=":", lw=0.8)
    ax.set_title(title)
    ax.set_xlabel("Zeit (Monatsdaten)")
    ax.set_ylabel("Transformiert: diff(ln(PDAX)), linear trendbereinigt")
    ax.legend(loc="upper left", fontsize=8)
    fig.subplots_adjust(bottom=0.14)
    tmp = path.with_name(f"{path.stem}_write.png")
    fig.savefig(tmp, format="png", dpi=120, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    with Image.open(tmp) as im:
        im.convert("RGB").save(path, format="PNG")
    tmp.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 1 TSA (ARMA)")
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None, help="Cutoff YYYY-MM-DD")
    parser.add_argument("--forecast-end", default=None)
    parser.add_argument("--from-db", action="store_true")
    parser.add_argument(
        "--order",
        default="1,1",
        help="ARMA(p,q) als p,q (Standard: 1,1)",
    )
    args = parser.parse_args()

    p, q = (int(x.strip()) for x in args.order.split(","))
    check_connection()

    with get_session() as session:
        pdax_full = load_pdax_full(session, prefer_db=True)

    study = resolve_study_dates(
        pdax_full,
        mode="tsa",
        start_date=args.start_date,
        end_date=args.end_date,
        forecast_end=args.forecast_end,
    )
    split = prepare_tsa_split(pdax_full, study)
    forecast_ctx = build_forecast_plot_data(pdax_full, study)

    train_lr = log_returns_detrended(split.train)
    res, fitted = fit_arma(train_lr, order=(p, q))

    if forecast_ctx.forecast_index.empty:
        fc = pd.Series(dtype=float)
    else:
        steps = len(forecast_ctx.forecast_index)
        pred = res.get_forecast(steps=steps).predicted_mean
        fc = pd.Series(pred.values, index=forecast_ctx.forecast_index, name="forecast")

    label = f"{study.start_date.date()}_to_{study.cutoff.date()}"
    out = resolve_output_dir() / f"tsa_arma{p}{q}_{label}"
    out.mkdir(parents=True, exist_ok=True)

    display = SeriesDisplay(
        short_name=f"ARMA({p},{q}) auf kont. Renditen",
        value_axis="Transformiert: diff(ln(PDAX)), linear trendbereinigt",
        data_basis=train_lr.name or "log_returns_detrended",
    )
    plot_series(train_lr, out / "series_train.png", display)
    plot_residuals(
        train_lr.loc[fitted.index],
        fitted,
        out / f"arma{p}{q}_residuals.png",
        SeriesDisplay(
            short_name=f"Residuen nach ARMA({p},{q})",
            value_axis=f"Residuen (ARMA({p},{q}))",
            data_basis=display.data_basis,
        ),
    )
    if not forecast_ctx.holdout_actual.empty:
        combo = pd.concat([split.train, forecast_ctx.holdout_actual])
        holdout_lr = log_returns(combo).loc[forecast_ctx.holdout_actual.index]
    else:
        holdout_lr = pd.Series(dtype=float)

    _save_forecast_plot(
        train_lr,
        fc,
        holdout_lr,
        out / f"arma{p}{q}_forecast_holdout.png",
        title=f"ARMA({p},{q}) Prognose vs. Holdout – {study.analysis_label}",
    )

    summary = [
        f"Modell: ARMA({p},{q})",
        f"Analyse: {study.analysis_label}",
        f"Cutoff: {study.cutoff.date()}",
        f"Training (Renditen): {len(train_lr)}",
        f"Holdout Monate: {len(forecast_ctx.holdout_actual)}",
        "",
        str(res.summary()),
    ]
    (out / "summary.txt").write_text("\n".join(summary), encoding="utf-8")

    print(f"Fertig: {out}")
    print(f"  ARMA({p},{q}) AIC={res.aic:.2f}")
    if not fc.empty:
        print(f"  Prognose: {len(fc)} Schritte bis {fc.index.max().date()}")


if __name__ == "__main__":
    main()
