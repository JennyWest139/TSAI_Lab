"""Tabellen-Export fuer Analyse-Laeufe (Excel statt CSV)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def write_dataframe_excel(df: pd.DataFrame, path: Path, *, sheet_name: str = "Daten") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = path.with_suffix(".xlsx")
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
    return out
