"""CSV/Excel-Vorschau fuer den Upload-Dialog."""

from __future__ import annotations

from tslab.config_loader import load_defaults
from tslab.services.date_parse import (
    DATE_PARSE_MODES,
    analyze_date_column,
    detect_date_format,
    parse_observation_dates,
)
from tslab.services.frequency_detect import detect_frequency_from_dates
from tslab.services.number_parse import DECIMAL_MODES, analyze_value_column, parse_locale_number
from tslab.services.upload_io import load_upload_dataframe, read_raw_text
from tslab.web.mock_data import FREQUENCY_OPTIONS

_PREVIEW_LINES = 45


def _guess_date_column(df) -> str | None:
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


def _numeric_columns(df, *, decimal_mode: str = "auto") -> list[str]:
    cols: list[str] = []
    for col in df.columns:
        nums = parse_locale_number(df[col], decimal_mode)
        if nums.notna().sum() >= 3:
            cols.append(str(col))
    return cols


def date_detection_for_column(
    df,
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


def decimal_detection_for_column(
    df,
    value_column: str,
    *,
    mode: str = "auto",
) -> dict:
    if value_column not in df.columns:
        raise ValueError(f"Spalte {value_column!r} nicht gefunden.")
    return analyze_value_column(df[value_column], mode=mode)


def preview_upload_bytes(data: bytes, filename: str) -> dict:
    """Vorschau fuer Upload-UI: Texteditor + Spaltenwahl."""
    text, encoding = read_raw_text(data, filename)
    lines = text.splitlines()
    preview_text = "\n".join(lines[:_PREVIEW_LINES])
    if len(lines) > _PREVIEW_LINES:
        preview_text += f"\n… ({len(lines) - _PREVIEW_LINES} weitere Zeilen)"

    df, sep, source = load_upload_dataframe(data, filename)
    columns = [str(c) for c in df.columns]
    date_col = _guess_date_column(df)
    value_cols = _numeric_columns(df)

    suggested_value = None
    decimal_detection: dict | None = None
    if value_cols:
        cfg = load_defaults().get("csv", {})
        default_val = cfg.get("value_column")
        if default_val in value_cols:
            suggested_value = default_val
        else:
            suggested_value = value_cols[0]
        decimal_detection = decimal_detection_for_column(df, suggested_value)

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
            from tslab.services.silent_errors import log_suppressed_exception

            log_suppressed_exception()
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
        "decimal_modes": DECIMAL_MODES,
        "date_detection": date_detection,
        "decimal_detection": decimal_detection,
        "date_columns_info": date_columns_info,
    }
