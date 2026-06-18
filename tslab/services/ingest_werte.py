"""Einlesen der Diplomarbeit-CSV Werte.csv (Datum1 / PDAX)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from tslab.config_loader import load_defaults
from tslab.services.decomposition import pin_inferred_datetime_freq


def _parse_german_number(series: pd.Series) -> pd.Series:
    """Wandelt '4.256,08' oder '417,79' in float (Komma-Modus)."""
    from tslab.services.number_parse import parse_locale_number

    return parse_locale_number(series, "comma")


def load_pdax_series(
    csv_path: str | Path | None = None,
    *,
    date_column: str | None = None,
    value_column: str | None = None,
) -> pd.Series:
    """
    Liest monatliche PDAX-Zeitreihe.

    Returns
    -------
    pd.Series
        Index: DatetimeIndex (Monatsende), Name: PDAX, float, ohne NaN.
    """
    cfg = load_defaults()["csv"]
    path = Path(csv_path or load_defaults()["werte_csv"])
    date_col = date_column or cfg["date_column"]
    value_col = value_column or cfg["value_column"]

    df = pd.read_csv(
        path,
        sep=cfg.get("sep", ";"),
        encoding=cfg.get("encoding", "utf-8-sig"),
        dtype=str,
    )

    if date_col not in df.columns or value_col not in df.columns:
        raise KeyError(
            f"Erwartete Spalten {date_col!r} und {value_col!r}, "
            f"gefunden: {list(df.columns)}"
        )

    dates = pd.to_datetime(df[date_col], format=cfg.get("date_format", "%d.%m.%Y"))
    values = _parse_german_number(df[value_col])

    idx = pin_inferred_datetime_freq(pd.DatetimeIndex(dates))
    series = pd.Series(values.values, index=idx, name=value_col)
    series = series.dropna().sort_index()
    series = series[~series.index.duplicated(keep="last")]
    return series


def available_dates(series: pd.Series) -> list[pd.Timestamp]:
    """Für späteren Kalender: alle Tage mit Daten."""
    return list(series.index)
