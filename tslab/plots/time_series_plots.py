"""Matplotlib-Plots für Phase 0 (ein Plot = eine Datei)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image
from scipy import stats
from statsmodels.graphics.tsaplots import plot_acf as sm_plot_acf
from statsmodels.graphics.tsaplots import plot_pacf as sm_plot_pacf
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.stattools import pacf as sm_pacf

from tslab.plots.series_display import SeriesDisplay

plt.style.use("seaborn-v0_8-whitegrid")

_MIN_PNG_BYTES = 1000
_X_TIME = "Zeit (Monatsdaten, Stichtag bis Cutoff)"
_BOTTOM_WITH_CAPTION = 0.24


def _save(fig: plt.Figure, path: Path) -> Path:
    """Speichert als Standard-RGB-PNG direkt auf Disk (max. Viewer-Kompatibilitaet)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.stem}_write.png")

    fig.savefig(
        tmp,
        format="png",
        dpi=120,
        facecolor="white",
        edgecolor="none",
        pad_inches=0.12,
    )
    plt.close(fig)

    with Image.open(tmp) as im:
        rgb = im.convert("RGB")
        rgb.save(path, format="PNG")
    tmp.unlink(missing_ok=True)

    if path.stat().st_size < _MIN_PNG_BYTES:
        path.unlink(missing_ok=True)
        raise OSError(f"PNG nicht gueltig geschrieben: {path}")

    return path


def _caption(
    fig: plt.Figure, display: SeriesDisplay, *, bottom: float = _BOTTOM_WITH_CAPTION
) -> None:
    fig.text(
        0.5,
        0.02,
        display.footnote(),
        ha="center",
        va="bottom",
        fontsize=8,
        style="italic",
        transform=fig.transFigure,
    )
    fig.subplots_adjust(bottom=bottom)


def _prepare_series(y: pd.Series) -> pd.Series:
    clean = y.dropna().astype(float).copy()
    if clean.index.freq is None and isinstance(clean.index, pd.DatetimeIndex):
        clean.index = pd.DatetimeIndex(clean.index, freq="MS")
    return clean


