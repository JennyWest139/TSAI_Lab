"""Ausrichtung von Zeitreihenpaaren (taeglich, woechentlich, monatlich)."""

from __future__ import annotations

from datetime import date

import pandas as pd

from tslab.services.frequency_detect import detect_frequency_from_dates

_FREQ_ORDER = {"D": 0, "W": 1, "MS": 2, "Q": 3, "Y": 4}


def month_key(d: date) -> tuple[int, int]:
    return (d.year, d.month)


def month_start_stamp(year: int, month: int) -> str:
    return date(year, month, 1).isoformat()


def month_end_stamp(year: int, month: int) -> str:
    return pd.Period(year=year, month=month, freq="M").to_timestamp("M").date().isoformat()


def common_month_overlap_stamps(dates_a: list[date], dates_b: list[date]) -> list[str]:
    """Kalendermonate mit Daten in beiden Reihen; Stempel = 1. des Monats (MS)."""
    a_months = {month_key(d) for d in dates_a}
    b_months = {month_key(d) for d in dates_b}
    return [month_start_stamp(y, m) for y, m in sorted(a_months & b_months)]


def collapse_series_to_month_end(series: pd.Series) -> pd.Series:
    """Eine Beobachtung pro Kalendermonat (letzter Wert), Index = Monatsende."""
    s = series.dropna().astype(float).sort_index()
    if s.empty:
        return s
    grouped = s.groupby(s.index.to_period("M"), observed=True)
    out = grouped.last()
    out.index = out.index.to_timestamp("M")
    return out


def to_month_end_timestamp(value: str | pd.Timestamp) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    return ts.to_period("M").to_timestamp("M")


def snap_to_overlap_stamp(overlap_dates: list[str], value: str) -> str:
    """ISO-Datum auf gemeinsamen Monatsstempel abbilden (1. des Monats)."""
    if value in overlap_dates:
        return value
    d = date.fromisoformat(value)
    candidate = month_start_stamp(d.year, d.month)
    if candidate in overlap_dates:
        return candidate
    raise ValueError(
        f"{value} liegt ausserhalb der gemeinsamen Monatsbasis "
        f"({overlap_dates[0]} … {overlap_dates[-1]})."
    )


