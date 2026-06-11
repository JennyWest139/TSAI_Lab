"""Grafiken fuer Phase-1-TSA (GARCH, Prognosebaender)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image

from tslab.plots.series_display import SeriesDisplay
from tslab.services.models_garch import VolatilityForecast

plt.style.use("seaborn-v0_8-whitegrid")
_BOTTOM = 0.22


def _save(fig: plt.Figure, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.stem}_write.png")
    fig.savefig(tmp, format="png", dpi=120, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    with Image.open(tmp) as im:
        im.convert("RGB").save(path, format="PNG")
    tmp.unlink(missing_ok=True)
    return path


def plot_conditional_volatility(
    volatility: pd.Series,
    path: Path,
    display: SeriesDisplay,
    *,
    title_suffix: str,
) -> Path:
    fig, ax = plt.subplots(figsize=(10, 4.5))
    volatility.plot(ax=ax, color="#c55a11", lw=1.0)
    ax.set_title(display.title(f"Bedingte Volatilitaet ({title_suffix})"))
    ax.set_xlabel("Zeit (Monatsdaten)")
    ax.set_ylabel("Sigma (GARCH)")
    fig.text(
        0.5,
        0.02,
        display.footnote(),
        ha="center",
        fontsize=8,
        style="italic",
        transform=fig.transFigure,
    )
    fig.subplots_adjust(bottom=_BOTTOM)
    return _save(fig, path)


def plot_standardized_residuals(
    std_resid: pd.Series,
    path: Path,
    display: SeriesDisplay,
    *,
    title_suffix: str,
) -> Path:
    fig, ax = plt.subplots(figsize=(10, 4.5))
    std_resid.plot(ax=ax, color="#7030a0", lw=0.9)
    ax.axhline(0, color="gray", ls="--", lw=0.8)
    ax.set_title(display.title(f"Standardisierte Residuen ({title_suffix})"))
    ax.set_xlabel("Zeit (Monatsdaten)")
    ax.set_ylabel("z_t")
    fig.text(
        0.5,
        0.02,
        display.footnote(),
        ha="center",
        fontsize=8,
        style="italic",
        transform=fig.transFigure,
    )
    fig.subplots_adjust(bottom=_BOTTOM)
    return _save(fig, path)


def plot_forecast_quantiles(
    train: pd.Series,
    forecast: VolatilityForecast,
    holdout: pd.Series,
    path: Path,
    *,
    title: str,
    model_label: str,
) -> Path:
    fig, ax = plt.subplots(figsize=(11, 5))
    train.plot(ax=ax, color="#1f4e79", lw=1.0, label="Training")

    if not forecast.mean.empty:
        forecast.mean.plot(ax=ax, color="#c55a11", lw=1.8, label="Prognose (Mittelwert)")
        idx = forecast.index
        q_lo, q_hi = 0.005, 0.995
        q05, q95 = 0.05, 0.95
        if q_lo in forecast.quantiles and q_hi in forecast.quantiles:
            ax.fill_between(
                idx,
                forecast.quantiles[q_lo],
                forecast.quantiles[q_hi],
                color="#8db4e2",
                alpha=0.25,
                label="99%-Band (0.5%-99.5%)",
            )
        if q05 in forecast.quantiles and q95 in forecast.quantiles:
            ax.fill_between(
                idx,
                forecast.quantiles[q05],
                forecast.quantiles[q95],
                color="#1f4e79",
                alpha=0.18,
                label="90%-Band (5%-95%)",
            )
        if 0.5 in forecast.quantiles:
            forecast.quantiles[0.5].plot(
                ax=ax, color="#548235", lw=1.0, ls="--", label="Median"
            )

    if not holdout.empty:
        holdout.plot(ax=ax, color="#bf8f00", lw=1.2, ls="--", label="Ist (Holdout)")

    ax.axvline(train.index.max(), color="gray", ls=":", lw=0.8)
    ax.set_title(title)
    ax.set_xlabel("Zeit (Monatsdaten)")
    ax.set_ylabel("Transformiert: diff(ln(PDAX)), linear trendbereinigt")
    ax.legend(loc="upper left", fontsize=7, framealpha=0.9)
    fig.text(
        0.5,
        0.01,
        f"Modell: {model_label}; Quantile unter Normalverteilungsannahme",
        ha="center",
        fontsize=7,
        style="italic",
    )
    fig.subplots_adjust(bottom=0.14)
    return _save(fig, path)
