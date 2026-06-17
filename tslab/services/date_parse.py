"""Flexible Datumserkennung und -parsing fuer CSV/Excel-Upload."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pandas as pd

DATE_PARSE_MODES: list[dict[str, str]] = [
    {
        "id": "auto",
        "label": "Automatisch erkennen",
        "order": "Wird aus der Datei abgeleitet",
        "example": "",
    },
    {
        "id": "iso",
        "label": "Jahr – Monat – Tag (ISO)",
        "order": "Jahr → Monat → Tag",
        "example": "1959-09-30",
    },
    {
        "id": "dmy_dot",
        "label": "Tag.Monat.Jahr",
        "order": "Tag → Monat → Jahr",
        "example": "30.09.1959",
    },
    {
        "id": "dmy_dash",
        "label": "Tag-Monat-Jahr",
        "order": "Tag → Monat → Jahr",
        "example": "30-09-1959",
    },
    {
        "id": "ymd_slash",
        "label": "Jahr/Monat/Tag",
        "order": "Jahr → Monat → Tag",
        "example": "1959/09/30",
    },
    {
        "id": "mdy_slash",
        "label": "Monat/Tag/Jahr (US)",
        "order": "Monat → Tag → Jahr",
        "example": "09/30/1959",
    },
    {
        "id": "mixed_eu",
        "label": "Gemischt / uneinheitlich (Tag zuerst)",
        "order": "Tag hat Vorrang bei Mehrdeutigkeit",
        "example": "verschiedene Schreibweisen",
    },
    {
        "id": "mixed_us",
        "label": "Gemischt / uneinheitlich (Monat zuerst)",
        "order": "Monat hat Vorrang bei Mehrdeutigkeit",
        "example": "verschiedene Schreibweisen",
    },
]


class DateParseMode(str, Enum):
    AUTO = "auto"
    ISO = "iso"
    DMY_DOT = "dmy_dot"
    DMY_DASH = "dmy_dash"
    YMD_SLASH = "ymd_slash"
    MDY_SLASH = "mdy_slash"
    MIXED_EU = "mixed_eu"
    MIXED_US = "mixed_us"
    STRFTIME = "strftime"


@dataclass(frozen=True)
class DateFormatDetection:
    mode: str
    strftime_format: str | None
    dayfirst: bool | None
    label_de: str
    order_de: str
    example: str
    parse_rate: float
    parsed_count: int
    total_count: int
    samples: list[dict[str, str]]

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "strftime_format": self.strftime_format,
            "dayfirst": self.dayfirst,
            "label_de": self.label_de,
            "order_de": self.order_de,
            "example": self.example,
            "parse_rate": round(self.parse_rate, 4),
            "parsed_count": self.parsed_count,
            "total_count": self.total_count,
            "samples": self.samples,
        }


_MODE_META = {m["id"]: m for m in DATE_PARSE_MODES}

_STRFTIME_BY_MODE: dict[str, tuple[str | None, bool | None]] = {
    DateParseMode.ISO.value: (None, None),
    DateParseMode.DMY_DOT.value: ("%d.%m.%Y", True),
    DateParseMode.DMY_DASH.value: ("%d-%m-%Y", True),
    DateParseMode.YMD_SLASH.value: ("%Y/%m/%d", False),
    DateParseMode.MDY_SLASH.value: ("%m/%d/%Y", False),
    DateParseMode.MIXED_EU.value: (None, True),
    DateParseMode.MIXED_US.value: (None, False),
}


def _clean_series(series: pd.Series) -> pd.Series:
    return series.dropna().astype(str).str.strip().loc[lambda s: s != ""]


def _parse_with_spec(
    series: pd.Series,
    *,
    mode: str,
    strftime_format: str | None = None,
    dayfirst: bool | None = None,
) -> pd.Series:
    s = series.astype(str).str.strip()

    if mode == DateParseMode.AUTO.value:
        detected = detect_date_format(series)
        return _parse_with_spec(
            series,
            mode=detected.mode,
            strftime_format=detected.strftime_format,
            dayfirst=detected.dayfirst,
        )

    if mode == DateParseMode.STRFTIME.value:
        if not strftime_format:
            raise ValueError("strftime-Modus benoetigt date_format.")
        return pd.to_datetime(s, format=strftime_format, errors="coerce")

    fmt, default_dayfirst = _STRFTIME_BY_MODE.get(mode, (None, True))
    eff_fmt = strftime_format or fmt
    eff_dayfirst = dayfirst if dayfirst is not None else default_dayfirst

    if mode == DateParseMode.ISO.value:
        try:
            return pd.to_datetime(s, format="ISO8601", errors="coerce")
        except (ValueError, TypeError):
            return pd.to_datetime(s, errors="coerce")

    if mode in (DateParseMode.MIXED_EU.value, DateParseMode.MIXED_US.value):
        try:
            return pd.to_datetime(
                s, format="mixed", dayfirst=bool(eff_dayfirst), errors="coerce"
            )
        except (ValueError, TypeError):
            return pd.to_datetime(s, errors="coerce", dayfirst=bool(eff_dayfirst))

    if eff_fmt:
        return pd.to_datetime(s, format=eff_fmt, errors="coerce")

    return pd.to_datetime(s, errors="coerce", dayfirst=bool(eff_dayfirst))


def _score_parsed(parsed: pd.Series, total: int) -> float:
    if total == 0:
        return 0.0
    return float(parsed.notna().sum()) / float(total)


def _build_samples(raw: pd.Series, parsed: pd.Series, limit: int = 5) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for r, p in zip(raw.head(limit), parsed.head(limit)):
        out.append(
            {
                "raw": str(r),
                "parsed": p.date().isoformat() if pd.notna(p) else "—",
            }
        )
    return out


def _detection_from_parse(
    raw: pd.Series,
    parsed: pd.Series,
    *,
    mode: str,
    strftime_format: str | None,
    dayfirst: bool | None,
) -> DateFormatDetection:
    meta = _MODE_META.get(mode, _MODE_META["auto"])
    total = len(raw)
    ok = int(parsed.notna().sum())
    return DateFormatDetection(
        mode=mode,
        strftime_format=strftime_format,
        dayfirst=dayfirst,
        label_de=meta["label"],
        order_de=meta["order"],
        example=meta["example"],
        parse_rate=_score_parsed(parsed, total),
        parsed_count=ok,
        total_count=total,
        samples=_build_samples(raw, parsed),
    )


def detect_date_format(series: pd.Series) -> DateFormatDetection:
    """Erkennt das beste Datumsformat fuer eine Spalte."""
    clean = _clean_series(series)
    if clean.empty:
        raise ValueError("Keine Datumswerte in der gewaehlten Spalte.")

    sample = clean.head(200)
    total = len(sample)
    candidates: list[tuple[str, str | None, bool | None, pd.Series]] = []

    for mode_id, (fmt, df) in _STRFTIME_BY_MODE.items():
        parsed = _parse_with_spec(sample, mode=mode_id, strftime_format=fmt, dayfirst=df)
        candidates.append((mode_id, fmt, df, parsed))

    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        parsed = pd.to_datetime(sample, format=fmt, errors="coerce")
        dayfirst = fmt.startswith("%d")
        candidates.append((DateParseMode.STRFTIME.value, fmt, dayfirst, parsed))

    best_mode, best_fmt, best_df, best_parsed = max(
        candidates,
        key=lambda item: (_score_parsed(item[3], total), item[3].notna().sum()),
    )

    if best_mode == DateParseMode.STRFTIME.value and best_fmt:
        for mode_id, (fmt, dayfirst) in _STRFTIME_BY_MODE.items():
            if fmt == best_fmt:
                best_mode = mode_id
                best_df = dayfirst
                break

    mapped_fmt = (
        best_fmt
        if best_mode == DateParseMode.STRFTIME.value
        else _STRFTIME_BY_MODE.get(best_mode, (None, None))[0]
    )
    return _detection_from_parse(
        sample,
        best_parsed,
        mode=best_mode,
        strftime_format=mapped_fmt,
        dayfirst=best_df,
    )


def analyze_date_column(
    series: pd.Series,
    *,
    mode: str = "auto",
    strftime_format: str | None = None,
    dayfirst: bool | None = None,
) -> DateFormatDetection:
    """Validiert Parsing fuer UI (Vorschau / Live-Check)."""
    clean = _clean_series(series)
    if clean.empty:
        raise ValueError("Keine Datumswerte in der gewaehlten Spalte.")

    if mode == DateParseMode.AUTO.value:
        return detect_date_format(clean)

    parsed = _parse_with_spec(
        clean,
        mode=mode,
        strftime_format=strftime_format,
        dayfirst=dayfirst,
    )
    eff_fmt = strftime_format
    eff_dayfirst = dayfirst
    if mode in _STRFTIME_BY_MODE:
        default_fmt, default_df = _STRFTIME_BY_MODE[mode]
        eff_fmt = eff_fmt or default_fmt
        if eff_dayfirst is None:
            eff_dayfirst = default_df

    return _detection_from_parse(
        clean.head(200),
        parsed.head(200),
        mode=mode,
        strftime_format=eff_fmt,
        dayfirst=eff_dayfirst,
    )


def parse_observation_dates(
    series: pd.Series,
    *,
    mode: str = "auto",
    strftime_format: str | None = None,
    dayfirst: bool | None = None,
) -> pd.Series:
    """Parst Datumsspalte fuer DB-Import."""
    parsed = _parse_with_spec(
        series,
        mode=mode,
        strftime_format=strftime_format,
        dayfirst=dayfirst,
    )
    if parsed.notna().sum() == 0:
        hint = analyze_date_column(series, mode=mode, strftime_format=strftime_format, dayfirst=dayfirst)
        raise ValueError(
            f"Kein Datum konnte gelesen werden (Modus: {hint.label_de}). "
            f"Bitte Reihenfolge Jahr/Monat/Tag in der Oberflaeche pruefen."
        )
    rate = _score_parsed(parsed, len(series))
    if rate < 0.5:
        raise ValueError(
            f"Nur {rate:.0%} der Datumswerte lesbar — bitte Datumsformat anpassen."
        )
    return parsed