def _decompose_period(y: pd.Series, period: int = 12) -> int:
    if len(y) < 2 * period:
        return max(2, len(y) // 3)
    return period


def multiplicative_allowed(y: pd.Series) -> bool:
    clean = y.dropna()
    return len(clean) > 0 and bool((clean > 0).all())


def _safe_lags(y: pd.Series, lags: int = 40) -> int:
    n = len(y.dropna())
    return max(1, min(lags, n // 2 - 1))


def plot_series(y: pd.Series, path: Path, display: SeriesDisplay) -> Path:
    fig, ax = plt.subplots(figsize=(10, 4.5))
    y.plot(ax=ax, color="#1f4e79", lw=1.2)
    ax.set_title(display.title("Zeitreihe"))
    ax.set_xlabel(_X_TIME)
    ax.set_ylabel(display.value_axis)
    _caption(fig, display)
    return _save(fig, path)


def plot_histogram(y: pd.Series, path: Path, display: SeriesDisplay) -> Path:
    fig, ax = plt.subplots(figsize=(9, 4.5))
    values = y.dropna().values
    ax.hist(
        values,
        bins=30,
        color="#2e75b6",
        edgecolor="#1a4a73",
        linewidth=0.4,
        alpha=0.9,
    )
    ax.set_title(display.title("Histogramm"))
    ax.set_xlabel(display.value_axis)
    ax.set_ylabel("Haeufigkeit")
    _caption(fig, display)
    return _save(fig, path)


def plot_acf(y: pd.Series, path: Path, display: SeriesDisplay, lags: int = 40) -> Path:
    clean = _prepare_series(y)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    sm_plot_acf(clean, lags=_safe_lags(clean, lags), ax=ax, title=display.title("AKF"))
    ax.set_xlabel("Lag")
    ax.set_ylabel("Autokorrelation")
    _caption(fig, display)
    return _save(fig, path)


def plot_pacf(y: pd.Series, path: Path, display: SeriesDisplay, lags: int = 40) -> Path:
    clean = _prepare_series(y)
    nlags = _safe_lags(clean, lags)
    fig, ax = plt.subplots(figsize=(10, 4.5))

    last_error: Exception | None = None
    for method in ("ols", "ywm", "ldb"):
        try:
            sm_plot_pacf(
                clean,
                lags=nlags,
                ax=ax,
                title=display.title("PAKF"),
                method=method,
            )
            ax.set_xlabel("Lag")
            ax.set_ylabel("Partielle Autokorrelation")
            _caption(fig, display)
            return _save(fig, path)
        except Exception as exc:
            last_error = exc
            ax.clear()

    values = sm_pacf(clean.values, nlags=nlags, method="ols")
    ax.stem(range(len(values)), values, linefmt="#1f4e79", markerfmt="o", basefmt=" ")
    ax.axhline(0, color="gray", lw=0.8)
    ax.set_title(display.title("PAKF"))
    ax.set_xlabel("Lag")
    ax.set_ylabel("Partielle Autokorrelation")
    _caption(fig, display)
    try:
        return _save(fig, path)
    except Exception as exc:
        plt.close(fig)
        raise RuntimeError(f"PAKF fehlgeschlagen fuer {display.short_name}") from (
            last_error or exc
        )


def plot_spectral_density(y: pd.Series, path: Path, display: SeriesDisplay) -> Path:
    fig, ax = plt.subplots(figsize=(10, 4.5))
    clean = y.dropna().values
    centered = clean - clean.mean()
    freqs = np.fft.rfftfreq(len(centered), d=1.0)
    spectrum = np.abs(np.fft.rfft(centered)) ** 2 / len(centered)
    ax.plot(freqs[1:], spectrum[1:], color="#c55a11")
    ax.set_title(display.title("Spektraldichte"))
    ax.set_xlabel("Frequenz")
    ax.set_ylabel(f"Leistung: {display.value_axis}")
    _caption(fig, display)
    return _save(fig, path)


def plot_periodogram(y: pd.Series, path: Path, display: SeriesDisplay) -> Path:
    fig, ax = plt.subplots(figsize=(10, 4.5))
    clean = y.dropna().values
    centered = clean - clean.mean()
    freqs = np.fft.rfftfreq(len(centered), d=1.0)
    periodogram = (np.abs(np.fft.rfft(centered)) ** 2) / len(centered)
    ax.stem(freqs[1:], periodogram[1:], linefmt="#843c0b", markerfmt=" ", basefmt=" ")
    ax.set_title(display.title("Periodogramm"))
    ax.set_xlabel("Frequenz")
    ax.set_ylabel(f"Intensitaet: {display.value_axis}")
    _caption(fig, display)
    return _save(fig, path)


def plot_decomposition(
    y: pd.Series,
    path: Path,
    display: SeriesDisplay,
    *,
    model: str = "additive",
    period: int = 12,
) -> Path | None:
    clean = _prepare_series(y)
    if model == "multiplicative" and not multiplicative_allowed(clean):
        return None

    p = _decompose_period(clean, period)
    result = seasonal_decompose(
        clean, model=model, period=p, extrapolate_trend="freq"
    )
    model_label = "Additive" if model == "additive" else "Multiplikative"
    fig, axes = plt.subplots(4, 1, figsize=(10, 8), sharex=True)
    y_unit = display.value_axis
    idx = clean.index
    axes[0].plot(idx, result.observed, color="#1f4e79", lw=1.0)
    axes[0].set_title(f"Beobachtet ({y_unit})")
    axes[1].plot(idx, result.trend, color="#548235", lw=1.0)
    axes[1].set_title("Trendkomponente")
    axes[2].plot(idx, result.seasonal, color="#bf8f00", lw=1.0)
    axes[2].set_title("Saisonale Komponente")
    axes[3].plot(idx, result.resid, color="#7030a0", lw=1.0)
    axes[3].set_title("Residuum (soll zufaellig sein)")
    axes[-1].set_xlabel(_X_TIME)
    axes[-1].xaxis.set_major_locator(mdates.YearLocator(5))
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.suptitle(
        f"{model_label} Zerlegung - {display.short_name}",
        y=0.995,
        fontsize=11,
    )
    fig.subplots_adjust(left=0.08, right=0.98, top=0.92, bottom=0.30, hspace=0.38)
    _caption(fig, display, bottom=0.30)
    return _save(fig, path)


def plot_decompositions(
    y: pd.Series,
    out_base: Path,
    variant_id: str,
    display: SeriesDisplay,
    *,
    include_multiplicative: bool = True,
    period: int = 12,
) -> list[str]:
    created: list[str] = []

    add_path = out_base / f"{variant_id}_decomposition_additive.png"
    plot_decomposition(y, add_path, display, model="additive", period=period)
    created.append(add_path.name)

    if include_multiplicative and multiplicative_allowed(y):
        mult_path = out_base / f"{variant_id}_decomposition_multiplicative.png"
        plot_decomposition(y, mult_path, display, model="multiplicative", period=period)
        created.append(mult_path.name)

    return created


def plot_fitted_exponential(y: pd.Series, path: Path, display: SeriesDisplay) -> Path:
    """PDAX-Niveau mit exp. Trend – gleiche Plot-Methode wie plot_series."""
    pos = _prepare_series(y[y > 0])
    t = np.arange(len(pos), dtype=float)
    log_y = np.log(pos.values)
    slope, intercept, _, _, _ = stats.linregress(t, log_y)
    fitted = pd.Series(
        np.exp(intercept + slope * t),
        index=pos.index,
        name="exp_trend",
    )

    fig, ax = plt.subplots(figsize=(10, 4.5))
    pos.plot(ax=ax, label="Original PDAX", color="#1f4e79", lw=1.2)
    fitted.plot(ax=ax, label="exp. Trend (ln-Regression)", color="#c55a11", lw=2)
    ax.set_title(display.title("Exponential-Trend"))
    ax.set_xlabel(_X_TIME)
    ax.set_ylabel("Original: PDAX-Kursniveau")
    ax.legend(loc="upper left", fontsize=8, framealpha=0.9)
    _caption(fig, display)
    return _save(fig, path)


def plot_residuals(
    y: pd.Series, fitted: pd.Series, path: Path, display: SeriesDisplay
) -> Path:
    resid = (y - fitted).dropna()
    fig, ax = plt.subplots(figsize=(10, 4))
    resid.plot(ax=ax, color="#7030a0")
    ax.axhline(0, color="gray", ls="--", lw=0.8)
    ax.set_title(display.title("Residuen"))
    ax.set_xlabel(_X_TIME)
    ax.set_ylabel(display.value_axis)
    _caption(fig, display, bottom=0.28)
    return _save(fig, path)
