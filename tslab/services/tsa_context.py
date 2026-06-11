"""Gemeinsamer Kontext fuer TSA-Laeufe (Phase 1)."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sqlalchemy.orm import Session

from tslab.config_loader import load_defaults
from tslab.services.analysis_mode import (
    AnalysisModeConfig,
    get_analysis_mode_config,
    prepare_model_returns,
    resolve_study_dates_for_mode,
)
from tslab.services.analysis_window import StudyDates, prepare_tsa_split, resolve_study_dates
from tslab.services.forecast_context import ForecastPlotData, build_forecast_plot_data
from tslab.services.timeseries_store import load_pdax_full
from tslab.services.transforms import log_returns


@dataclass(frozen=True)
class TSAContext:
    mode_config: AnalysisModeConfig
    study: StudyDates
    train_lr: pd.Series
    holdout_lr: pd.Series
    forecast_ctx: ForecastPlotData
    label: str


def load_tsa_context(
    session: Session,
    mode_config: AnalysisModeConfig,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    forecast_end: str | None = None,
) -> TSAContext:
    pdax_full = load_pdax_full(session)
    eff_start, eff_end = resolve_study_dates_for_mode(
        mode_config, start_date=start_date, end_date=end_date
    )
    if eff_end is None and mode_config.mode.value == "extended":
        eff_end = load_defaults().get("default_cutoff")

    study = resolve_study_dates(
        pdax_full,
        mode="tsa",
        start_date=eff_start,
        end_date=eff_end,
        forecast_end=forecast_end,
    )
    split = prepare_tsa_split(pdax_full, study)
    forecast_ctx = build_forecast_plot_data(pdax_full, study)
    train_lr = prepare_model_returns(split.train, mode_config)

    if forecast_ctx.holdout_actual.empty:
        holdout_lr = pd.Series(dtype=float)
    else:
        combo = pd.concat([split.train, forecast_ctx.holdout_actual])
        holdout_lr = log_returns(combo).loc[forecast_ctx.holdout_actual.index]

    label = f"{mode_config.slug}_{study.start_date.date()}_to_{study.cutoff.date()}"
    return TSAContext(
        mode_config=mode_config,
        study=study,
        train_lr=train_lr,
        holdout_lr=holdout_lr,
        forecast_ctx=forecast_ctx,
        label=label,
    )


def mode_config_from_value(mode_value: str) -> AnalysisModeConfig:
    from tslab.services.analysis_mode import parse_analysis_mode

    return get_analysis_mode_config(parse_analysis_mode(mode_value))
