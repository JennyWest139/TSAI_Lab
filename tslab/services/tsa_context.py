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
from tslab.services.forecast_horizons import ForecastHorizons, build_forecast_horizons
from tslab.services.forecast_plot_window import ForecastPlotWindow
from tslab.services.timeseries_store import load_series_full_pandas


@dataclass(frozen=True)
class TSAContext:
    mode_config: AnalysisModeConfig
    study: StudyDates
    train_lr: pd.Series
    holdout_lr: pd.Series
    forward_train_lr: pd.Series
    train_prices: pd.Series
    holdout_prices: pd.Series
    forward_train_prices: pd.Series
    price_at_cutoff: float
    price_at_last_actual: float
    forecast_ctx: ForecastPlotData
    horizons: ForecastHorizons
    label: str
    series_slug: str


def load_tsa_context(
    session: Session,
    mode_config: AnalysisModeConfig,
    *,
    series_slug: str = "pdax",
    start_date: str | None = None,
    end_date: str | None = None,
    forecast_end: str | None = None,
    plot_window: ForecastPlotWindow | None = None,
) -> TSAContext:
    pdax_full = load_series_full_pandas(session, series_slug)
    eff_window = plot_window or ForecastPlotWindow.from_defaults(load_defaults())
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

    horizons = build_forecast_horizons(
        pdax_full,
        cutoff=study.cutoff,
        forecast_end=study.forecast_end,
        plot_window=eff_window,
    )

    data_end = min(study.forecast_end, study.available_end)
    price_through_forecast = pdax_full.loc[
        (pdax_full.index >= study.start_date) & (pdax_full.index <= data_end)
    ]
    lr_through_forecast = prepare_model_returns(price_through_forecast, mode_config)
    holdout_lr = lr_through_forecast.loc[lr_through_forecast.index > study.cutoff]

    price_through_last = pdax_full.loc[
        (pdax_full.index >= study.start_date)
        & (pdax_full.index <= horizons.last_actual)
    ]
    forward_train_lr = prepare_model_returns(price_through_last, mode_config)

    train_prices = split.train
    holdout_prices = forecast_ctx.holdout_actual
    forward_train_prices = price_through_last
    price_at_cutoff = float(train_prices.iloc[-1])
    price_at_last_actual = float(
        pdax_full.loc[pdax_full.index <= horizons.last_actual].iloc[-1]
    )

    label = f"{mode_config.slug}_{study.start_date.date()}_to_{study.cutoff.date()}"
    return TSAContext(
        mode_config=mode_config,
        study=study,
        train_lr=train_lr,
        holdout_lr=holdout_lr,
        forward_train_lr=forward_train_lr,
        train_prices=train_prices,
        holdout_prices=holdout_prices,
        forward_train_prices=forward_train_prices,
        price_at_cutoff=price_at_cutoff,
        price_at_last_actual=price_at_last_actual,
        forecast_ctx=forecast_ctx,
        horizons=horizons,
        label=label,
        series_slug=series_slug,
    )


def mode_config_from_value(mode_value: str) -> AnalysisModeConfig:
    from tslab.services.analysis_mode import parse_analysis_mode

    return get_analysis_mode_config(parse_analysis_mode(mode_value))
