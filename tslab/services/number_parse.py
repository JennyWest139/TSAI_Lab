"""Dezimalzahl-Parsing fuer Upload (Komma vs. Punkt)."""

from __future__ import annotations

import re

import pandas as pd

DECIMAL_MODES = [
    {"id": "auto", "label": "Automatisch erkennen"},
    {"id": "comma", "label": "Komma (deutsch, z. B. 1.234,56)"},
    {"id": "dot", "label": "Punkt (englisch, z. B. 1,234.56)"},
    {"id": "integer", "label": "Ganzzahlen (kein Dezimaltrennzeichen)"},
]


def _clean_raw(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.strip()
    return s.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})


def _parse_comma_decimal(s: pd.Series) -> pd.Series:
    """Deutsch: Tausenderpunkt entfernen, Dezimalkomma -> Punkt."""
    out = s.copy()
    out = out.str.replace(".", "", regex=False)
    out = out.str.replace(",", ".", regex=False)
    return pd.to_numeric(out, errors="coerce")


def _parse_dot_decimal(s: pd.Series) -> pd.Series:
    """Englisch: Tausendertrennzeichen entfernen, Dezimalpunkt behalten."""
    out = s.copy()
    out = out.str.replace(",", "", regex=False)
    return pd.to_numeric(out, errors="coerce")


def _score_mode(s: pd.Series, mode: str) -> float:
    if mode == "comma":
        parsed = _parse_comma_decimal(s)
    elif mode == "dot":
        parsed = _parse_dot_decimal(s)
    else:
        parsed = pd.to_numeric(s, errors="coerce")
    if len(s) == 0:
        return 0.0
    return float(parsed.notna().sum()) / len(s)


def detect_decimal_mode(series: pd.Series) -> str:
    """Erkennt Komma- vs. Punkt-Dezimaltrennzeichen anhand der Spaltenwerte."""
    raw = _clean_raw(series).dropna()
    if raw.empty:
        return "comma"

    sample = raw.head(200)
    comma_score = _score_mode(sample, "comma")
    dot_score = _score_mode(sample, "dot")

    has_comma = sample.str.contains(",", regex=False).any()
    has_dot = sample.str.contains(r"\.", regex=True).any()

    if comma_score >= 0.9 and dot_score < 0.5:
        return "comma"
    if dot_score >= 0.9 and comma_score < 0.5:
        return "dot"
    if comma_score > dot_score + 0.1:
        return "comma"
    if dot_score > comma_score + 0.1:
        return "dot"

    # Heuristik: letztes Trennzeichen in typischen Zahlen
    last_sep_comma = 0
    last_sep_dot = 0
    for val in sample.head(50):
        text = str(val)
        m_comma = re.search(r",(\d{1,4})$", text)
        m_dot = re.search(r"\.(\d{1,4})$", text)
        if m_comma:
            last_sep_comma += 1
        if m_dot:
            last_sep_dot += 1
    if last_sep_comma > last_sep_dot:
        return "comma"
    if last_sep_dot > last_sep_comma:
        return "dot"
    if has_comma and not has_dot:
        return "comma"
    if has_dot and not has_comma:
        return "dot"
    return "comma"


def parse_locale_number(series: pd.Series, mode: str = "auto") -> pd.Series:
    """Wandelt Spaltenwerte in float — Modus auto, comma, dot oder integer."""
    raw = _clean_raw(series)
    eff = detect_decimal_mode(raw) if mode == "auto" else mode
    if eff == "comma":
        return _parse_comma_decimal(raw)
    if eff == "dot":
        return _parse_dot_decimal(raw)
    return pd.to_numeric(raw, errors="coerce")


def analyze_value_column(series: pd.Series, *, mode: str = "auto") -> dict:
    """Vorschau fuer Upload-UI: erkanntes Format + Beispielwerte."""
    raw = _clean_raw(series)
    eff = detect_decimal_mode(raw) if mode == "auto" else mode
    parsed = parse_locale_number(series, eff)
    samples: list[dict] = []
    for idx in raw.dropna().head(8).index:
        r = raw.loc[idx]
        p = parsed.loc[idx]
        samples.append(
            {
                "raw": str(r),
                "parsed": None if pd.isna(p) else round(float(p), 6),
            }
        )
    total = int(raw.notna().sum())
    parsed_count = int(parsed.notna().sum())
    return {
        "mode": eff,
        "parse_rate": parsed_count / total if total else 0.0,
        "parsed_count": parsed_count,
        "total_count": total,
        "samples": samples,
    }
