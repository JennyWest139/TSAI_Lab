"""Sichtfenster fuer Prognosegrafiken (Historie + Prognose + Verlaengerung)."""

from __future__ import annotations

import argparse
from dataclasses import dataclass

import pandas as pd

from tslab.config_loader import load_defaults
from tslab.services.models_garch import VolatilityForecast


@dataclass(frozen=True)
class ForecastPlotWindow:
    """X-Achsen-Fenster fuer Prognoseplots (Default: 3 J. / 1 J. / 1 J.)."""

    pre_years: float = 3.0
    forecast_years: float = 1.0
    post_years: float = 1.0

    @classmethod
    def from_defaults(cls, cfg: dict | None = None) -> ForecastPlotWindow:
        cfg = cfg or load_defaults()
        section = cfg.get("forecast_plot_window") or {}
        return cls(
            pre_years=float(section.get("pre_years", 3)),
            forecast_years=float(section.get("forecast_years", 1)),
            post_years=float(section.get("post_years", 1)),
        )

    @property
    def label_de(self) -> str:
        return (
            f"{self.pre_years:g} J. vor Prognose, "
            f"{self.forecast_years:g} J. Prognose, "
            f"{self.post_years:g} J. danach (falls verfuegbar)"
        )


def resolve_forecast_plot_window(
    *,
    pre_years: float | None = None,
    forecast_years: float | None = None,
    post_years: float | None = None,
    cfg: dict | None = None,
) -> ForecastPlotWindow:
    base = ForecastPlotWindow.from_defaults(cfg)
    return ForecastPlotWindow(
        pre_years=pre_years if pre_years is not None else base.pre_years,
        forecast_years=forecast_years if forecast_years is not None else base.forecast_years,
        post_years=post_years if post_years is not None else base.post_years,
    )


def add_forecast_plot_window_arguments(parser: argparse.ArgumentParser) -> None:
    """CLI-Parameter; Defaults aus config/defaults.yaml."""
    defaults = ForecastPlotWindow.from_defaults()
    parser.add_argument(
        "--plot-pre-years",
        type=float,
        default=None,
        metavar="YEARS",
        help=(
            f"Jahre Training vor Prognosebeginn in Grafiken "
            f"(Default: {defaults.pre_years:g})"
        ),
    )
    parser.add_argument(
        "--plot-forecast-years",
        type=float,
        default=None,
        metavar="YEARS",
        help=(
            f"Jahre Prognosehorizont in Grafiken "
            f"(Default: {defaults.forecast_years:g})"
        ),
    )
    parser.add_argument(
        "--plot-post-years",
        type=float,
        default=None,
        metavar="YEARS",
        help=(
            f"Zusaetzliche Jahre nach Prognosehorizont (Holdout/Quantile), "
            f"falls Daten vorliegen (Default: {defaults.post_years:g})"
        ),
    )


def forecast_plot_window_from_args(args: argparse.Namespace) -> ForecastPlotWindow:
    return resolve_forecast_plot_window(
        pre_years=args.plot_pre_years,
        forecast_years=args.plot_forecast_years,
        post_years=args.plot_post_years,
    )


def _months(years: float) -> int:
    return max(0, int(round(years * 12)))


def _step_offset(index: pd.DatetimeIndex) -> pd.tseries.frequencies.DateOffset:
    freq = pd.infer_freq(index)
    if freq:
        return pd.tseries.frequencies.to_offset(freq)
    return pd.tseries.frequencies.to_offset("MS")


