"""Einheitliche Output-Ordnernamen fuer CORR und TSA."""

from __future__ import annotations

from datetime import date


def _mode_prefix(mode_slug: str) -> str:
    return "th" if mode_slug == "thesis" else "ex"


def correlation_folder_name(
    *,
    mode_slug: str,
    series_a: str,
    series_b: str,
    start_date: date,
    end_date: date,
) -> str:
    prefix = _mode_prefix(mode_slug)
    return (
        f"CORR_{prefix}_{series_a}_vs_{series_b}_"
        f"{start_date.isoformat()}_to_{end_date.isoformat()}"
    )


def tsa_folder_name(
    *,
    mode_slug: str,
    series_slug: str,
    train_start: date,
    train_end: date,
) -> str:
    prefix = _mode_prefix(mode_slug)
    return (
        f"TSA_{prefix}_{series_slug}_"
        f"{train_start.isoformat()}_to_{train_end.isoformat()}"
    )
