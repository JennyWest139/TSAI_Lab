"""Kreuzkorrelation zweier Zeitreihen (nur Lesen aus Upload-DB)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from tslab.services.analysis_mode import (
    AnalysisModeConfig,
    prepare_model_returns,
    returns_display,
)
from tslab.services.analysis_window import StudyDates
from tslab.services.timeseries_store import load_series_full_pandas


@dataclass(frozen=True)
class CorrelationResult:
    series_a: str
    series_b: str
    study: StudyDates
    table: pd.DataFrame
    aligned_observations: int
    lag_definition: str
    analysis_mode: str
    data_basis: str
    series_a_values: pd.Series
    series_b_values: pd.Series

    @property
    def best_lag(self) -> int | None:
        t = self.table.dropna(subset=["correlation"])
        if t.empty:
            return None
        row = t.loc[t["correlation"].abs().idxmax()]
        return int(row["lag"])


LAG_DEFINITION = (
    "Lag h: Korrelation zwischen Serie A(t) und Serie B(t+h). "
    "h>0: B liegt h Perioden vor A; h<0: B liegt |h| Perioden nach A."
)


def resolve_correlation_study_dates(
    series_a: pd.Series,
    series_b: pd.Series,
    *,
    start_date: str | pd.Timestamp | None = None,
    end_date: str | pd.Timestamp | None = None,
) -> StudyDates:
    """Gemeinsames Fenster: Schnitt der verfuegbaren Daten beider Reihen."""
    a = series_a.dropna().sort_index()
    b = series_b.dropna().sort_index()
    if a.empty or b.empty:
        raise ValueError("Eine der Zeitreihen enthaelt keine Beobachtungen.")

    avail_start = max(pd.Timestamp(a.index.min()), pd.Timestamp(b.index.min()))
    avail_end = min(pd.Timestamp(a.index.max()), pd.Timestamp(b.index.max()))
    if avail_start > avail_end:
        raise ValueError("Keine ueberlappenden Daten zwischen beiden Zeitreihen.")

    user_set_start = start_date is not None
    user_set_end = end_date is not None
    eff_start = pd.Timestamp(start_date) if user_set_start else avail_start
    eff_end = pd.Timestamp(end_date) if user_set_end else avail_end

    if eff_start > eff_end:
        raise ValueError(
            f"Start ({eff_start.date()}) liegt nach Ende ({eff_end.date()})."
        )
    if eff_start < avail_start or eff_end > avail_end:
        raise ValueError(
            f"Fenster {eff_start.date()}..{eff_end.date()} ausserhalb des "
            f"Ueberlappungsbereichs {avail_start.date()}..{avail_end.date()}."
        )

    return StudyDates(
        mode="correlation",
        start_date=eff_start,
        end_date=eff_end,
        cutoff=eff_end,
        forecast_end=eff_end,
        available_start=avail_start,
        available_end=avail_end,
        user_set_start=user_set_start,
        user_set_end=user_set_end,
        user_set_cutoff=False,
        user_set_forecast_end=False,
    )


def load_pair_for_correlation(
    session: Session,
    slug_a: str,
    slug_b: str,
    *,
    start_date: str | pd.Timestamp | None = None,
    end_date: str | pd.Timestamp | None = None,
) -> tuple[pd.Series, pd.Series, StudyDates]:
    """Laedt zwei Reihen; schneidet auf gemeinsames Analysefenster (read-only)."""
    full_a = load_series_full_pandas(session, slug_a)
    full_b = load_series_full_pandas(session, slug_b)
    study = resolve_correlation_study_dates(
        full_a, full_b, start_date=start_date, end_date=end_date
    )
    a = full_a.loc[
        (full_a.index >= study.start_date) & (full_a.index <= study.end_date)
    ]
    b = full_b.loc[
        (full_b.index >= study.start_date) & (full_b.index <= study.end_date)
    ]
    return a, b, study


def prepare_correlation_returns(
    levels_a: pd.Series,
    levels_b: pd.Series,
    mode_config: AnalysisModeConfig,
) -> tuple[pd.Series, pd.Series]:
    """Kont. Renditen gemaess Analysemodus (thesis vs. extended)."""
    a = prepare_model_returns(levels_a, mode_config).rename(levels_a.name or "a")
    b = prepare_model_returns(levels_b, mode_config).rename(levels_b.name or "b")
    return a, b


def align_series(a: pd.Series, b: pd.Series) -> pd.DataFrame:
    """Innere Vereinigung auf gemeinsame Daten (keine DB-Aenderung)."""
    df = pd.concat([a, b], axis=1, join="inner").dropna()
    df.columns = ["a", "b"]
    return df


def _pearson(x: np.ndarray, y: np.ndarray) -> float:
    """Pearson auf gleich langen Vektoren (positionsbasiert, ohne Index-Join)."""
    if len(x) < 3:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def compute_cross_correlation(
    a: pd.Series,
    b: pd.Series,
    *,
    max_lag: int = 24,
    lags: list[int] | None = None,
) -> pd.DataFrame:
    """
    Pearson-Korrelation pro Lag (positionsbasiert).

    Wichtig: nicht ``Series.corr`` auf verschobenen Slices – pandas wuerde
    dort nach Datum alignen (gleicher Monat) statt A(t) mit B(t+h).

    Returns DataFrame: lag, correlation, n_obs
    """
    xy = align_series(a, b)
    if len(xy) < 3:
        raise ValueError(
            f"Zu wenige gemeinsame Beobachtungen ({len(xy)}), mindestens 3 noetig."
        )

    av = xy["a"].to_numpy(dtype=float)
    bv = xy["b"].to_numpy(dtype=float)

    if lags is None:
        lags = list(range(-max_lag, max_lag + 1))

    rows: list[dict] = []
    for lag in lags:
        if lag > 0:
            xa, xb = av[lag:], bv[:-lag]
        elif lag < 0:
            k = -lag
            xa, xb = av[:-k], bv[k:]
        else:
            xa, xb = av, bv
        n = len(xa)
        rows.append({"lag": int(lag), "correlation": _pearson(xa, xb), "n_obs": n})

    return pd.DataFrame(rows)


def run_correlation(
    session: Session,
    slug_a: str,
    slug_b: str,
    *,
    mode_config: AnalysisModeConfig,
    start_date: str | pd.Timestamp | None = None,
    end_date: str | pd.Timestamp | None = None,
    max_lag: int = 24,
    lags: list[int] | None = None,
) -> CorrelationResult:
    levels_a, levels_b, study = load_pair_for_correlation(
        session, slug_a, slug_b, start_date=start_date, end_date=end_date
    )
    a, b = prepare_correlation_returns(levels_a, levels_b, mode_config)
    table = compute_cross_correlation(a, b, max_lag=max_lag, lags=lags)
    disp = returns_display(mode_config)
    return CorrelationResult(
        series_a=slug_a,
        series_b=slug_b,
        study=study,
        table=table,
        aligned_observations=len(align_series(a, b)),
        lag_definition=LAG_DEFINITION,
        analysis_mode=mode_config.slug,
        data_basis=disp.data_basis,
        series_a_values=a,
        series_b_values=b,
    )
