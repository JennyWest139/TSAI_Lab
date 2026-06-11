"""Gemeinsamer Kontext fuer TSA-Laeufe (Phase 1)."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sqlalchemy.orm import Session

from tslab.services.analysis_window import StudyDates, prepare_tsa_split, resolve_study_dates
from tslab.services.forecast_context import ForecastPlotData, build_forecast_plot_data
from tslab.services.timeseries_store import load_pdax_full
from tslab.services.transforms import log_returns, log_returns_detrended


@dataclass(frozen=True)
class TSAContext:
    study: StudyDates
    train_lr: pd.Series
    holdout_lr: pd.Series
    forecast_ctx: ForecastPlotData
    label: str


def load_tsa_context(
    session: Session,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    forecast_end: str | None = None,
) -> TSAContext:
    pdax_full = load_pdax_full(session)
    study = resolve_study_dates(
        pdax_full,
        mode="tsa",
        start_date=start_date,
        end_date=end_date,
        forecast_end=forecast_end,
    )
    split = prepare_tsa_split(pdax_full, study)
    forecast_ctx = build_forecast_plot_data(pdax_full, study)
    train_lr = log_returns_detrended(split.train)

    if forecast_ctx.holdout_actual.empty:
        holdout_lr = pd.Series(dtype=float)
    else:
        combo = pd.concat([split.train, forecast_ctx.holdout_actual])
        holdout_lr = log_returns(combo).loc[forecast_ctx.holdout_actual.index]

    label = f"{study.start_date.date()}_to_{study.cutoff.date()}"
    return TSAContext(
        study=study,
        train_lr=train_lr,
        holdout_lr=holdout_lr,
        forecast_ctx=forecast_ctx,
        label=label,
    )
