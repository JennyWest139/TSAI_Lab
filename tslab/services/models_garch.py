"""GARCH und ARMA-GARCH (arch) fuer TSA."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from arch import arch_model
from scipy import stats

from tslab.services.analysis_mode import AnalysisModeConfig, prepare_garch_input
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
    mean_offset: float = 0.0

    @property
    def aic(self) -> float:
        return float(self.result.aic)

    @property
    def label(self) -> str:
        p, q = self.vol_order
        return f"GARCH({p},{q})"


@dataclass(frozen=True)
class ArmaGarchFitResult:
    """ARMA-GARCH: zweistufig (extended) oder gemeinsam via arch (thesis)."""

    arma_order: tuple[int, int]
    garch: GarchFitResult
    joint: bool
    mean_offset: float
    arma_result: object | None = None
    arma_fitted: pd.Series | None = None
    arma_residuals: pd.Series | None = None
    arch_result: object | None = None

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


def fit_garch(
    y: pd.Series,
    mode_config: AnalysisModeConfig,
    *,
    p: int = 1,
    q: int = 1,
    dist: str = "normal",
    scale: float = GARCH_SCALE,
) -> GarchFitResult:
    """GARCH(p,q); im thesis-Modus auf mittelwertbereinigten Renditen."""
    clean = _with_monthly_freq(y)
    garch_y, mean_offset = prepare_garch_input(clean, mode_config)
    scaled = garch_y * scale
    model = arch_model(
        scaled,
        mean="Zero",
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
        mean_model="Zero",
        vol_order=(p, q),
        conditional_volatility=cond_vol,
        standardized_residuals=std_resid,
        mean_offset=mean_offset,
    )


def _fit_arma_garch_two_step(
    y: pd.Series,
    mode_config: AnalysisModeConfig,
    *,
    arma_order: tuple[int, int],
    garch_p: int,
    garch_q: int,
    dist: str,
    scale: float,
) -> ArmaGarchFitResult:
    clean = _with_monthly_freq(y)
    arma_res, arma_fitted = fit_arma(clean, arma_order)
    aligned = clean.loc[arma_fitted.index]
    resid = (aligned - arma_fitted).rename("arma_residual")
    garch = fit_garch(
        resid,
        mode_config,
        p=garch_p,
        q=garch_q,
        dist=dist,
        scale=scale,
    )
    return ArmaGarchFitResult(
        arma_order=arma_order,
        garch=garch,
        joint=False,
        mean_offset=0.0,
        arma_result=arma_res,
        arma_fitted=arma_fitted,
        arma_residuals=resid,
    )


def _fit_arma_garch_joint(
    y: pd.Series,
    mode_config: AnalysisModeConfig,
    *,
    arma_order: tuple[int, int],
    garch_p: int,
    garch_q: int,
    dist: str,
    scale: float,
) -> ArmaGarchFitResult:
    """Gemeinsames ARMA-GARCH via arch (Diplomarbeit / R: arma(1,1)+garch(1,1))."""
    clean = _with_monthly_freq(y)
    fit_y, mean_offset = prepare_garch_input(clean, mode_config)
    p, q = arma_order
    model = arch_model(
        fit_y * scale,
        mean="AR",
        lags=p,
        vol="GARCH",
        p=garch_p,
        q=garch_q,
        dist=dist,
        rescale=False,
    )
    res = model.fit(disp="off", update_freq=0)
    cond_vol = pd.Series(
        res.conditional_volatility / scale,
        index=clean.index,
        name="conditional_volatility",
    )
    std_resid = pd.Series(res.std_resid, index=clean.index, name="std_resid")
    garch = GarchFitResult(
        result=res,
        scale=scale,
        mean_model="AR",
        vol_order=(garch_p, garch_q),
        conditional_volatility=cond_vol,
        standardized_residuals=std_resid,
        mean_offset=mean_offset,
    )
    return ArmaGarchFitResult(
        arma_order=arma_order,
        garch=garch,
        joint=True,
        mean_offset=mean_offset,
        arch_result=res,
    )


def fit_arma_garch(
    y: pd.Series,
    mode_config: AnalysisModeConfig,
    *,
    arma_order: tuple[int, int] = (1, 1),
    garch_p: int = 1,
    garch_q: int = 1,
    dist: str = "normal",
    scale: float = GARCH_SCALE,
) -> ArmaGarchFitResult:
    if mode_config.arma_garch_joint:
        return _fit_arma_garch_joint(
            y,
            mode_config,
            arma_order=arma_order,
            garch_p=garch_p,
            garch_q=garch_q,
            dist=dist,
            scale=scale,
        )
    return _fit_arma_garch_two_step(
        y,
        mode_config,
        arma_order=arma_order,
        garch_p=garch_p,
        garch_q=garch_q,
        dist=dist,
        scale=scale,
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
    if steps <= 0:
        empty = pd.Series(dtype=float)
        return VolatilityForecast(empty, empty, {}, index[:0])

    fc = fit.result.forecast(horizon=steps, reindex=False)
    mean = pd.Series(
        fc.mean.iloc[-1].values / fit.scale + fit.mean_offset,
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
    if steps <= 0:
        empty = pd.Series(dtype=float)
        return VolatilityForecast(empty, empty, {}, index[:0])

    if fit.joint:
        assert fit.arch_result is not None
        fc = fit.arch_result.forecast(horizon=steps, reindex=False)
        mean = pd.Series(
            fc.mean.iloc[-1].values / fit.garch.scale + fit.mean_offset,
            index=index,
            name="mean",
        )
        variance = pd.Series(
            fc.variance.iloc[-1].values / (fit.garch.scale**2),
            index=index,
            name="variance",
        )
    else:
        assert fit.arma_result is not None
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
