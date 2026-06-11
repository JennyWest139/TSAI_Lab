"""Analyse-Zeitfenster: Korrelation vs. TSA (Cutoff = Ende)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

StudyMode = Literal["correlation", "tsa"]


@dataclass(frozen=True)
class AnalysisWindow:
    """Effektives Analysefenster [start_date, end_date] (inklusive)."""

    start_date: pd.Timestamp
    end_date: pd.Timestamp
    available_start: pd.Timestamp
    available_end: pd.Timestamp
    user_set_start: bool
    user_set_end: bool

    @property
    def label(self) -> str:
        return f"{self.start_date.date()} bis {self.end_date.date()}"


@dataclass(frozen=True)
class StudyDates:
    """
    Einheitliche Datumslogik fuer Korrelation und TSA.

    Korrelation: nur start_date und end_date (Analysefenster).
    TSA: start_date + end_date; end_date ist immer cutoff (letzter Analyse-Tag).
         Prognose ab dem naechsten Intervall nach cutoff bis forecast_end.
         Liegen danach noch Ist-Werte vor, gehoeren sie in Prognosegrafiken (Holdout).
    """

    mode: StudyMode
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    cutoff: pd.Timestamp
    forecast_end: pd.Timestamp
    available_start: pd.Timestamp
    available_end: pd.Timestamp
    user_set_start: bool
    user_set_end: bool
    user_set_cutoff: bool
    user_set_forecast_end: bool

    @property
    def analysis_label(self) -> str:
        return f"{self.start_date.date()} bis {self.end_date.date()}"

    @property
    def forecast_label(self) -> str:
        if self.forecast_end <= self.cutoff:
            return "kein Prognosezeitraum"
        return f"nach {self.cutoff.date()} bis {self.forecast_end.date()}"


@dataclass(frozen=True)
class TSASplit:
    """TSA: Training, optional Holdout-Istwerte fuer Prognoseplots."""

    train: pd.Series
    holdout_actual: pd.Series
    cutoff: pd.Timestamp
    forecast_end: pd.Timestamp
    has_holdout: bool


def resolve_study_dates(
    full_series: pd.Series,
    *,
    mode: StudyMode = "tsa",
    start_date: str | pd.Timestamp | None = None,
    end_date: str | pd.Timestamp | None = None,
    cutoff: str | pd.Timestamp | None = None,
    forecast_end: str | pd.Timestamp | None = None,
) -> StudyDates:
    """
    Leitet Start, Ende, Cutoff und Prognoseende aus der vollen Zeitreihe ab.

    Regeln
    ------
    - end_date gesetzt => cutoff = end_date (TSA; end_date ist Stichtag).
    - cutoff nur noetig, wenn end_date fehlt (dann cutoff oder letztes Datum).
    - forecast_end Standard: letztes verfuegbares Datum der ZR.
    - TSA: forecast_end darf ueber available_end hinausreichen (reine Prognose).
    - Korrelation: cutoff = end_date, forecast_end = end_date (unbenutzt).
    """
    clean = full_series.dropna().sort_index()
    if clean.empty:
        raise ValueError("Zeitreihe enthaelt keine Beobachtungen.")

    available_start = pd.Timestamp(clean.index.min())
    available_end = pd.Timestamp(clean.index.max())

    user_set_start = start_date is not None
    user_set_end = end_date is not None
    user_set_cutoff = cutoff is not None
    user_set_forecast_end = forecast_end is not None

    eff_start = pd.Timestamp(start_date) if user_set_start else available_start
    eff_end = pd.Timestamp(end_date) if user_set_end else available_end

    if user_set_end:
        eff_cutoff = eff_end
    elif user_set_cutoff:
        eff_cutoff = pd.Timestamp(cutoff)
        if not user_set_end:
            eff_end = eff_cutoff
    else:
        eff_cutoff = eff_end

    if user_set_forecast_end:
        eff_forecast_end = pd.Timestamp(forecast_end)
    else:
        eff_forecast_end = available_end

    if eff_start > eff_end:
        raise ValueError(
            f"Start ({eff_start.date()}) liegt nach Ende ({eff_end.date()})."
        )
    if eff_cutoff < eff_start:
        raise ValueError(
            f"Cutoff ({eff_cutoff.date()}) liegt vor Analyse-Start ({eff_start.date()})."
        )
    if eff_start < available_start:
        raise ValueError(
            f"Start ({eff_start.date()}) liegt vor erstem Datenpunkt "
            f"({available_start.date()})."
        )
    if eff_cutoff > available_end:
        raise ValueError(
            f"Cutoff ({eff_cutoff.date()}) liegt nach letztem Datenpunkt "
            f"({available_end.date()})."
        )
    if mode != "tsa" and eff_forecast_end > available_end:
        raise ValueError(
            f"Prognose-Ende ({eff_forecast_end.date()}) liegt nach letztem "
            f"Datenpunkt ({available_end.date()})."
        )
    if eff_forecast_end < eff_cutoff:
        raise ValueError(
            f"Prognose-Ende ({eff_forecast_end.date()}) liegt vor Cutoff ({eff_cutoff.date()})."
        )

    return StudyDates(
        mode=mode,
        start_date=eff_start,
        end_date=eff_end,
        cutoff=eff_cutoff,
        forecast_end=eff_forecast_end,
        available_start=available_start,
        available_end=available_end,
        user_set_start=user_set_start,
        user_set_end=user_set_end,
        user_set_cutoff=user_set_cutoff and not user_set_end,
        user_set_forecast_end=user_set_forecast_end,
    )


def resolve_analysis_window(
    series: pd.Series,
    *,
    start_date: str | pd.Timestamp | None = None,
    end_date: str | pd.Timestamp | None = None,
) -> tuple[pd.Series, AnalysisWindow]:
    """Schneidet auf [start, end] (Korrelation / allgemeine Analyse)."""
    study = resolve_study_dates(
        series, mode="correlation", start_date=start_date, end_date=end_date
    )
    clean = series.dropna().sort_index()
    mask = (clean.index >= study.start_date) & (clean.index <= study.end_date)
    sliced = clean.loc[mask]
    window = AnalysisWindow(
        start_date=study.start_date,
        end_date=study.end_date,
        available_start=study.available_start,
        available_end=study.available_end,
        user_set_start=study.user_set_start,
        user_set_end=study.user_set_end,
    )
    return sliced, window


def prepare_correlation_series(
    full_series: pd.Series, study: StudyDates
) -> pd.Series:
    """Korrelation: nur Daten zwischen start und end."""
    if study.mode != "correlation":
        study = StudyDates(
            mode="correlation",
            start_date=study.start_date,
            end_date=study.end_date,
            cutoff=study.end_date,
            forecast_end=study.end_date,
            available_start=study.available_start,
            available_end=study.available_end,
            user_set_start=study.user_set_start,
            user_set_end=study.user_set_end,
            user_set_cutoff=False,
            user_set_forecast_end=False,
        )
    clean = full_series.dropna().sort_index()
    return clean.loc[
        (clean.index >= study.start_date) & (clean.index <= study.end_date)
    ]


def prepare_tsa_split(full_series: pd.Series, study: StudyDates) -> TSASplit:
    """
    TSA: Training bis cutoff (= end); Holdout = Ist-Werte im Prognosezeitraum.

    Prognose beginnt am naechsten Zeitpunkt nach cutoff (wird in forecast-Modul
    aus dem Index abgeleitet). holdout_actual liefert reale Werte fuer Vergleichsplots.
    """
    clean = full_series.dropna().sort_index()
    train = clean.loc[
        (clean.index >= study.start_date) & (clean.index <= study.cutoff)
    ]
    data_end = min(study.forecast_end, study.available_end)
    holdout = clean.loc[
        (clean.index > study.cutoff) & (clean.index <= data_end)
    ]
    if train.empty:
        raise ValueError("Keine Trainingsdaten im TSA-Analysefenster.")

    return TSASplit(
        train=train,
        holdout_actual=holdout,
        cutoff=study.cutoff,
        forecast_end=study.forecast_end,
        has_holdout=not holdout.empty,
    )


def split_forecast_holdout(
    series: pd.Series,
    *,
    analysis_end: str | pd.Timestamp,
    forecast_end: str | pd.Timestamp | None = None,
) -> tuple[pd.Series, pd.Series]:
    """Abwaertskompatibel: Training bis analysis_end, Holdout danach."""
    full = series.dropna().sort_index()
    study = resolve_study_dates(
        full,
        mode="tsa",
        end_date=analysis_end,
        forecast_end=forecast_end,
    )
    split = prepare_tsa_split(full, study)
    return split.train, split.holdout_actual
