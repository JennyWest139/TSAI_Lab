"""Einheitliche Output-Ordnernamen fuer CORR und TSA."""

from __future__ import annotations

from datetime import date
from pathlib import Path


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


def allocate_unique_output_folder(parent: Path, base_name: str) -> str:
    """Vergibt base_name oder base_name_N (hoechstes vorhandenes N + 1)."""
    if not parent.is_dir():
        return base_name

    max_suffix = -1
    prefix = f"{base_name}_"
    for child in parent.iterdir():
        if not child.is_dir():
            continue
        name = child.name
        if name == base_name:
            max_suffix = max(max_suffix, 0)
            continue
        if not name.startswith(prefix):
            continue
        tail = name[len(prefix) :]
        if tail.isdigit():
            max_suffix = max(max_suffix, int(tail))

    if max_suffix < 0:
        return base_name
    return f"{base_name}_{max_suffix + 1}"
