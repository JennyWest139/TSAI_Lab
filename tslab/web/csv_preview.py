"""CSV/Excel-Vorschau fuer den Upload-Dialog."""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

from tslab.config_loader import load_defaults
from tslab.services.date_parse import (
    DATE_PARSE_MODES,
    analyze_date_column,
    detect_date_format,
    parse_observation_dates,
)
from tslab.services.frequency_detect import detect_frequency_from_dates
from tslab.services.ingest_werte import _parse_german_number
from tslab.web.mock_data import FREQUENCY_OPTIONS

_PREVIEW_LINES = 45


def _read_raw_text(data: bytes, filename: str) -> tuple[str, str]:
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace"), "utf-8"


def _guess_sep(text: str) -> str:
    first = text.splitlines()[0] if text else ""
    if ";" in first and first.count(";") >= first.count(","):
        return ";"
    if "\t" in first:
        return "\t"
    return ","


def load_upload_dataframe(data: bytes, filename: str) -> tuple[pd.DataFrame, str, str]:
    ext = Path(filename).suffix.lower()
    if ext in (".xlsx", ".xls"):
        try:
            df = pd.read_excel(io.BytesIO(data), dtype=str)
            return df, ";", "excel"
        except ImportError as exc:
            raise ValueError(
                "Excel-Dateien benoetigen openpyxl: pip install openpyxl"
            ) from exc

    text, encoding = _read_raw_text(data, filename)
    sep = _guess_sep(text)
    df = pd.read_csv(io.StringIO(text), sep=sep, encoding=encoding, dtype=str)
    return df, sep, encoding


def _guess_date_column(df: pd.DataFrame) -> str | None:
    best_col: str | None = None
    best_score = 0.0
    for col in df.columns:
        try:
            det = detect_date_format(df[col])
            if det.parse_rate > best_score:
                best_score = det.parse_rate
                best_col = str(col)
        except ValueError:
            continue
    return best_col


def _numeric_columns(df: pd.DataFrame) -> list[str]:
    cols: list[str] = []
    for col in df.columns:
        nums = _parse_german_number(df[col])
        if nums.notna().sum() >= 3:
            cols.append(str(col))
    return cols


def date_detection_for_column(
    df: pd.DataFrame,
    date_column: str,
    *,
    mode: str = "auto",
    strftime_format: str | None = None,
    dayfirst: bool | None = None,
) -> dict:
    if date_column not in df.columns:
        raise ValueError(f"Spalte {date_column!r} nicht gefunden.")
    det = analyze_date_column(
        df[date_column],
        mode=mode,
        strftime_format=strftime_format,
        dayfirst=dayfirst,
    )
    return det.to_dict()


def preview_upload_bytes(data: bytes, filename: str) -> dict:
    """Vorschau fuer Upload-UI: Texteditor + Spaltenwahl."""
    text, encoding = _read_raw_text(data, filename)
    lines = text.splitlines()
    preview_text = "\n".join(lines[:_PREVIEW_LINES])
    if len(lines) > _PREVIEW_LINES:
        preview_text += f"\n… ({len(lines) - _PREVIEW_LINES} weitere Zeilen)"

    df, sep, source = load_upload_dataframe(data, filename)
    columns = [str(c) for c in df.columns]
    date_col = _guess_date_column(df)
    value_cols = _numeric_columns(df)

    suggested_value = None
    if value_cols:
        cfg = load_defaults().get("csv", {})
        default_val = cfg.get("value_column")
        if default_val in value_cols:
            suggested_value = default_val
        else:
            suggested_value = value_cols[0]

    freq_id, freq_label = "MS", "Monatlich"
    date_detection: dict | None = None
    date_columns_info: dict[str, dict] = {}

    for col in columns:
        try:
            date_columns_info[col] = detect_date_format(df[col]).to_dict()
        except ValueError:
            continue

    if date_col and date_col in date_columns_info:
        date_detection = date_columns_info[date_col]
        try:
            parsed = parse_observation_dates(df[date_col], mode=date_detection["mode"])
            dates = [d.date() for d in parsed.dropna().dt.to_pydatetime()]
            if dates:
                freq_id, freq_label = detect_frequency_from_dates(dates)
        except ValueError:
            pass

    return {
        "filename": filename,
        "preview_text": preview_text,
        "line_count": len(lines),
        "encoding": encoding,
        "sep": sep,
        "source": source,
        "columns": columns,
        "suggested_date_column": date_col,
        "suggested_value_column": suggested_value,
        "value_columns": value_cols,
        "suggested_frequency": freq_id,
        "suggested_frequency_label": freq_label,
        "frequencies": FREQUENCY_OPTIONS,
        "date_parse_modes": DATE_PARSE_MODES,
        "date_detection": date_detection,
        "date_columns_info": date_columns_info,
    }
