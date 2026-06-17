"""Grafiken fuer Kreuzkorrelation."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image

from tslab.services.correlation import CorrelationResult, LAG_DEFINITION
from tslab.services.decomposition import extract_trend_component
from tslab.plots.text_util import wrap_plot_text

plt.style.use("seaborn-v0_8-whitegrid")
_MIN_PNG_BYTES = 500


def _save(fig: plt.Figure, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.stem}_write.png")
    fig.savefig(tmp, format="png", dpi=120, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    with Image.open(tmp) as im:
        im.convert("RGB").save(path, format="PNG")
    tmp.unlink(missing_ok=True)
    return path


def plot_cross_correlation_bars(result: CorrelationResult, path: Path) -> Path:
    t = result.table.dropna(subset=["correlation"])
    fig, ax = plt.subplots(figsize=(11, 5))
    colors = ["#c55a11" if r < 0 else "#1f4e79" for r in t["correlation"]]
    ax.bar(t["lag"], t["correlation"], color=colors, edgecolor="white", linewidth=0.3)
    ax.axhline(0, color="gray", lw=0.8)
    ax.set_xlabel("Lag h")
    ax.set_ylabel("Pearson-Korrelation")
    ax.set_title(
        wrap_plot_text(
            f"Kreuzkorrelation: {result.series_a} vs {result.series_b} "
            f"[{result.analysis_mode}]\n"
            f"Fenster: {result.study.analysis_label} ({result.aligned_observations} gemeinsame Monate)",
            width=58,
        ),
        fontsize=10,
    )
    fig.text(0.5, 0.01, LAG_DEFINITION, ha="center", fontsize=7, style="italic")
    fig.subplots_adjust(bottom=0.14)
    return _save(fig, path)


def _axis_limits(series: pd.Series, *, pad_frac: float = 0.08) -> tuple[float, float]:
    lo, hi = float(series.min()), float(series.max())
    span = hi - lo
    pad = span * pad_frac if span > 0 else max(abs(hi), abs(lo), 1.0) * pad_frac
    return lo - pad, hi + pad


def plot_aligned_series(result: CorrelationResult, a: pd.Series, b: pd.Series, path: Path) -> Path:
    """Zwei Y-Achsen: links Serie A, rechts Serie B (eigene Skala je Reihe)."""
    fig, ax_left = plt.subplots(figsize=(11, 5))
    ax_right = ax_left.twinx()

    color_a, color_b = "#1f4e79", "#c55a11"
    trend_a_color, trend_b_color = "#8db4e2", "#f0a88a"

    trend_meta_a = extract_trend_component(a)
    trend_meta_b = extract_trend_component(b)
    trend_a = trend_meta_a.trend
    trend_b = trend_meta_b.trend

    line_a, = ax_left.plot(
        a.index, a.values, color=color_a, lw=1.2, label=result.series_a
    )
    line_trend_a, = ax_left.plot(
        trend_a.index,
        trend_a.values,
        color=trend_a_color,
        lw=1.6,
        ls="--",
        label=f"{result.series_a} (Trendkomponente)",
    )
    line_b, = ax_right.plot(
        b.index, b.values, color=color_b, lw=1.2, label=result.series_b
    )
    line_trend_b, = ax_right.plot(
        trend_b.index,
        trend_b.values,
        color=trend_b_color,
        lw=1.6,
        ls="--",
        label=f"{result.series_b} (Trendkomponente)",
    )

    ax_left.set_ylim(_axis_limits(pd.concat([a, trend_a])))
    ax_right.set_ylim(_axis_limits(pd.concat([b, trend_b])))

    ax_left.set_ylabel(
        f"{result.series_a}\n(min={a.min():.2f}, max={a.max():.2f})",
        color=color_a,
        fontsize=9,
    )
    ax_right.set_ylabel(
        f"{result.series_b}\n(min={b.min():.2f}, max={b.max():.2f})",
        color=color_b,
        fontsize=9,
    )
    ax_left.tick_params(axis="y", labelcolor=color_a)
    ax_right.tick_params(axis="y", labelcolor=color_b)

    ax_left.set_title(
        wrap_plot_text(f"Originalwerte – {result.study.analysis_label}", width=52)
    )
    ax_left.set_xlabel("Zeit (Monatsdaten)")

    ax_left.legend(
        [line_a, line_trend_a, line_b, line_trend_b],
        [
            result.series_a,
            f"{result.series_a} (Trendkomponente)",
            result.series_b,
            f"{result.series_b} (Trendkomponente)",
        ],
        loc="upper left",
        fontsize=7,
        framealpha=0.9,
    )

    trend_note = trend_meta_a.footnote_de()
    if (
        trend_meta_a.model != trend_meta_b.model
        or trend_meta_a.period != trend_meta_b.period
    ):
        trend_note = (
            f"{result.series_a}: {trend_meta_a.footnote_de()}; "
            f"{result.series_b}: {trend_meta_b.footnote_de()}"
        )

    fig.text(
        0.5,
        0.02,
        wrap_plot_text(
            "Quelle: observations (Upload-DB), nur Lesen\n" + trend_note,
            width=95,
        ),
        ha="center",
        fontsize=7,
        style="italic",
    )
    fig.subplots_adjust(bottom=0.16, right=0.88)
    return _save(fig, path)
