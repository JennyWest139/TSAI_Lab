"""Grafiken fuer Phase-1-TSA (GARCH, Prognosebaender, Diplomarbeit-Layout)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image

from tslab.plots.series_display import SeriesDisplay
from tslab.services.forecast_plot_window import (
    ForecastPlotWindow,
    apply_forecast_plot_window,
)
from tslab.services.models_garch import VolatilityForecast

plt.style.use("seaborn-v0_8-whitegrid")
_BOTTOM = 0.22

_QUANTILE_LINES = (
    (0.995, "#c00000", "Oberes Quantil (99,5 %)"),
    (0.95, "#ed7d31", "Oberes Quantil (95 %)"),
    (0.05, "#ed7d31", "Unteres Quantil (5 %)"),
    (0.005, "#c00000", "Unteres Quantil (0,5 %)"),
)


def _save(fig: plt.Figure, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.stem}_write.png")
    fig.savefig(tmp, format="png", dpi=120, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    with Image.open(tmp) as im:
        im.convert("RGB").save(path, format="PNG")
    tmp.unlink(missing_ok=True)
    return path


def _continuous_actual(
    train: pd.Series,
    holdout: pd.Series,
    *,
    cutoff: pd.Timestamp,
    plot_start: pd.Timestamp,
    plot_end: pd.Timestamp,
    last_actual: pd.Timestamp | None = None,
) -> pd.Series:
    """Eine durchgehende Ist-Linie ohne Luecke zwischen Training und Holdout."""
    end = last_actual if last_actual is not None else plot_end
    train_part = train.loc[(train.index >= plot_start) & (train.index <= cutoff)]
    parts = [train_part]
    if not holdout.empty:
        ho = holdout.loc[
            (holdout.index > cutoff) & (holdout.index <= end) & (holdout.index <= plot_end)
        ]
        if not ho.empty:
            parts.append(ho)
    actual = pd.concat(parts).sort_index()
    return actual[~actual.index.duplicated(keep="last")]


def _plot_quantile_lines(ax: plt.Axes, forecast: VolatilityForecast) -> None:
    if 0.5 in forecast.quantiles:
        forecast.quantiles[0.5].plot(
            ax=ax, color="#548235", lw=1.6, label="Punktprognose"
        )
    elif not forecast.mean.empty:
        forecast.mean.plot(ax=ax, color="#548235", lw=1.6, label="Punktprognose")

    for q, color, label in _QUANTILE_LINES:
        if q in forecast.quantiles:
            forecast.quantiles[q].plot(ax=ax, color=color, lw=1.0, label=label)


def _forecast_marker_dates(
    forecast_index: pd.DatetimeIndex,
    *,
    forecast_years: float,
) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    """Erster Prognosemonat und Ende des 1-Jahres-Horizonts (12. Wert)."""
    if len(forecast_index) == 0:
        return None, None
    months = max(1, int(round(forecast_years * 12)))
    second_pos = min(months - 1, len(forecast_index) - 1)
    return pd.Timestamp(forecast_index[0]), pd.Timestamp(forecast_index[second_pos])


def _slice_forecast_from(
    forecast: VolatilityForecast,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> VolatilityForecast:
    idx = forecast.index[(forecast.index >= start) & (forecast.index <= end)]
    if len(idx) == 0:
        empty = pd.Series(dtype=float)
        return VolatilityForecast(empty, empty, {}, pd.DatetimeIndex([]))
    return VolatilityForecast(
        mean=forecast.mean.reindex(idx),
        variance=forecast.variance.reindex(idx),
        quantiles={q: s.reindex(idx) for q, s in forecast.quantiles.items()},
        index=idx,
    )


def plot_forecast_abgleich(
    train: pd.Series,
    forecast: VolatilityForecast,
    holdout: pd.Series,
    path: Path,
    *,
    title: str,
    model_label: str,
    cutoff: pd.Timestamp,
    holdout_end: pd.Timestamp | None,
    plot_window: ForecastPlotWindow | None = None,
    y_label: str = "kont. Renditen",
    actual_label: str = "Kont. Rendite",
) -> Path:
    """
    Diplomarbeit-Abgleich: Training, Ueberlappung (Ist + Prognose), reine Prognose.
    Ist-Werte als eine durchgehende schwarze Linie; Prognose ab Cutoff ohne Luecke.
    """
    window = plot_window or ForecastPlotWindow.from_defaults()
    eff_cutoff = pd.Timestamp(cutoff)
    _, forecast_p, holdout_p, plot_start, plot_end = apply_forecast_plot_window(
        train, forecast, holdout, eff_cutoff, window
    )
    actual = _continuous_actual(
        train,
        holdout_p,
        cutoff=eff_cutoff,
        plot_start=plot_start,
        plot_end=plot_end,
    )

    fig, ax = plt.subplots(figsize=(11, 5.5))
    if not actual.empty:
        actual.plot(ax=ax, color="black", lw=1.1, label=actual_label, zorder=3)

    if not forecast_p.mean.empty:
        _plot_quantile_lines(ax, forecast_p)

    fc_start, fc_year_end = _forecast_marker_dates(
        forecast_p.index, forecast_years=window.forecast_years
    )
    if fc_start is not None:
        ax.axvline(fc_start, color="gray", ls="--", lw=0.9, zorder=1)
    if fc_year_end is not None and fc_year_end != fc_start:
        ax.axvline(fc_year_end, color="gray", ls="--", lw=0.9, zorder=1)

    ax.set_xlim(plot_start, plot_end)
    ax.set_title(title)
    ax.set_xlabel("Zeit (Monatsdaten)")
    ax.set_ylabel(y_label)
    ax.legend(loc="upper left", fontsize=6.5, framealpha=0.92, ncol=1)
    marker_note = ""
    if fc_start is not None:
        marker_note = f"; Prognose ab {fc_start.date()}"
        if fc_year_end is not None and fc_year_end != fc_start:
            marker_note += f", 12 Monate bis {fc_year_end.date()}"
    footnote = f"Modell: {model_label}{marker_note}; Fenster: {window.label_de}"
    fig.text(
        0.5,
        0.01,
        footnote,
        ha="center",
        fontsize=7,
        style="italic",
    )
    fig.subplots_adjust(bottom=0.14)
    return _save(fig, path)


def plot_forecast_forward(
    actual_lr: pd.Series,
    forecast: VolatilityForecast,
    path: Path,
    *,
    title: str,
    model_label: str,
    last_actual: pd.Timestamp,
    plot_window: ForecastPlotWindow | None = None,
    y_label: str = "kont. Renditen",
    actual_label: str = "Kont. Rendite",
) -> Path:
    """
    Forward-Grafik: Ist-Werte bis letzter Beobachtung, Prognose nur danach.
    Modell typischerweise auf voller Stichprobe bis last_actual geschaetzt.
    """
    window = plot_window or ForecastPlotWindow.from_defaults()
    eff_last = pd.Timestamp(last_actual)
    plot_start = eff_last - pd.DateOffset(months=int(round(window.pre_years * 12)))

    full_actual = actual_lr.loc[
        (actual_lr.index >= plot_start) & (actual_lr.index <= eff_last)
    ]

    step = pd.tseries.frequencies.to_offset("MS")
    forecast_start = eff_last + step
    plot_end = forecast.index.max() if len(forecast.index) else forecast_start
    forecast_p = _slice_forecast_from(forecast, forecast_start, pd.Timestamp(plot_end))

    fig, ax = plt.subplots(figsize=(11, 5.5))
    if not full_actual.empty:
        full_actual.plot(ax=ax, color="black", lw=1.1, label=actual_label, zorder=3)

    if not forecast_p.mean.empty:
        _plot_quantile_lines(ax, forecast_p)

    ax.axvline(eff_last, color="gray", ls="--", lw=0.9, zorder=1)
    ax.set_xlim(plot_start, plot_end)
    ax.set_title(title)
    ax.set_xlabel("Zeit (Monatsdaten)")
    ax.set_ylabel(y_label)
    ax.legend(loc="upper left", fontsize=6.5, framealpha=0.92)
    fig.text(
        0.5,
        0.01,
        (
            f"Modell: {model_label}; letzter Istwert {eff_last.date()} "
            f"(PDAX); Prognose ab Folgemonat"
            if actual_label == "PDAX (Niveau)"
            else (
                f"Modell: {model_label}; letzter Istwert {eff_last.date()}; "
                f"Prognose ab Folgemonat"
            )
        ),
        ha="center",
        fontsize=7,
        style="italic",
    )
    fig.subplots_adjust(bottom=0.14)
    return _save(fig, path)


def plot_forecast_quantiles(
    train: pd.Series,
    forecast: VolatilityForecast,
    holdout: pd.Series,
    path: Path,
    *,
    title: str,
    model_label: str,
    cutoff: pd.Timestamp | None = None,
    plot_window: ForecastPlotWindow | None = None,
    holdout_end: pd.Timestamp | None = None,
    y_label: str = "kont. Renditen",
) -> Path:
    """Abwaertskompatibel: leitet auf plot_forecast_abgleich um."""
    eff_cutoff = pd.Timestamp(cutoff if cutoff is not None else train.index.max())
    ho_end = holdout_end
    if ho_end is None and not holdout.empty:
        ho_end = pd.Timestamp(holdout.index.max())
    return plot_forecast_abgleich(
        train,
        forecast,
        holdout,
        path,
        title=title,
        model_label=model_label,
        cutoff=eff_cutoff,
        holdout_end=ho_end,
        plot_window=plot_window,
        y_label=y_label,
    )


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
