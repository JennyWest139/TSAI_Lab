"""JSON-Vorschau der TSA-Zeitfenster fuer interaktive Grafik."""

from __future__ import annotations

from typing import Any

import pandas as pd

from tslab.services.forecast_plot_window import (
    resolve_forecast_plot_bounds,
    resolve_forecast_plot_window,
)
from tslab.services.timeseries_store import load_series_full_pandas
from tslab.services.tsa_context import load_tsa_context


def _iso(ts: pd.Timestamp) -> str:
    return ts.date().isoformat()


def build_tsa_window_preview(
    session,
    *,
    mode_config,
    series_slug: str,
    start_date: str | None,
    end_date: str | None,
    forecast_end: str | None,
    plot_pre_years: float | None = None,
    plot_forecast_years: float | None = None,
    plot_post_years: float | None = None,
) -> dict[str, Any]:
    plot_window = resolve_forecast_plot_window(
        pre_years=plot_pre_years,
        forecast_years=plot_forecast_years,
        post_years=plot_post_years,
    )
    ctx = load_tsa_context(
        session,
        mode_config,
        series_slug=series_slug,
        start_date=start_date,
        end_date=end_date,
        forecast_end=forecast_end,
        plot_window=plot_window,
    )
    study = ctx.study
    levels = load_series_full_pandas(session, series_slug).dropna().sort_index()
    dates = [_iso(d) for d in levels.index]
    values = [None if pd.isna(v) else round(float(v), 6) for v in levels.values]

    regions: list[dict] = [
        {
            "label": "Training",
            "start": _iso(study.start_date),
            "end": _iso(study.cutoff),
            "color": "rgba(59, 130, 246, 0.2)",
        },
    ]
    if ctx.holdout_prices is not None and not ctx.holdout_prices.empty:
        regions.append(
            {
                "label": "Holdout (Ist)",
                "start": _iso(ctx.holdout_prices.index.min()),
                "end": _iso(ctx.holdout_prices.index.max()),
                "color": "rgba(34, 197, 94, 0.2)",
            }
        )
    if study.forecast_end > study.cutoff:
        forecast_start = study.cutoff + pd.offsets.MonthBegin(1)
        regions.append(
            {
                "label": "Prognose",
                "start": _iso(forecast_start),
                "end": _iso(study.forecast_end),
                "color": "rgba(249, 115, 22, 0.2)",
            }
        )

    plot_start, plot_end = resolve_forecast_plot_bounds(
        study.cutoff,
        ctx.horizons.forward_index,
        ctx.holdout_prices,
        plot_window,
    )
    plot_region = {
        "label": "Plot-Sichtfenster",
        "start": _iso(plot_start),
        "end": _iso(plot_end),
        "color": "transparent",
        "border": True,
    }

    return {
        "slug": series_slug,
        "dates": dates,
        "values": values,
        "regions": regions,
        "plot_region": plot_region,
        "cutoff": _iso(study.cutoff),
        "forecast_end": _iso(study.forecast_end),
        "train_label": study.analysis_label,
        "forecast_label": study.forecast_label,
        "observation_count": len(levels),
    }
