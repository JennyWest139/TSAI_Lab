"""Plots fuer Residuen-Diagnostik (AKF, PAKF, QQ, Histogramm, Modellzerlegung)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from statsmodels.graphics.gofplots import qqplot

from tslab.plots.series_display import SeriesDisplay
from tslab.plots.time_series_plots import (
    _caption,
    _prepare_series,
    _save,
    plot_acf,
    plot_histogram,
    plot_pacf,
)

plt.style.use("seaborn-v0_8-whitegrid")

_X_TIME = "Zeit (Monatsdaten, Stichtag bis Cutoff)"


def plot_qq(
    residuals: pd.Series,
    path: Path,
    display: SeriesDisplay,
) -> Path:
    clean = _prepare_series(residuals)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    qqplot(clean, line="45", ax=ax, markerfacecolor="#2e75b6", markeredgecolor="#1a4a73")
    ax.set_title(display.title("QQ-Plot (Normalverteilung)"))
    ax.set_xlabel("Theoretische Quantile")
    ax.set_ylabel("Empirische Quantile")
    _caption(fig, display)
    return _save(fig, path)


def plot_model_decomposition(
    y: pd.Series,
    fitted: pd.Series,
    path: Path,
    display: SeriesDisplay,
    *,
    model_label: str,
) -> Path:
    """Beobachtet, angepasster Mittelwert und Residuen (Modellzerlegung)."""
    aligned = y.loc[fitted.index]
    resid = (aligned - fitted).dropna()
    common_idx = resid.index
    aligned = aligned.loc[common_idx]
    fitted_aligned = fitted.loc[common_idx]

    fig, axes = plt.subplots(3, 1, figsize=(10, 7), sharex=True)
    axes[0].plot(common_idx, aligned.values, color="#1f4e79", lw=1.0)
    axes[0].set_title(f"Beobachtet ({display.value_axis})")
    axes[1].plot(common_idx, fitted_aligned.values, color="#548235", lw=1.0)
    axes[1].set_title(f"Angepasster Mittelwert ({model_label})")
    axes[2].plot(common_idx, resid.values, color="#7030a0", lw=1.0)
    axes[2].axhline(0, color="gray", ls="--", lw=0.8)
    axes[2].set_title("Residuen (soll keine Struktur mehr enthalten)")
    axes[-1].set_xlabel(_X_TIME)
    if isinstance(common_idx, pd.DatetimeIndex):
        axes[-1].xaxis.set_major_locator(mdates.YearLocator(5))
        axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.suptitle(
        f"Modellzerlegung {model_label} - {display.short_name}",
        y=0.995,
        fontsize=11,
    )
    fig.subplots_adjust(left=0.08, right=0.98, top=0.90, bottom=0.28, hspace=0.35)
    _caption(fig, display, bottom=0.28)
    return _save(fig, path)


def export_residual_diagnostic_plots(
    residuals: pd.Series,
    out_dir: Path,
    file_tag: str,
    display: SeriesDisplay,
    *,
    include_arch: bool = False,
    acf_lags: int = 24,
) -> list[Path]:
    """AKF/PAKF/QQ/Histogramm; bei GARCH zusaetzlich AKF der quadrierten Residuen."""
    out_dir.mkdir(parents=True, exist_ok=True)
    clean = _prepare_series(residuals)
    created: list[Path] = []

    created.append(
        plot_acf(
            clean,
            out_dir / f"{file_tag}_residuals_acf.png",
            display,
            lags=acf_lags,
        )
    )
    created.append(
        plot_pacf(
            clean,
            out_dir / f"{file_tag}_residuals_pacf.png",
            display,
            lags=acf_lags,
        )
    )
    created.append(
        plot_histogram(
            clean,
            out_dir / f"{file_tag}_residuals_histogram.png",
            display,
        )
    )
    created.append(
        plot_qq(
            clean,
            out_dir / f"{file_tag}_residuals_qq.png",
            display,
        )
    )

    if include_arch:
        sq_display = SeriesDisplay(
            short_name=f"{display.short_name} (quadriert)",
            value_axis=f"({display.value_axis})^2",
            data_basis=(
                f"Quadrierte Residuen zur ARCH-Pruefung; Basis: {display.data_basis}"
            ),
        )
        created.append(
            plot_acf(
                clean**2,
                out_dir / f"{file_tag}_residuals_sq_acf.png",
                sq_display,
                lags=acf_lags,
            )
        )

    return created
