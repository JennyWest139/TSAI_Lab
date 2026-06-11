"""Erzeugt Diplomarbeit-konforme Prognosegrafiken (Abgleich + Forward)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd

from tslab.services.forecast_horizons import ForecastHorizons
from tslab.services.forecast_plot_window import ForecastPlotWindow
from tslab.services.models_garch import DEFAULT_QUANTILES, VolatilityForecast
from tslab.plots.tsa_plots import plot_forecast_abgleich, plot_forecast_forward


ForecastFactory = Callable[[int, pd.DatetimeIndex], VolatilityForecast]


def arma_volatility_forecast(
    res: object,
    *,
    steps: int,
    index: pd.DatetimeIndex,
    quantiles: tuple[float, ...] = DEFAULT_QUANTILES,
) -> VolatilityForecast:
    """ARMA-Prognose mit konstantem Residuen-Std fuer Quantilbaender."""
    from tslab.services.models_garch import _quantile_bands

    if steps <= 0:
        empty = pd.Series(dtype=float)
        return VolatilityForecast(empty, empty, {}, index[:0])  # noqa: E701

    pred = res.get_forecast(steps=steps).predicted_mean
    mean = pd.Series(pred.values, index=index, name="mean")
    resid_std = float(np.std(res.resid))
    variance = pd.Series(resid_std**2, index=index, name="variance")
    return VolatilityForecast(
        mean=mean,
        variance=variance,
        quantiles=_quantile_bands(mean, variance, quantiles),
        index=index,
    )


def write_thesis_forecast_plots(
    *,
    train_lr: pd.Series,
    holdout_lr: pd.Series,
    horizons: ForecastHorizons,
    forward_train_lr: pd.Series,
    forecast_factory: ForecastFactory,
    forward_forecast_factory: ForecastFactory | None,
    out_dir: Path,
    file_tag: str,
    title_base: str,
    model_label: str,
    plot_window: ForecastPlotWindow,
    y_label: str,
) -> None:
    """Schreibt Abgleichs- und Forward-Grafik (Diplomarbeit-Layout)."""
    comp_steps = len(horizons.comparison_index)
    if comp_steps > 0:
        fc_cmp = forecast_factory(comp_steps, horizons.comparison_index)
        plot_forecast_abgleich(
            train_lr,
            fc_cmp,
            holdout_lr,
            out_dir / f"{file_tag}_forecast_abgleich.png",
            title=f"{title_base} – Prognoseabgleich",
            model_label=model_label,
            cutoff=horizons.cutoff,
            holdout_end=horizons.holdout_end,
            plot_window=plot_window,
            y_label=y_label,
        )

    fwd_factory = forward_forecast_factory or forecast_factory
    fwd_steps = len(horizons.forward_index)
    if fwd_steps > 0:
        fc_fwd = fwd_factory(fwd_steps, horizons.forward_index)
        plot_forecast_forward(
            forward_train_lr,
            fc_fwd,
            out_dir / f"{file_tag}_forecast_forward.png",
            title=f"{title_base} – Prognose ab letztem Istwert",
            model_label=model_label,
            last_actual=horizons.last_actual,
            plot_window=plot_window,
            y_label=y_label,
        )
