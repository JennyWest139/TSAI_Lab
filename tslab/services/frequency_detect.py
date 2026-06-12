"""Periodizitaet aus Datumsabstaenden schaetzen."""

from __future__ import annotations

from datetime import date

import numpy as np

_LABELS = {
    "MS": "Monatlich",
    "W": "Woechentlich",
    "D": "Taeglich",
    "Y": "Jaehrlich",
    "H": "Stuendlich",
}


def detect_frequency_from_dates(dates: list[date]) -> tuple[str, str]:
    """
    Schaetzt MS, W, D, Y aus medianem Abstand in Tagen.

    Returns (freq_id, label_de).
    """
    if len(dates) < 2:
        return "MS", _LABELS["MS"]

    sorted_dates = sorted(dates)
    gaps = [
        (sorted_dates[i + 1] - sorted_dates[i]).days
        for i in range(len(sorted_dates) - 1)
        if sorted_dates[i + 1] > sorted_dates[i]
    ]
    if not gaps:
        return "MS", _LABELS["MS"]

    median = float(np.median(gaps))
    if median <= 2:
        return "D", _LABELS["D"]
    if median <= 10:
        return "W", _LABELS["W"]
    if median <= 45:
        return "MS", _LABELS["MS"]
    if median <= 120:
        return "Q", "Quartalsweise"
    if median <= 400:
        return "Y", _LABELS["Y"]
    return "MS", _LABELS["MS"]
