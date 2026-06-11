"""Prognose-Indizes fuer Abgleichs- und Forward-Grafiken (Diplomarbeit-Stil)."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from tslab.services.forecast_plot_window import ForecastPlotWindow, _months


@dataclass(frozen=True)
class ForecastHorizons:
    """Zeitachsen fuer die beiden Prognosegrafiken."""

    comparison_index: pd.DatetimeIndex
    forward_index: pd.DatetimeIndex
    cutoff: pd.Timestamp
    last_actual: pd.Timestamp
    holdout_end: pd.Timestamp | None

    @property
    def has_holdout_overlap(self) -> bool:
        return self.holdout_end is not None and self.holdout_end > self.cutoff


def _monthly_range(start: pd.Timestamp, end: pd.Timestamp, freq: str) -> pd.DatetimeIndex:
    if start > end:
        return pd.DatetimeIndex([])
    return pd.date_range(start=start, end=end, freq=freq)


def build_forecast_horizons(
    full_series: pd.Series,
    *,
    cutoff: pd.Timestamp,
    forecast_end: pd.Timestamp,
    plot_window: ForecastPlotWindow,
) -> ForecastHorizons:
    """
    comparison_index: ab Monat nach Cutoff (Abgleich Ist vs. Prognose).
    forward_index: ab Monat nach letztem Istwert (reine Prognose).
    """
    clean = full_series.dropna().sort_index()
    freq = pd.infer_freq(clean.index) or "MS"
    step = pd.tseries.frequencies.to_offset(freq)

    cutoff = pd.Timestamp(cutoff)
    forecast_end = pd.Timestamp(forecast_end)
    available_end = pd.Timestamp(clean.index.max())
    data_end = min(forecast_end, available_end)
    last_actual = pd.Timestamp(clean.loc[clean.index <= data_end].index.max())

    comp_start = cutoff + step
    overlap = clean.index[(clean.index > cutoff) & (clean.index <= available_end)]
    holdout_end = pd.Timestamp(overlap.max()) if len(overlap) > 0 else None

    primary_months = max(1, _months(plot_window.forecast_years))
    post_months = _months(plot_window.post_years)
    comp_end_candidates = [comp_start + step * (primary_months - 1), forecast_end]
    if holdout_end is not None:
        comp_end_candidates.append(holdout_end)
    if post_months > 0:
        comp_end_candidates.append(comp_start + step * (primary_months + post_months - 1))
        if holdout_end is not None:
            comp_end_candidates.append(holdout_end + step * post_months)
    comp_end = min(max(comp_end_candidates), forecast_end)

    comparison_index = _monthly_range(comp_start, comp_end, freq)

    forward_start = last_actual + step
    if forecast_end > last_actual:
        forward_index = _monthly_range(forward_start, forecast_end, freq)
    else:
        forward_months = max(1, post_months if post_months > 0 else primary_months)
        forward_index = pd.date_range(
            start=forward_start, periods=forward_months, freq=freq
        )

    return ForecastHorizons(
        comparison_index=comparison_index,
        forward_index=forward_index,
        cutoff=cutoff,
        last_actual=last_actual,
        holdout_end=holdout_end,
    )
