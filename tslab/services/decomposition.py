"""Saisonale Zerlegung und Trendkomponente (statsmodels)."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from statsmodels.tsa.seasonal import seasonal_decompose


def pin_inferred_datetime_freq(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Kalenderfrequenz erkennen (MS oder ME) statt Monatsanfang zu erzwingen."""
    if not isinstance(index, pd.DatetimeIndex):
        index = pd.DatetimeIndex(pd.to_datetime(index))
    if index.freq is not None or len(index) < 3:
        return index
    inferred = pd.infer_freq(index)
    if inferred:
        return pd.DatetimeIndex(index, freq=inferred)
    return index


def prepare_monthly_series(y: pd.Series) -> pd.Series:
    clean = y.dropna().astype(float).copy()
    if isinstance(clean.index, pd.DatetimeIndex):
        clean.index = pin_inferred_datetime_freq(clean.index)
    return clean


def resolve_decomposition_period(y: pd.Series, period: int = 12) -> int:
    if len(y) < 2 * period:
        return max(2, len(y) // 3)
    return period


@dataclass(frozen=True)
class TrendComponentResult:
    trend: pd.Series
    model: str
    period: int

    @property
    def model_label_de(self) -> str:
        return "additive" if self.model == "additive" else "multiplikative"

    def footnote_de(self) -> str:
        return (
            f"Trendkomponente (gestrichelt): {self.model_label_de} Saisonzerlegung "
            f"(statsmodels.tsa.seasonal.seasonal_decompose, Periode={self.period} "
            f"Monate, extrapolate_trend='freq')"
        )


def extract_trend_component(
    y: pd.Series,
    *,
    model: str = "additive",
    period: int = 12,
) -> TrendComponentResult:
    """Trendkomponente aus klassischer STL-aehnlichen Zerlegung (Phase-0-Standard)."""
    clean = prepare_monthly_series(y)
    if len(clean) < 6:
        raise ValueError(
            f"Zu wenige Beobachtungen ({len(clean)}) fuer Saisonzerlegung."
        )

    eff_model = model
    if eff_model == "multiplicative" and not bool((clean > 0).all()):
        eff_model = "additive"

    p = resolve_decomposition_period(clean, period)
    result = seasonal_decompose(
        clean, model=eff_model, period=p, extrapolate_trend="freq"
    )
    trend = pd.Series(
        result.trend,
        index=clean.index,
        name=f"{clean.name or 'series'}_trend",
    )
    return TrendComponentResult(trend=trend, model=eff_model, period=p)
