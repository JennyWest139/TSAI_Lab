"""Transformationen für PDAX-Analyse (Diplomarbeit)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def log_levels(series: pd.Series) -> pd.Series:
    s = series.copy()
    s = s[s > 0]
    return np.log(s).rename("log_PDAX")


def log_returns(series: pd.Series) -> pd.Series:
    """Kontinuierliche Renditen: diff(log(PDAX))."""
    lg = log_levels(series)
    return lg.diff().dropna().rename("log_returns")


def detrend_linear(y: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Lineare Trendbereinigung; Rückgabe: trend, residuum."""
    t = np.arange(len(y), dtype=float)
    slope, intercept, _, _, _ = stats.linregress(t, y.values)
    trend = pd.Series(intercept + slope * t, index=y.index, name="trend")
    resid = (y - trend).rename(y.name or "resid")
    return trend, resid


def log_returns_detrended(series: pd.Series) -> pd.Series:
    r = log_returns(series)
    _, resid = detrend_linear(r)
    return resid.rename("log_returns_detrended")
