"""Erzeugt Diplomarbeit-konforme Prognosegrafiken (Abgleich + Forward)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd

from tslab.services.analysis_mode import AnalysisModeConfig
from tslab.services.forecast_horizons import ForecastHorizons
from tslab.services.forecast_plot_window import ForecastPlotWindow
from tslab.services.level_forecast import (
    format_level_forecast_summary,
    volatility_forecast_to_levels,
    write_level_forecast_table,
)
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
        return VolatilityForecast(empty, empty, {}, index[:0])

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


def _write_level_outputs(
    *,
    fc: VolatilityForecast,
    out_dir: Path,
    file_tag: str,
    title_base: str,
    model_label: str,
    plot_window: ForecastPlotWindow,
    mode_config: AnalysisModeConfig,
    train_prices: pd.Series,
    holdout_prices: pd.Series,
    anchor_price: float,
    anchor_date: pd.Timestamp,
    plot_kind: str,
    horizons: ForecastHorizons,
    forward_actual_prices: pd.Series | None = None,
) -> str | None:
    """Grafik + CSV im PDAX-Niveau; Rueckgabe Text fuer summary.txt."""
    if fc.mean.empty:
        return None

    level_fc = volatility_forecast_to_levels(
        fc,
        anchor_price=anchor_price,
        anchor_date=anchor_date,
        mode_config=mode_config,
        train_prices=train_prices,
    )
    level_vfc = level_fc.as_volatility_forecast()
    suffix = f"_{plot_kind}_levels"

    if plot_kind == "abgleich":
        plot_forecast_abgleich(
            train_prices,
            level_vfc,
            holdout_prices,
            out_dir / f"{file_tag}_forecast{suffix}.png",
            title=f"{title_base} – Prognoseabgleich (PDAX-Niveau)",
            model_label=model_label,
            cutoff=horizons.cutoff,
            holdout_end=horizons.holdout_end,
            plot_window=plot_window,
            y_label="PDAX (Niveau)",
            actual_label="PDAX (Niveau)",
        )
        write_level_forecast_table(
            level_fc,
            out_dir / f"{file_tag}_forecast{suffix}.csv",
            holdout_prices=holdout_prices,
        )
    else:
        actual_for_plot = (
            forward_actual_prices
            if forward_actual_prices is not None
            else train_prices
        )
        plot_forecast_forward(
            actual_for_plot,
            level_vfc,
            out_dir / f"{file_tag}_forecast{suffix}.png",
            title=f"{title_base} – Prognose Forward (PDAX-Niveau)",
            model_label=model_label,
            last_actual=horizons.last_actual,
            plot_window=plot_window,
            y_label="PDAX (Niveau)",
            actual_label="PDAX (Niveau)",
        )
        write_level_forecast_table(
            level_fc,
            out_dir / f"{file_tag}_forecast{suffix}.csv",
        )

    return format_level_forecast_summary(level_fc)


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
    mode_config: AnalysisModeConfig,
    train_prices: pd.Series,
    holdout_prices: pd.Series,
    forward_train_prices: pd.Series,
    price_at_cutoff: float,
    price_at_last_actual: float,
) -> list[str]:
    """Schreibt Abgleichs-/Forward-Grafiken in Renditen und PDAX-Niveau."""
    level_summaries: list[str] = []

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
        txt = _write_level_outputs(
            fc=fc_cmp,
            out_dir=out_dir,
            file_tag=file_tag,
            title_base=title_base,
            model_label=model_label,
            plot_window=plot_window,
            mode_config=mode_config,
            train_prices=train_prices,
            holdout_prices=holdout_prices,
            anchor_price=price_at_cutoff,
            anchor_date=horizons.cutoff,
            plot_kind="abgleich",
            horizons=horizons,
        )
        if txt:
            level_summaries.append(txt)

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
        txt = _write_level_outputs(
            fc=fc_fwd,
            out_dir=out_dir,
            file_tag=file_tag,
            title_base=title_base,
            model_label=model_label,
            plot_window=plot_window,
            mode_config=mode_config,
            train_prices=forward_train_prices,
            holdout_prices=pd.Series(dtype=float),
            anchor_price=price_at_last_actual,
            anchor_date=horizons.last_actual,
            plot_kind="forward",
            horizons=horizons,
            forward_actual_prices=forward_train_prices,
        )
        if txt:
            level_summaries.append(txt)

    return level_summaries
