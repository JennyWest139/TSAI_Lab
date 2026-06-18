"""JSON-Daten fuer interaktive Zeitreihen-Grafiken (Web)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from tslab.services.analysis_mode import AnalysisMode, get_analysis_mode_config, prepare_model_returns
from tslab.services.decomposition import extract_trend_component
from tslab.services.month_align import align_pair_for_frequency
from tslab.services.transforms import log_returns


def _iso_dates(index: pd.DatetimeIndex) -> list[str]:
    return [pd.Timestamp(d).date().isoformat() for d in index]


def _float_values(series: pd.Series) -> list[float | None]:
    return [None if pd.isna(v) else round(float(v), 6) for v in series.values]


def _slice_series(
    series: pd.Series,
    *,
    start: str | None = None,
    end: str | None = None,
) -> pd.Series:
    s = series.dropna().sort_index()
    if start:
        s = s.loc[s.index >= pd.Timestamp(start)]
    if end:
        s = s.loc[s.index <= pd.Timestamp(end)]
    return s


def _align_pair(
    series_a: pd.Series,
    series_b: pd.Series,
    *,
    start: str | None = None,
    end: str | None = None,
    frequency: str = "MS",
) -> tuple[pd.Series, pd.Series]:
    """Gemeinsame Frequenzbasis im Fenster."""
    a, b = align_pair_for_frequency(series_a, series_b, frequency)
    if start:
        a = a.loc[a.index >= pd.Timestamp(start)]
        b = b.loc[b.index >= pd.Timestamp(start)]
    if end:
        a = a.loc[a.index <= pd.Timestamp(end)]
        b = b.loc[b.index <= pd.Timestamp(end)]
    if a.empty or b.empty:
        raise ValueError("Keine gemeinsamen Zeitstempel im gewaehlten Fenster.")
    common = a.index.intersection(b.index)
    if common.empty:
        raise ValueError("Keine gemeinsamen Zeitstempel im gewaehlten Fenster.")
    return a.loc[common], b.loc[common]


def _returns_recommended(levels: pd.Series, slug: str) -> bool:
    """Log-Renditen sind fuer Kursindizes sinnvoll; sonst nur per Nutzerwahl."""
    if levels.empty or not bool((levels > 0).all()):
        return False
    price_like = {"pdax", "dax", "dowjones"}
    return slug.lower() in price_like


def _returns_payload(
    levels: pd.Series,
    *,
    analysis_mode: str | None,
) -> dict[str, Any] | None:
    pos = levels[levels > 0]
    if len(pos) < 3:
        return None
    mode = get_analysis_mode_config(AnalysisMode(analysis_mode or "thesis"))
    try:
        rets = prepare_model_returns(pos, mode)
    except Exception:
        rets = log_returns(pos)
    if rets.empty:
        return None
    return {
        "label": "kont. Renditen" if mode.mode is AnalysisMode.THESIS else "Renditen (detrended)",
        "dates": _iso_dates(rets.index),
        "values": _float_values(rets),
    }


def build_series_chart_payload(
    series: pd.Series,
    *,
    slug: str,
    label: str,
    start: str | None = None,
    end: str | None = None,
    include_returns: bool = False,
    analysis_mode: str | None = None,
) -> dict[str, Any]:
    """Originalwerte + Trendkomponente fuer Plotly."""
    levels = _slice_series(series, start=start, end=end)
    if levels.empty:
        raise ValueError("Keine Beobachtungen im gewaehlten Fenster.")

    trend_meta = None
    trend: pd.Series | None = None
    try:
        trend_meta = extract_trend_component(levels)
        trend = trend_meta.trend.reindex(levels.index)
    except ValueError:
        trend = pd.Series([None] * len(levels), index=levels.index)

    payload: dict[str, Any] = {
        "slug": slug,
        "label": label,
        "value_label": "Originalwert",
        "dates": _iso_dates(levels.index),
        "values": _float_values(levels),
        "trend": _float_values(trend) if trend is not None else [None] * len(levels),
        "trend_model": trend_meta.model if trend_meta else None,
        "trend_period": trend_meta.period if trend_meta else None,
        "trend_note": (
            trend_meta.footnote_de()
            if trend_meta
            else f"Trend nicht berechenbar: weniger als 6 Beobachtungen ({len(levels)})."
        ),
        "observation_count": len(levels),
        "returns_recommended": _returns_recommended(levels, slug),
    }
    if include_returns:
        payload["returns"] = _returns_payload(levels, analysis_mode=analysis_mode)
    return payload


def build_pair_chart_payload(
    series_a: pd.Series,
    series_b: pd.Series,
    *,
    slug_a: str,
    slug_b: str,
    label_a: str,
    label_b: str,
    start: str | None = None,
    end: str | None = None,
    include_returns: bool = False,
    analysis_mode: str | None = None,
    frequency: str = "MS",
) -> dict[str, Any]:
    """Zwei Reihen (Original + Trend) fuer Korrelations-Vorschau."""
    a, b = _align_pair(
        series_a, series_b, start=start, end=end, frequency=frequency
    )

    def _trend_or_null(levels: pd.Series) -> tuple[pd.Series, str]:
        try:
            meta = extract_trend_component(levels)
            return meta.trend.reindex(levels.index), meta.footnote_de()
        except ValueError:
            null = pd.Series([None] * len(levels), index=levels.index)
            note = f"Trend nicht berechenbar: weniger als 6 Beobachtungen ({len(levels)})."
            return null, note

    trend_a, note_a = _trend_or_null(a)
    trend_b, note_b = _trend_or_null(b)

    returns_a_ok = _returns_recommended(a, slug_a)
    returns_b_ok = _returns_recommended(b, slug_b)

    payload: dict[str, Any] = {
        "window": {
            "start": _iso_dates(a.index)[0],
            "end": _iso_dates(a.index)[-1],
        },
        "returns_recommended": returns_a_ok or returns_b_ok,
        "series_a": {
            "slug": slug_a,
            "label": label_a,
            "dates": _iso_dates(a.index),
            "values": _float_values(a),
            "trend": _float_values(trend_a),
            "trend_note": note_a,
        },
        "series_b": {
            "slug": slug_b,
            "label": label_b,
            "dates": _iso_dates(b.index),
            "values": _float_values(b),
            "trend": _float_values(trend_b),
            "trend_note": note_b,
        },
    }
    if include_returns:
        ret_a = _returns_payload(a, analysis_mode=analysis_mode)
        if ret_a:
            payload["returns_a"] = ret_a
        ret_b = _returns_payload(b, analysis_mode=analysis_mode)
        if ret_b:
            payload["returns_b"] = ret_b
    return payload
