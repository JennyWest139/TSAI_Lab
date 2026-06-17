"""Zeitreihen in PostgreSQL speichern und laden."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from tslab.db.engine import get_session, init_db
from tslab.db.models import Observation, TimeSeries, UploadHistory
from tslab.services.analysis_window import AnalysisWindow, resolve_analysis_window
from tslab.services.ingest_werte import _parse_german_number, load_pdax_series
from tslab.services.date_parse import parse_observation_dates


def _slugify(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_") or "series"


def _series_to_frame(
    csv_path: Path,
    date_column: str,
    value_column: str,
    *,
    date_parse_mode: str = "auto",
    date_format: str | None = None,
    dayfirst: bool | None = None,
    sep: str,
    encoding: str,
) -> pd.DataFrame:
    df = pd.read_csv(csv_path, sep=sep, encoding=encoding, dtype=str)
    if date_column not in df.columns or value_column not in df.columns:
        raise KeyError(f"Spalten {date_column!r}, {value_column!r} fehlen in {csv_path}")

    dates = parse_observation_dates(
        df[date_column],
        mode=date_parse_mode,
        strftime_format=date_format,
        dayfirst=dayfirst,
    )
    values = _parse_german_number(df[value_column])
    out = pd.DataFrame({"obs_date": dates, "value": values}).dropna()
    out = out.sort_values("obs_date").drop_duplicates("obs_date", keep="last")
    return out


def import_series_from_csv(
    session: Session,
    *,
    name: str,
    csv_path: str | Path,
    date_column: str = "Datum1",
    value_column: str = "PDAX",
    date_parse_mode: str = "auto",
    date_format: str | None = None,
    dayfirst: bool | None = None,
    sep: str = ";",
    encoding: str = "utf-8-sig",
    replace_existing: bool = True,
) -> TimeSeries:
    """Importiert eine Wertespalte aus CSV in die DB."""
    path = Path(csv_path)
    frame = _series_to_frame(
        path,
        date_column,
        value_column,
        date_parse_mode=date_parse_mode,
        date_format=date_format,
        dayfirst=dayfirst,
        sep=sep,
        encoding=encoding,
    )
    if frame.empty:
        raise ValueError(f"Keine Werte fuer {value_column} in {path}")

    slug = _slugify(name)
    existing = session.scalar(select(TimeSeries).where(TimeSeries.slug == slug))

    if existing and replace_existing:
        session.execute(
            delete(Observation).where(Observation.series_id == existing.id)
        )
        ts = existing
        ts.source_file = str(path)
        ts.value_column = value_column
        ts.date_column = date_column
    elif existing:
        raise ValueError(f"Zeitreihe {name!r} existiert bereits (slug={slug}).")
    else:
        ts = TimeSeries(
            name=name,
            slug=slug,
            source_file=str(path),
            value_column=value_column,
            date_column=date_column,
        )
        session.add(ts)
        session.flush()

    obs_rows = [
        Observation(
            series_id=ts.id,
            obs_date=row.obs_date.date(),
            value=float(row.value),
        )
        for row in frame.itertuples(index=False)
    ]
    session.add_all(obs_rows)

    ts.first_date = frame["obs_date"].min().date()
    ts.last_date = frame["obs_date"].max().date()
    ts.observation_count = len(obs_rows)

    session.add(
        UploadHistory(
            filename=path.name,
            series_id=ts.id,
            rows_imported=len(obs_rows),
            note=f"Import Spalte {value_column}",
        )
    )
    session.commit()
    session.refresh(ts)
    return ts


def list_series(session: Session) -> list[TimeSeries]:
    return list(session.scalars(select(TimeSeries).order_by(TimeSeries.name)))


def get_series_by_slug(session: Session, slug: str) -> TimeSeries | None:
    return session.scalar(select(TimeSeries).where(TimeSeries.slug == slug))


def load_series_full_pandas(
    session: Session,
    series: TimeSeries | str | int,
) -> pd.Series:
    """Laedt die vollstaendige Zeitreihe aus der DB (ohne Datumsfilter)."""
    if isinstance(series, str):
        ts = get_series_by_slug(session, series)
        if ts is None:
            ts = session.scalar(select(TimeSeries).where(TimeSeries.name == series))
    elif isinstance(series, int):
        ts = session.get(TimeSeries, series)
    else:
        ts = series

    if ts is None:
        raise LookupError(f"Zeitreihe nicht gefunden: {series!r}")

    rows = session.scalars(
        select(Observation)
        .where(Observation.series_id == ts.id)
        .order_by(Observation.obs_date)
    ).all()
    if not rows:
        raise ValueError(f"Keine Beobachtungen fuer {ts.name!r}.")

    idx = pd.DatetimeIndex([r.obs_date for r in rows], freq="MS")
    return pd.Series([r.value for r in rows], index=idx, name=ts.name)


def load_series_pandas(
    session: Session,
    series: TimeSeries | str | int,
    *,
    start_date: str | pd.Timestamp | None = None,
    end_date: str | pd.Timestamp | None = None,
) -> tuple[pd.Series, AnalysisWindow]:
    """Laedt ZR aus DB; optional mit Analysefenster (Korrelation)."""
    s = load_series_full_pandas(session, series)
    return resolve_analysis_window(s, start_date=start_date, end_date=end_date)


def available_dates_for_series(session: Session, series_id: int) -> list[date]:
    """Alle Daten mit Werten (fuer Kalender / UI)."""
    rows = session.scalars(
        select(Observation.obs_date)
        .where(Observation.series_id == series_id)
        .order_by(Observation.obs_date)
    ).all()
    return list(rows)


def seed_werte_csv_columns(
    session: Session,
    csv_path: str | Path | None = None,
    *,
    columns: list[str] | None = None,
) -> list[TimeSeries]:
    """
    Importiert numerische Spalten aus Werte.csv (Standard: PDAX, DAX, ...).
    """
    from tslab.config_loader import load_defaults

    cfg = load_defaults()
    path = Path(csv_path or cfg["werte_csv"])
    csv_cfg = cfg["csv"]
    date_col = csv_cfg["date_column"]

    df = pd.read_csv(
        path,
        sep=csv_cfg.get("sep", ";"),
        encoding=csv_cfg.get("encoding", "utf-8-sig"),
        dtype=str,
    )
    if columns is None:
        columns = [
            c
            for c in df.columns
            if c not in ("Nr", date_col, "Datum2")
            and _parse_german_number(df[c]).notna().any()
        ]

    imported: list[TimeSeries] = []
    for col in columns:
        ts = import_series_from_csv(
            session,
            name=col,
            csv_path=path,
            date_column=date_col,
            value_column=col,
            date_parse_mode="auto",
            date_format=csv_cfg.get("date_format"),
            sep=csv_cfg.get("sep", ";"),
            encoding=csv_cfg.get("encoding", "utf-8-sig"),
        )
        imported.append(ts)
    return imported


def load_pdax_full(
    session: Session | None = None,
    *,
    prefer_db: bool = True,
    csv_path: str | Path | None = None,
) -> pd.Series:
    """PDAX vollstaendig (DB oder CSV)."""
    if prefer_db and session is not None:
        try:
            return load_series_full_pandas(session, "pdax")
        except LookupError:
            pass
    return load_pdax_series(csv_path)


def load_pdax_from_db_or_csv(
    session: Session | None = None,
    *,
    prefer_db: bool = True,
    start_date: str | pd.Timestamp | None = None,
    end_date: str | pd.Timestamp | None = None,
) -> tuple[pd.Series, AnalysisWindow]:
    """PDAX mit Analysefenster (Korrelation)."""
    full = load_pdax_full(session, prefer_db=prefer_db)
    return resolve_analysis_window(full, start_date=start_date, end_date=end_date)