def resolve_forecast_plot_bounds(
    cutoff: pd.Timestamp,
    forecast_index: pd.DatetimeIndex,
    holdout: pd.Series,
    window: ForecastPlotWindow,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Linke/rechte X-Grenze fuer Prognoseplots."""
    cutoff = pd.Timestamp(cutoff)
    plot_start = cutoff - pd.DateOffset(months=_months(window.pre_years))

    if len(forecast_index) == 0:
        return plot_start, cutoff

    step = _step_offset(forecast_index)
    first_fc = pd.Timestamp(forecast_index[0])
    fc_steps = max(1, _months(window.forecast_years))
    primary_fc_end = first_fc + step * (fc_steps - 1)

    candidates: list[pd.Timestamp] = [primary_fc_end]
    fc_primary = forecast_index[forecast_index <= primary_fc_end]
    if len(fc_primary) > 0:
        candidates.append(pd.Timestamp(fc_primary.max()))
    if not holdout.empty:
        ho_primary = holdout.index[holdout.index <= primary_fc_end]
        if len(ho_primary) > 0:
            candidates.append(pd.Timestamp(ho_primary.max()))

    post_steps = _months(window.post_years)
    if post_steps > 0:
        extended_end = primary_fc_end + step * post_steps
        fc_post = forecast_index[
            (forecast_index > primary_fc_end) & (forecast_index <= extended_end)
        ]
        if len(fc_post) > 0:
            candidates.append(pd.Timestamp(fc_post.max()))
        if not holdout.empty:
            ho_post = holdout.index[
                (holdout.index > primary_fc_end) & (holdout.index <= extended_end)
            ]
            if len(ho_post) > 0:
                candidates.append(pd.Timestamp(ho_post.max()))

    plot_end = max(candidates)
    return plot_start, plot_end


def _slice_indexed(index: pd.DatetimeIndex, start: pd.Timestamp, end: pd.Timestamp) -> pd.DatetimeIndex:
    mask = (index >= start) & (index <= end)
    return index[mask]


def slice_series_for_forecast_plot(
    series: pd.Series,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.Series:
    if series.empty:
        return series
    mask = (series.index >= start) & (series.index <= end)
    return series.loc[mask]


def slice_train_for_forecast_plot(
    train: pd.Series,
    cutoff: pd.Timestamp,
    plot_start: pd.Timestamp,
) -> pd.Series:
    if train.empty:
        return train
    mask = (train.index >= plot_start) & (train.index <= cutoff)
    return train.loc[mask]


def slice_holdout_for_forecast_plot(
    holdout: pd.Series,
    cutoff: pd.Timestamp,
    plot_end: pd.Timestamp,
) -> pd.Series:
    if holdout.empty:
        return holdout
    mask = (holdout.index > cutoff) & (holdout.index <= plot_end)
    return holdout.loc[mask]


def slice_volatility_forecast(
    forecast: VolatilityForecast,
    plot_start: pd.Timestamp,
    plot_end: pd.Timestamp,
) -> VolatilityForecast:
    idx = _slice_indexed(forecast.index, plot_start, plot_end)
    if len(idx) == 0:
        return VolatilityForecast(
            mean=pd.Series(dtype=float),
            variance=pd.Series(dtype=float),
            quantiles={},
            index=pd.DatetimeIndex([]),
        )
    return VolatilityForecast(
        mean=forecast.mean.reindex(idx).dropna(),
        variance=forecast.variance.reindex(idx).dropna(),
        quantiles={q: s.reindex(idx).dropna() for q, s in forecast.quantiles.items()},
        index=idx,
    )


def apply_forecast_plot_window(
    train: pd.Series,
    forecast: VolatilityForecast,
    holdout: pd.Series,
    cutoff: pd.Timestamp,
    window: ForecastPlotWindow,
) -> tuple[pd.Series, VolatilityForecast, pd.Series, pd.Timestamp, pd.Timestamp]:
    """Schneidet Trainings-, Prognose- und Holdout-Reihen auf das Anzeigefenster."""
    plot_start, plot_end = resolve_forecast_plot_bounds(
        cutoff, forecast.index, holdout, window
    )
    train_plot = slice_train_for_forecast_plot(train, cutoff, plot_start)
    holdout_plot = slice_holdout_for_forecast_plot(holdout, cutoff, plot_end)
    forecast_plot = slice_volatility_forecast(forecast, plot_start, plot_end)
    return train_plot, forecast_plot, holdout_plot, plot_start, plot_end
