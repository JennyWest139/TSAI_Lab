"""GARCH und ARMA-GARCH (arch) fuer TSA."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from arch import arch_model
from scipy import stats

from tslab.services.models_ar import _with_monthly_freq
from tslab.services.models_arma import fit_arma

DEFAULT_QUANTILES = (0.005, 0.05, 0.5, 0.95, 0.995)
GARCH_SCALE = 100.0


@dataclass(frozen=True)
class GarchFitResult:
    """GARCH(p,q)-Schaetzung (arch)."""

    result: object
    scale: float
    mean_model: str
    vol_order: tuple[int, int]
    conditional_volatility: pd.Series
    standardized_residuals: pd.Series

    @property
    def aic(self) -> float:
        return float(self.result.aic)

    @property
    def label(self) -> str:
        p, q = self.vol_order
        return f"GARCH({p},{q})"


@dataclass(frozen=True)
class ArmaGarchFitResult:
    """ARMA(p,q) fuer Mittelwert + GARCH(r,s) auf ARMA-Residuen."""

    arma_result: object
    garch: GarchFitResult
    arma_order: tuple[int, int]
    arma_fitted: pd.Series
    arma_residuals: pd.Series

    @property
    def label(self) -> str:
        p, q = self.arma_order
        r, s = self.garch.vol_order
        return f"ARMA({p},{q})-GARCH({r},{s})"


@dataclass(frozen=True)
class VolatilityForecast:
    """Mehrschritt-Prognose mit Quantilbaendern."""

    mean: pd.Series
    variance: pd.Series
    quantiles: dict[float, pd.Series]
    index: pd.DatetimeIndex


def _scaled_series(y: pd.Series, scale: float = GARCH_SCALE) -> pd.Series:
    return _with_monthly_freq(y) * scale


def fit_garch(
    y: pd.Series,
    *,
    p: int = 1,
    q: int = 1,
    mean: str = "Zero",
    dist: str = "normal",
    scale: float = GARCH_SCALE,
) -> GarchFitResult:
    """GARCH(p,q); bei trendbereinigten Renditen typisch mean='Zero'."""
    clean = _with_monthly_freq(y)
    scaled = clean * scale
    model = arch_model(
        scaled,
        mean=mean,
        vol="GARCH",
        p=p,
        q=q,
        dist=dist,
        rescale=False,
    )
    res = model.fit(disp="off")
    cond_vol = pd.Series(
        res.conditional_volatility / scale,
        index=clean.index,
        name="conditional_volatility",
    )
    std_resid = pd.Series(res.std_resid, index=clean.index, name="std_resid")
    return GarchFitResult(
        result=res,
        scale=scale,
        mean_model=mean,
        vol_order=(p, q),
        conditional_volatility=cond_vol,
        standardized_residuals=std_resid,
    )


def fit_arma_garch(
    y: pd.Series,
    *,
    arma_order: tuple[int, int] = (1, 1),
    garch_p: int = 1,
    garch_q: int = 1,
    dist: str = "normal",
    scale: float = GARCH_SCALE,
) -> ArmaGarchFitResult:
    """
    ARMA-GARCH: ARMA fuer den Mittelwert, GARCH auf die ARMA-Residuen.

    Entspricht der ueblichen zweistufigen Spezifikation in der Diplomarbeit.
    """
    clean = _with_monthly_freq(y)
    arma_res, arma_fitted = fit_arma(clean, arma_order)
    aligned = clean.loc[arma_fitted.index]
    resid = (aligned - arma_fitted).rename("arma_residual")
    garch = fit_garch(
        resid,
        p=garch_p,
        q=garch_q,
        mean="Zero",
        dist=dist,
        scale=scale,
    )
    return ArmaGarchFitResult(
        arma_result=arma_res,
        garch=garch,
        arma_order=arma_order,
        arma_fitted=arma_fitted,
        arma_residuals=resid,
    )


def _quantile_bands(
    mean: pd.Series,
    variance: pd.Series,
    quantiles: tuple[float, ...],
) -> dict[float, pd.Series]:
    out: dict[float, pd.Series] = {}
    vol = np.sqrt(variance.clip(lower=0.0))
    for q in quantiles:
        out[q] = mean + stats.norm.ppf(q) * vol
    return out


def forecast_garch(
    fit: GarchFitResult,
    *,
    steps: int,
    index: pd.DatetimeIndex,
    quantiles: tuple[float, ...] = DEFAULT_QUANTILES,
) -> VolatilityForecast:
    """GARCH-Prognose (Mittelwert + Varianz + Normal-Quantile)."""
    if steps <= 0:
        empty = pd.Series(dtype=float)
        return VolatilityForecast(empty, empty, {}, index[:0])

    fc = fit.result.forecast(horizon=steps, reindex=False)
    mean = pd.Series(
        fc.mean.iloc[-1].values / fit.scale,
        index=index,
        name="mean",
    )
    variance = pd.Series(
        fc.variance.iloc[-1].values / (fit.scale**2),
        index=index,
        name="variance",
    )
    return VolatilityForecast(
        mean=mean,
        variance=variance,
        quantiles=_quantile_bands(mean, variance, quantiles),
        index=index,
    )


def forecast_arma_garch(
    fit: ArmaGarchFitResult,
    *,
    steps: int,
    index: pd.DatetimeIndex,
    quantiles: tuple[float, ...] = DEFAULT_QUANTILES,
) -> VolatilityForecast:
    """Kombinierte ARMA-Mittelwert- und GARCH-Varianzprognose."""
    if steps <= 0:
        empty = pd.Series(dtype=float)
        return VolatilityForecast(empty, empty, {}, index[:0])

    arma_fc = fit.arma_result.get_forecast(steps=steps).predicted_mean
    garch_fc = forecast_garch(
        fit.garch,
        steps=steps,
        index=index,
        quantiles=quantiles,
    )
    mean = pd.Series(arma_fc.values, index=index, name="mean")
    variance = garch_fc.variance
    return VolatilityForecast(
        mean=mean,
        variance=variance,
        quantiles=_quantile_bands(mean, variance, quantiles),
        index=index,
    )
