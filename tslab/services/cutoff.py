"""Train/Test-Split anhand Stichtag (Cutoff) — TSA-Prognose."""

from __future__ import annotations

import pandas as pd

from tslab.services.analysis_window import split_forecast_holdout


def split_at_cutoff(
    series: pd.Series,
    cutoff: str | pd.Timestamp,
) -> tuple[pd.Series, pd.Series]:
    """
    Alles mit Index <= cutoff: Analyse (Training).
    Alles mit Index > cutoff: Holdout (Prognose-Validierung).
    """
    return split_forecast_holdout(series, analysis_end=cutoff)
