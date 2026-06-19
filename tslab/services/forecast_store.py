"""TSA-Prognosen und Quantile in PostgreSQL persistieren."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import delete
from sqlalchemy.orm import Session

from tslab.db.models import TsaForecastValue
from tslab.services.level_forecast import LevelForecast


def _field_name(quantile: float) -> str:
    return f"q{quantile:.3f}".replace(".", "_")


def persist_level_forecast(
    session: Session,
    *,
    tsa_history_id: int,
    model: str,
    level: LevelForecast,
) -> int:
    """Speichert Mittelwert und Quantile eines Niveau-Prognoselaufs."""
    session.execute(
        delete(TsaForecastValue).where(
            TsaForecastValue.tsa_history_id == tsa_history_id,
            TsaForecastValue.model == model,
        )
    )
    rows: list[TsaForecastValue] = []

    def add_series(series: pd.Series, field: str) -> None:
        for ts, val in series.dropna().items():
            if pd.isna(val):
                continue
            obs = ts.date() if hasattr(ts, "date") else date.fromisoformat(str(ts)[:10])
            rows.append(
                TsaForecastValue(
                    tsa_history_id=tsa_history_id,
                    model=model,
                    obs_date=obs,
                    field=field,
                    value=float(val),
                )
            )

    add_series(level.mean, "mean")
    for q, ser in level.quantiles.items():
        add_series(ser, _field_name(q))

    session.add_all(rows)
    session.commit()
    return len(rows)


def persist_forecast_table(session: Session, *, tsa_history_id: int, model: str, table_path: Path) -> int:
    """Liest Niveau-Prognose-Tabelle (Excel oder legacy CSV) und speichert Werte in der DB."""
    if not table_path.is_file():
        return 0
    if table_path.suffix.lower() == ".xlsx":
        df = pd.read_excel(table_path, engine="openpyxl")
    else:
        df = pd.read_csv(table_path)
    if df.empty or "date" not in df.columns:
        return 0
    session.execute(
        delete(TsaForecastValue).where(
            TsaForecastValue.tsa_history_id == tsa_history_id,
            TsaForecastValue.model == model,
        )
    )
    rows: list[TsaForecastValue] = []
    for _, row in df.iterrows():
        obs = date.fromisoformat(str(row["date"])[:10])
        for col in df.columns:
            if col == "date":
                continue
            val = row[col]
            if pd.isna(val):
                continue
            field = "mean" if col == "prognose_mittelwert" else col.replace("quantil_", "q")
            rows.append(
                TsaForecastValue(
                    tsa_history_id=tsa_history_id,
                    model=model,
                    obs_date=obs,
                    field=field,
                    value=float(val),
                )
            )
    session.add_all(rows)
    session.commit()
    return len(rows)


def persist_tsa_output_forecasts(
    session: Session, *, tsa_history_id: int, output_dir: Path, models_run: list[str]
) -> int:
    """Persistiert Forward-Prognose-Tabellen aller gelaufenen Modelle."""
    total = 0
    for model in models_run:
        tag = model.replace("-", "_")
        patterns = (f"{tag}_forecast_forward.xlsx", f"{tag}_forecast_forward.csv")
        for pattern in patterns:
            for table_path in sorted(output_dir.rglob(pattern)):
                total += persist_forecast_table(
                    session, tsa_history_id=tsa_history_id, model=model, table_path=table_path
                )
    return total
