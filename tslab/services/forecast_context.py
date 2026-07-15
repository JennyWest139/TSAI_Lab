"""Kontext fuer Prognoseplots: Prognose + optionale Ist-Werte im Prognosezeitraum."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from tslab.services.analysis_window import StudyDates, prepare_tsa_split


@dataclass
class ForecastPlotData:
    """Daten fuer Prognosegrafiken (Quantile + Abgleich mit Ist)."""

    train: pd.Series
    forecast_index: pd.DatetimeIndex
    holdout_actual: pd.Series
    cutoff: pd.Timestamp
    forecast_end: pd.Timestamp

    @property
    def has_actuals_for_comparison(self) -> bool:
        return not self.holdout_actual.empty


def build_forecast_plot_data(
    full_series: pd.Series,
    study: StudyDates,
) -> ForecastPlotData:
    """
    Bereitet Trainingsdaten und Holdout-Istwerte fuer Prognoseplots vor.

    Liegen nach cutoff noch Messwerte bis forecast_end vor, werden sie in
    holdout_actual zurueckgegeben (fuer Overlay in Grafiken).
    """
    split = prepare_tsa_split(full_series, study)
    clean = full_series.dropna().sort_index()

    freq = pd.infer_freq(clean.index) or "MS"
    step = pd.tseries.frequencies.to_offset(freq)
    fc_start = study.cutoff + step
    if fc_start > study.forecast_end:
        forecast_idx = pd.DatetimeIndex([])
    else:
        forecast_idx = pd.date_range(
            start=fc_start, end=study.forecast_end, freq=freq
        )

    return ForecastPlotData(
        train=split.train,
        forecast_index=forecast_idx,
        holdout_actual=split.holdout_actual,
        cutoff=study.cutoff,
        forecast_end=study.forecast_end,
    )