def align_monthly_pair(series_a: pd.Series, series_b: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Gemeinsame Monatsbasis (unabhaengig vom Stichtag innerhalb des Monats)."""
    a = collapse_series_to_month_end(series_a)
    b = collapse_series_to_month_end(series_b)
    common = a.index.intersection(b.index)
    if common.empty:
        raise ValueError("Keine gemeinsame Monatsbasis zwischen den Zeitreihen.")
    return a.loc[common], b.loc[common]


def common_exact_overlap_stamps(dates_a: list[date], dates_b: list[date]) -> list[str]:
    """Gemeinsame Kalendertage (exakter Zeitstempel in beiden Reihen)."""
    b_set = {d.isoformat() for d in dates_b}
    return sorted(d.isoformat() for d in dates_a if d.isoformat() in b_set)


def _iso_week_key(d: date) -> tuple[int, int]:
    y, w, _ = d.isocalendar()
    return y, w


def common_week_overlap_stamps(dates_a: list[date], dates_b: list[date]) -> list[str]:
    """Gemeinsame ISO-Wochen; Stempel von Reihe A."""
    b_weeks = {_iso_week_key(d) for d in dates_b}
    by_week: dict[tuple[int, int], str] = {}
    for d in sorted(dates_a):
        key = _iso_week_key(d)
        if key in b_weeks:
            by_week[key] = d.isoformat()
    return [by_week[k] for k in sorted(by_week)]


def overlap_stamps_for_frequency(
    dates_a: list[date], dates_b: list[date], frequency: str
) -> list[str]:
    if frequency == "D":
        return common_exact_overlap_stamps(dates_a, dates_b)
    if frequency == "W":
        return common_week_overlap_stamps(dates_a, dates_b)
    return common_month_overlap_stamps(dates_a, dates_b)


def pick_narrower_window(
    first_a: date,
    last_a: date,
    count_a: int,
    first_b: date,
    last_b: date,
    count_b: int,
) -> tuple[date, date, str]:
    """Zeitraum der eingeschraenkteren Reihe (kuerzerer Spanne, bei Gleichstand weniger n)."""
    span_a = (last_a - first_a).days
    span_b = (last_b - first_b).days
    if span_a < span_b or (span_a == span_b and count_a <= count_b):
        return first_a, last_a, "a"
    return first_b, last_b, "b"


def filter_stamps_to_window(
    stamps: list[str], window_first: date, window_last: date
) -> list[str]:
    return [
        s
        for s in stamps
        if window_first <= date.fromisoformat(s) <= window_last
    ]


def resolve_pair_frequency(
    dates_a: list[date], dates_b: list[date]
) -> tuple[str, str, str | None]:
    """Frequenz fuer Paarvergleich; bei Mismatch Hinweistext."""
    fa, la = detect_frequency_from_dates(dates_a)
    fb, lb = detect_frequency_from_dates(dates_b)
    if fa == fb:
        return fa, la, None

    freqs = {fa, fb}
    if "D" in freqs and freqs & {"MS", "Q", "Y"}:
        if "MS" in freqs:
            return (
                "MS",
                la if fa == "MS" else lb,
                "Unterschiedliche Frequenzen: taegliche Reihe wird auf monatliche "
                "Basis aggregiert (Stichtag der monatlichen Reihe).",
            )
        coarser = "Q" if "Q" in freqs else "Y"
        _, label = detect_frequency_from_dates(dates_a if fa == coarser else dates_b)
        return (
            coarser,
            label,
            f"Unterschiedliche Frequenzen: feinere Reihe wird {label.lower} aggregiert.",
        )

    coarser = fa if _FREQ_ORDER.get(fa, 2) >= _FREQ_ORDER.get(fb, 2) else fb
    label = la if coarser == fa else lb
    return (
        coarser,
        label,
        f"Unterschiedliche Frequenzen: Vergleich auf {label.lower()}er Basis.",
    )


def collapse_series_to_week_end(series: pd.Series) -> pd.Series:
    """Eine Beobachtung pro ISO-Woche (letzter Wert)."""
    s = series.dropna().astype(float).sort_index()
    if s.empty:
        return s
    grouped = s.groupby(s.index.to_period("W"), observed=True)
    out = grouped.last()
    out.index = out.index.to_timestamp("W")
    return out


def align_pair_for_frequency(
    series_a: pd.Series, series_b: pd.Series, frequency: str
) -> tuple[pd.Series, pd.Series]:
    if frequency == "D":
        a = series_a.dropna().astype(float).sort_index()
        b = series_b.dropna().astype(float).sort_index()
        common = a.index.intersection(b.index)
        if common.empty:
            raise ValueError("Keine gemeinsamen Tagesdaten.")
        return a.loc[common], b.loc[common]
    if frequency == "W":
        a = collapse_series_to_week_end(series_a)
        b = collapse_series_to_week_end(series_b)
        common = a.index.intersection(b.index)
        if common.empty:
            raise ValueError("Keine gemeinsamen Wochen.")
        return a.loc[common], b.loc[common]
    return align_monthly_pair(series_a, series_b)


def snap_to_overlap_stamp_for_frequency(
    overlap_dates: list[str], value: str, frequency: str
) -> str:
    if frequency in ("MS", "Q", "Y"):
        return snap_to_overlap_stamp(overlap_dates, value)
    if value in overlap_dates:
        return value
    raise ValueError(
        f"{value} ist kein gueltiger Zeitstempel der Schnittmenge "
        f"({overlap_dates[0]} … {overlap_dates[-1]})."
    )


def compute_pair_overlap(
    dates_a: list[date],
    dates_b: list[date],
    *,
    first_a: date,
    last_a: date,
    count_a: int,
    first_b: date,
    last_b: date,
    count_b: int,
    slug_a: str,
    slug_b: str,
    label_a: str,
    label_b: str,
    frequency: str | None = None,
) -> dict | None:
    """Schnittmenge, Vorbelegung auf Fenster der eingeschraenkteren Reihe."""
    auto_freq, auto_label, freq_note = resolve_pair_frequency(dates_a, dates_b)
    eff_freq = frequency if frequency in ("D", "W", "MS", "Y") else auto_freq
    eff_label = auto_label
    if frequency and frequency != auto_freq and not freq_note:
        from tslab.services.frequency_detect import detect_frequency_from_dates

        _, eff_label = detect_frequency_from_dates(
            dates_a if eff_freq == auto_freq else dates_b
        )

    all_stamps = overlap_stamps_for_frequency(dates_a, dates_b, eff_freq)
    if not all_stamps:
        return None

    win_first, win_last, narrower_side = pick_narrower_window(
        first_a, last_a, count_a, first_b, last_b, count_b
    )
    stamps = filter_stamps_to_window(all_stamps, win_first, win_last)
    if not stamps:
        return None

    narrower_slug = slug_a if narrower_side == "a" else slug_b
    narrower_label = label_a if narrower_side == "a" else label_b
    window_note = (
        f"Vorbelegung: gesamter Verfuegbarkeitszeitraum der eingeschraenkteren Reihe "
        f"({narrower_label}) — {len(stamps)} gemeinsame Zeitpunkte."
    )

    return {
        "overlap_start": stamps[0],
        "overlap_end": stamps[-1],
        "suggested_start": stamps[0],
        "suggested_end": stamps[-1],
        "overlap_observations": len(stamps),
        "dates": stamps,
        "suggested_frequency": eff_freq,
        "suggested_frequency_label": eff_label,
        "frequency_note": freq_note,
        "window_note": window_note,
        "narrower_series_slug": narrower_slug,
        "narrower_series_label": narrower_label,
    }
